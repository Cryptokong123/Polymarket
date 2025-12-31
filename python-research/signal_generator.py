#!/usr/bin/env python3
"""
Signal Generator - Main entry point for the Python research layer.
Analyzes markets and outputs trading signals for the executor to consume.

Usage:
    python signal_generator.py [--once] [--dry-run]

Signals are written to shared/signals/ as JSON files.
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from agents.llm_analyzer import LLMAnalyzer
from agents.market_research import MarketResearcher
from agents.signal_types import TradingSignal, MarketData, AnalysisResult
from agents.crypto_analyzer import CryptoAnalyzer
from agents.sentiment_analyzer import SentimentAnalyzer, MarketSentiment

# Ensure log directory exists
log_dir = Path(config.logging.file).parent
log_dir.mkdir(parents=True, exist_ok=True)

# Ensure signal output directory exists
config.signals_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.logging.file, mode="a"),
    ],
)
logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Main signal generator class.
    Fetches markets, analyzes them with LLM, and generates trading signals.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run or config.trading.dry_run

        # Initialize components
        self.researcher = MarketResearcher(
            gamma_url=config.polymarket.gamma_url,
            clob_url=config.polymarket.clob_url,
            newsapi_key=config.research.newsapi_key,
            tavily_api_key=config.research.tavily_api_key,
        )

        self.analyzer = LLMAnalyzer(
            provider=config.llm.provider,
            # Ollama (FREE)
            ollama_base_url=config.llm.ollama_base_url,
            ollama_model=config.llm.ollama_model,
            # Groq (FREE)
            groq_api_key=config.llm.groq_api_key,
            groq_model=config.llm.groq_model,
            # Google (FREE tier)
            google_api_key=config.llm.google_api_key,
            google_model=config.llm.google_model,
            # Paid options
            openai_api_key=config.llm.openai_api_key,
            anthropic_api_key=config.llm.anthropic_api_key,
            model=config.llm.model,
        )

        # Crypto analyzer for BTC/crypto price markets
        self.crypto_analyzer = CryptoAnalyzer() if config.crypto.enabled else None

        # Sentiment analyzer for market context
        self.sentiment_analyzer = SentimentAnalyzer(
            finnhub_api_key=config.sentiment.finnhub_api_key
        ) if config.sentiment.enabled else None
        self._cached_sentiment: Optional[MarketSentiment] = None
        self._sentiment_cache_time: Optional[datetime] = None

        # Paths
        self.signals_dir = config.signals_dir

        # Trading parameters
        self.min_ev = config.trading.min_expected_value
        self.max_position = config.trading.max_position_size
        self.min_liquidity = config.trading.min_liquidity
        self.max_positions = config.trading.max_positions

        # Tracking
        self.signals_generated = 0
        self.markets_analyzed = 0
        self.active_signals: Dict[str, TradingSignal] = {}

        logger.info(f"Signal Generator initialized (dry_run={self.dry_run})")
        logger.info(f"Min EV threshold: {self.min_ev * 100:.1f}%")
        logger.info(f"Max position size: ${self.max_position}")

    async def get_tradeable_markets(self) -> List[MarketData]:
        """Fetch active markets with sufficient liquidity"""
        logger.info("Fetching tradeable markets...")

        markets = await self.researcher.get_tradeable_markets(
            min_liquidity=self.min_liquidity,
            limit=config.research.max_markets_per_scan,
        )

        logger.info(f"Found {len(markets)} tradeable markets")
        return markets

    async def get_market_sentiment(self) -> Optional[MarketSentiment]:
        """Get cached market sentiment (refreshes every 5 minutes)"""
        if not self.sentiment_analyzer:
            return None

        # Check cache
        cache_ttl = config.sentiment.cache_ttl
        if (self._cached_sentiment and self._sentiment_cache_time and
            (datetime.utcnow() - self._sentiment_cache_time).seconds < cache_ttl):
            return self._cached_sentiment

        try:
            logger.info("Fetching market sentiment...")
            self._cached_sentiment = await self.sentiment_analyzer.get_market_sentiment()
            self._sentiment_cache_time = datetime.utcnow()

            # Log sentiment summary
            logger.info(f"  Fear & Greed: {self._cached_sentiment.fear_greed_value}/100 ({self._cached_sentiment.fear_greed_label})")
            logger.info(f"  News Sentiment: {self._cached_sentiment.news_sentiment_label}")
            logger.info(f"  Overall: {self._cached_sentiment.overall_sentiment.upper()}")

            return self._cached_sentiment
        except Exception as e:
            logger.warning(f"Failed to fetch sentiment: {e}")
            return None

    def calculate_expected_value(
        self,
        predicted_prob: float,
        current_price: float,
        side: str,
    ) -> float:
        """
        Calculate expected value for a trade.

        For BUY:
        EV = (predicted_prob * (1 - price)) - ((1 - predicted_prob) * price)

        For SELL:
        EV = ((1 - predicted_prob) * price) - (predicted_prob * (1 - price))
        """
        if side == "BUY":
            # Expected profit = prob_win * potential_profit - prob_lose * cost
            return (predicted_prob * (1 - current_price)) - ((1 - predicted_prob) * current_price)
        else:
            # For selling
            return ((1 - predicted_prob) * current_price) - (predicted_prob * (1 - current_price))

    def create_signal(
        self,
        market: MarketData,
        analysis: AnalysisResult,
        token_type: str,
        side: str,
        current_price: float,
        expected_value: float,
    ) -> TradingSignal:
        """Create a trading signal from analysis results"""
        token = market.yes_token if token_type == "YES" else market.no_token
        predicted_prob = analysis.predicted_probability if token_type == "YES" else (1 - analysis.predicted_probability)

        # Calculate suggested position size based on confidence
        # Kelly criterion inspired but more conservative
        suggested_size = min(
            self.max_position,
            self.max_position * analysis.confidence * 0.5,  # Half-Kelly
        )

        # Calculate price limits
        if side == "BUY":
            max_price = min(predicted_prob + 0.05, 0.95)  # Don't overpay
            min_price = 0.0
        else:
            max_price = 1.0
            min_price = max(predicted_prob - 0.05, 0.05)  # Don't undersell

        return TradingSignal(
            market_id=market.condition_id,
            token_id=token.token_id if token else "",
            market_question=market.question,
            side=side,
            token_type=token_type,
            current_price=current_price,
            predicted_probability=predicted_prob,
            expected_value=expected_value,
            confidence=analysis.confidence,
            reasoning=analysis.reasoning,
            suggested_size=suggested_size,
            max_price=max_price,
            min_price=min_price,
            expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
            metadata={
                "liquidity": market.liquidity,
                "volume_24h": market.volume_24h,
                "key_factors": analysis.key_factors,
                "risk_factors": analysis.risk_factors,
                "sentiment": analysis.sentiment,
            },
        )

    async def analyze_crypto_market(self, market: MarketData, crypto_symbol: str) -> Optional[TradingSignal]:
        """
        Analyze a crypto price prediction market with technical analysis.
        """
        try:
            logger.info(f"  📊 Crypto market detected ({crypto_symbol}) - Fetching TA...")

            # Get technical indicators
            indicators = await self.crypto_analyzer.get_technical_indicators(crypto_symbol)
            technical_data = indicators.get_summary()
            prediction_hint = indicators.get_prediction_hint()

            # Get news context
            context = await self.researcher.get_context_for_market(market)

            # Add sentiment context (especially Fear/Greed for crypto)
            sentiment = await self.get_market_sentiment()
            if sentiment:
                context = f"{context}\n\n{sentiment.get_summary()}" if context else sentiment.get_summary()

            # Analyze with crypto-specific LLM prompt
            analysis = await self.analyzer.analyze_crypto_market(
                market, technical_data, prediction_hint, context
            )
            self.markets_analyzed += 1

            # Check confidence threshold for crypto
            if analysis.confidence < config.crypto.min_confidence:
                logger.info(f"  ✗ Crypto confidence too low: {analysis.confidence:.1%} < {config.crypto.min_confidence:.1%}")
                return None

            # Get current prices
            yes_token = market.yes_token
            no_token = market.no_token

            if not yes_token or not no_token:
                logger.warning(f"Market {market.question[:50]}... missing tokens")
                return None

            yes_price = yes_token.price
            no_price = no_token.price

            # Calculate EV for both sides
            yes_ev = self.calculate_expected_value(
                analysis.predicted_probability, yes_price, "BUY"
            )
            no_ev = self.calculate_expected_value(
                1 - analysis.predicted_probability, no_price, "BUY"
            )

            # Apply crypto EV bonus (TA gives edge)
            crypto_bonus = config.crypto.ev_bonus
            yes_ev += crypto_bonus
            no_ev += crypto_bonus

            # Also apply new market bonus if applicable
            is_new = market.is_new_market(config.trading.new_market_hours)
            if is_new and config.trading.prioritize_new_markets:
                yes_ev += config.trading.new_market_ev_bonus
                no_ev += config.trading.new_market_ev_bonus

            # Log analysis
            logger.info(f"  BTC Price: ${indicators.current_price:,.2f}")
            logger.info(f"  15m Change: {indicators.change_15m:+.2%} | 1h: {indicators.change_1h:+.2%}")
            logger.info(f"  RSI: {indicators.rsi_14:.1f} | Trend: {indicators.trend_short}")
            logger.info(f"  TA Signal: {prediction_hint}")
            logger.info(f"  Predicted: {analysis.predicted_probability:.1%} | Market: {yes_price:.1%}")
            logger.info(f"  YES EV: {yes_ev:.2%} | NO EV: {no_ev:.2%} (crypto bonus: +{crypto_bonus:.1%})")
            logger.info(f"  Confidence: {analysis.confidence:.1%}")

            # Check if either side has sufficient EV
            if yes_ev > self.min_ev and yes_ev >= no_ev:
                signal = self.create_signal(
                    market=market,
                    analysis=analysis,
                    token_type="YES",
                    side="BUY",
                    current_price=yes_price,
                    expected_value=yes_ev,
                )
                # Add crypto metadata
                signal.metadata["is_crypto_market"] = True
                signal.metadata["crypto_symbol"] = crypto_symbol
                signal.metadata["btc_price"] = indicators.current_price
                signal.metadata["rsi"] = indicators.rsi_14
                signal.metadata["trend"] = indicators.trend_short
                signal.metadata["ta_signal"] = prediction_hint
                signal.metadata["crypto_bonus"] = crypto_bonus
                logger.info(f"  ✓ Signal generated: BUY YES @ ${yes_price:.4f}")
                return signal

            elif no_ev > self.min_ev:
                signal = self.create_signal(
                    market=market,
                    analysis=analysis,
                    token_type="NO",
                    side="BUY",
                    current_price=no_price,
                    expected_value=no_ev,
                )
                # Add crypto metadata
                signal.metadata["is_crypto_market"] = True
                signal.metadata["crypto_symbol"] = crypto_symbol
                signal.metadata["btc_price"] = indicators.current_price
                signal.metadata["rsi"] = indicators.rsi_14
                signal.metadata["trend"] = indicators.trend_short
                signal.metadata["ta_signal"] = prediction_hint
                signal.metadata["crypto_bonus"] = crypto_bonus
                logger.info(f"  ✓ Signal generated: BUY NO @ ${no_price:.4f}")
                return signal

            else:
                logger.info(f"  ✗ No trade opportunity (EV below threshold)")
                return None

        except Exception as e:
            logger.error(f"Error analyzing crypto market: {e}")
            return None

    async def analyze_market(self, market: MarketData) -> Optional[TradingSignal]:
        """
        Analyze a market and generate trading signal if opportunity exists.
        """
        try:
            # Check if this is a crypto price market
            if self.crypto_analyzer:
                crypto_symbol = self.crypto_analyzer.detect_crypto_market(market.question)
                if crypto_symbol:
                    return await self.analyze_crypto_market(market, crypto_symbol)

            # Standard market analysis
            # Get context from news sources
            context = await self.researcher.get_context_for_market(market)

            # Add sentiment context if available
            sentiment = await self.get_market_sentiment()
            if sentiment:
                sentiment_context = sentiment.get_summary()
                if context:
                    context = f"{context}\n\n{sentiment_context}"
                else:
                    context = sentiment_context

            # Analyze with LLM
            analysis = await self.analyzer.analyze_market(market, context)
            self.markets_analyzed += 1

            # Get current prices
            yes_token = market.yes_token
            no_token = market.no_token

            if not yes_token or not no_token:
                logger.warning(f"Market {market.question[:50]}... missing tokens")
                return None

            yes_price = yes_token.price
            no_price = no_token.price

            # Calculate EV for both sides
            yes_ev = self.calculate_expected_value(
                analysis.predicted_probability, yes_price, "BUY"
            )
            no_ev = self.calculate_expected_value(
                1 - analysis.predicted_probability, no_price, "BUY"
            )

            # Apply new market EV bonus for first-mover edge
            is_new = market.is_new_market(config.trading.new_market_hours)
            new_market_bonus = 0.0
            if is_new and config.trading.prioritize_new_markets:
                new_market_bonus = config.trading.new_market_ev_bonus
                yes_ev += new_market_bonus
                no_ev += new_market_bonus

            # Log analysis
            logger.info(f"Analyzed: {market.question[:60]}...")
            logger.info(f"  Predicted: {analysis.predicted_probability:.1%} | Market: {yes_price:.1%}")
            if is_new:
                age_hours = market.age_hours or 0
                logger.info(f"  🆕 NEW MARKET ({age_hours:.1f}h old) - EV bonus: +{new_market_bonus:.1%}")
            logger.info(f"  YES EV: {yes_ev:.2%} | NO EV: {no_ev:.2%}")
            logger.info(f"  Confidence: {analysis.confidence:.1%}")

            # Check if either side has sufficient EV
            if yes_ev > self.min_ev and yes_ev >= no_ev:
                signal = self.create_signal(
                    market=market,
                    analysis=analysis,
                    token_type="YES",
                    side="BUY",
                    current_price=yes_price,
                    expected_value=yes_ev,
                )
                # Add new market info to metadata
                if is_new:
                    signal.metadata["is_new_market"] = True
                    signal.metadata["market_age_hours"] = market.age_hours
                    signal.metadata["new_market_bonus"] = new_market_bonus
                logger.info(f"  ✓ Signal generated: BUY YES @ ${yes_price:.4f}")
                return signal

            elif no_ev > self.min_ev:
                signal = self.create_signal(
                    market=market,
                    analysis=analysis,
                    token_type="NO",
                    side="BUY",
                    current_price=no_price,
                    expected_value=no_ev,
                )
                # Add new market info to metadata
                if is_new:
                    signal.metadata["is_new_market"] = True
                    signal.metadata["market_age_hours"] = market.age_hours
                    signal.metadata["new_market_bonus"] = new_market_bonus
                logger.info(f"  ✓ Signal generated: BUY NO @ ${no_price:.4f}")
                return signal

            else:
                logger.info(f"  ✗ No trade opportunity (EV below threshold)")
                return None

        except Exception as e:
            logger.error(f"Error analyzing market {market.question[:50]}...: {e}")
            return None

    def save_signal(self, signal: TradingSignal) -> Path:
        """Save signal to shared directory for executor to consume"""
        filename = f"{signal.signal_id}.json"
        filepath = self.signals_dir / filename

        if self.dry_run:
            logger.info(f"[DRY RUN] Would save signal to: {filepath}")
            logger.info(f"[DRY RUN] Signal: {signal.to_json()}")
        else:
            with open(filepath, "w") as f:
                f.write(signal.to_json())
            logger.info(f"Signal saved: {filepath}")

        self.signals_generated += 1
        self.active_signals[signal.signal_id] = signal

        return filepath

    async def run_once(self) -> int:
        """
        Run a single scan cycle.

        Returns:
            Number of signals generated
        """
        logger.info(f"[{datetime.utcnow().isoformat()}] Starting market scan...")

        try:
            # Fetch tradeable markets
            markets = await self.get_tradeable_markets()

            if not markets:
                logger.warning("No tradeable markets found")
                return 0

            signals_this_run = 0

            # Analyze each market
            for i, market in enumerate(markets):
                logger.info(f"Processing market {i+1}/{len(markets)}")

                signal = await self.analyze_market(market)
                if signal:
                    self.save_signal(signal)
                    signals_this_run += 1

                # Rate limiting
                await asyncio.sleep(1)

            logger.info(f"Scan complete. Generated {signals_this_run} signals")
            return signals_this_run

        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
            return 0

    async def run(self):
        """Main loop - continuously scan for opportunities"""
        scan_interval = config.research.scan_interval

        logger.info("=" * 60)
        logger.info("POLYMARKET SIGNAL GENERATOR STARTED")
        logger.info("=" * 60)
        logger.info(f"LLM Provider: {config.llm.provider.upper()}")
        if config.llm.provider == "ollama":
            logger.info(f"  Model: {config.llm.ollama_model}")
        elif config.llm.provider == "groq":
            logger.info(f"  Model: {config.llm.groq_model}")
        elif config.llm.provider == "google":
            logger.info(f"  Model: {config.llm.google_model}")
        logger.info(f"Scan interval: {scan_interval}s")
        logger.info(f"Min EV threshold: {self.min_ev * 100:.1f}%")
        logger.info(f"Max position size: ${self.max_position}")
        logger.info(f"Min liquidity: ${self.min_liquidity}")
        if config.trading.prioritize_new_markets:
            logger.info(f"New market edge: ENABLED")
            logger.info(f"  New market threshold: <{config.trading.new_market_hours}h old")
            logger.info(f"  EV bonus for new markets: +{config.trading.new_market_ev_bonus:.1%}")
        if config.crypto.enabled:
            logger.info(f"Crypto TA: ENABLED")
            logger.info(f"  EV bonus for crypto markets: +{config.crypto.ev_bonus:.1%}")
            logger.info(f"  Min confidence for crypto: {config.crypto.min_confidence:.0%}")
            logger.info(f"  Fast scan interval: {config.crypto.fast_scan_interval}s")
        if config.sentiment.enabled:
            logger.info(f"Sentiment Analysis: ENABLED")
            logger.info(f"  Fear & Greed Index: Active")
            if config.sentiment.finnhub_api_key:
                logger.info(f"  Finnhub (news + calendar): Active")
            else:
                logger.info(f"  Finnhub: Not configured (optional)")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        while True:
            try:
                await self.run_once()

                logger.info(f"Total signals generated: {self.signals_generated}")
                logger.info(f"Total markets analyzed: {self.markets_analyzed}")
                logger.info(f"Sleeping for {scan_interval}s...")

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            await asyncio.sleep(scan_interval)

        # Cleanup
        await self.researcher.close()

    async def cleanup(self):
        """Clean up resources"""
        await self.researcher.close()
        if self.crypto_analyzer:
            await self.crypto_analyzer.close()
        if self.sentiment_analyzer:
            await self.sentiment_analyzer.close()


async def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description="Polymarket Signal Generator"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't loop)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually save signals",
    )
    args = parser.parse_args()

    # Validate configuration
    is_valid, errors = config.validate()
    if not is_valid:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        sys.exit(1)

    # Create and run generator
    generator = SignalGenerator(dry_run=args.dry_run)

    try:
        if args.once:
            signals = await generator.run_once()
            print(f"Generated {signals} signals")
        else:
            await generator.run()
    finally:
        await generator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
