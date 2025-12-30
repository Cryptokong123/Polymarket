"""
Crypto Analyzer - Technical Analysis for Bitcoin/Crypto Price Prediction Markets

Provides real-time price data and technical indicators to enhance
AI predictions for short-term crypto price markets (15-min, 1-hour, etc.)
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Price data point"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TechnicalIndicators:
    """Technical analysis indicators for a crypto asset"""
    symbol: str
    current_price: float
    timestamp: str

    # Price changes
    change_5m: float = 0.0
    change_15m: float = 0.0
    change_1h: float = 0.0
    change_4h: float = 0.0
    change_24h: float = 0.0

    # Moving averages
    sma_5: float = 0.0      # 5-period SMA
    sma_15: float = 0.0     # 15-period SMA
    sma_50: float = 0.0     # 50-period SMA
    ema_12: float = 0.0     # 12-period EMA
    ema_26: float = 0.0     # 26-period EMA

    # Momentum indicators
    rsi_14: float = 50.0    # RSI (14-period)
    macd: float = 0.0       # MACD line
    macd_signal: float = 0.0  # MACD signal line
    macd_histogram: float = 0.0

    # Volatility
    bollinger_upper: float = 0.0
    bollinger_middle: float = 0.0
    bollinger_lower: float = 0.0
    atr_14: float = 0.0     # Average True Range

    # Trend signals
    trend_short: str = "neutral"   # 5-15 min trend
    trend_medium: str = "neutral"  # 1-4 hour trend
    momentum: str = "neutral"      # Overall momentum

    # Support/Resistance (recent)
    support_level: float = 0.0
    resistance_level: float = 0.0

    # Volume analysis
    volume_24h: float = 0.0
    volume_change: float = 0.0  # vs 24h average

    def get_summary(self) -> str:
        """Get a human-readable summary for LLM context"""
        rsi_status = "oversold" if self.rsi_14 < 30 else "overbought" if self.rsi_14 > 70 else "neutral"

        price_vs_sma = "above" if self.current_price > self.sma_15 else "below"

        macd_signal_str = "bullish" if self.macd > self.macd_signal else "bearish"

        lines = [
            f"=== {self.symbol} Technical Analysis ===",
            f"Price: ${self.current_price:,.2f}",
            f"",
            f"-- Price Changes --",
            f"  5 min:  {self.change_5m:+.2%}",
            f"  15 min: {self.change_15m:+.2%}",
            f"  1 hour: {self.change_1h:+.2%}",
            f"  4 hour: {self.change_4h:+.2%}",
            f"  24 hour: {self.change_24h:+.2%}",
            f"",
            f"-- Trend Analysis --",
            f"  Short-term (5-15m): {self.trend_short.upper()}",
            f"  Medium-term (1-4h): {self.trend_medium.upper()}",
            f"  Overall momentum: {self.momentum.upper()}",
            f"",
            f"-- Technical Indicators --",
            f"  RSI(14): {self.rsi_14:.1f} ({rsi_status})",
            f"  Price vs 15-MA: {price_vs_sma} by {abs(self.current_price - self.sma_15)/self.sma_15:.2%}" if self.sma_15 > 0 else "  Price vs 15-MA: N/A",
            f"  MACD: {macd_signal_str} (histogram: {self.macd_histogram:+.2f})",
            f"",
            f"-- Volatility --",
            f"  Bollinger Band position: {'upper' if self.current_price > self.bollinger_upper else 'lower' if self.current_price < self.bollinger_lower else 'middle'}",
            f"  ATR(14): ${self.atr_14:.2f}",
            f"",
            f"-- Key Levels --",
            f"  Resistance: ${self.resistance_level:,.2f}",
            f"  Support: ${self.support_level:,.2f}",
        ]

        return "\n".join(lines)

    def get_prediction_hint(self) -> str:
        """Get a short prediction hint based on indicators"""
        bullish_signals = 0
        bearish_signals = 0

        # RSI
        if self.rsi_14 < 30:
            bullish_signals += 2  # Oversold = bullish
        elif self.rsi_14 > 70:
            bearish_signals += 2  # Overbought = bearish
        elif self.rsi_14 < 45:
            bullish_signals += 1
        elif self.rsi_14 > 55:
            bearish_signals += 1

        # MACD
        if self.macd > self.macd_signal:
            bullish_signals += 1
        else:
            bearish_signals += 1

        # Price vs MA
        if self.current_price > self.sma_15 and self.sma_15 > 0:
            bullish_signals += 1
        elif self.current_price < self.sma_15 and self.sma_15 > 0:
            bearish_signals += 1

        # Recent momentum
        if self.change_15m > 0.002:  # >0.2%
            bullish_signals += 1
        elif self.change_15m < -0.002:
            bearish_signals += 1

        # Trend
        if self.trend_short == "bullish":
            bullish_signals += 1
        elif self.trend_short == "bearish":
            bearish_signals += 1

        total = bullish_signals + bearish_signals
        if total == 0:
            return "NEUTRAL - No clear signals"

        bull_pct = bullish_signals / total
        if bull_pct > 0.65:
            return f"BULLISH ({bullish_signals}/{total} signals bullish)"
        elif bull_pct < 0.35:
            return f"BEARISH ({bearish_signals}/{total} signals bearish)"
        else:
            return f"MIXED ({bullish_signals} bullish, {bearish_signals} bearish)"


class CryptoAnalyzer:
    """
    Fetches real-time crypto price data and calculates technical indicators.
    Uses free APIs: CoinGecko, Binance public API
    """

    BINANCE_API = "https://api.binance.com/api/v3"
    COINGECKO_API = "https://api.coingecko.com/api/v3"

    # Mapping of common crypto names to symbols
    CRYPTO_SYMBOLS = {
        "bitcoin": "BTCUSDT",
        "btc": "BTCUSDT",
        "ethereum": "ETHUSDT",
        "eth": "ETHUSDT",
        "solana": "SOLUSDT",
        "sol": "SOLUSDT",
        "dogecoin": "DOGEUSDT",
        "doge": "DOGEUSDT",
        "xrp": "XRPUSDT",
        "cardano": "ADAUSDT",
        "ada": "ADAUSDT",
    }

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._price_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_ttl = 10  # seconds

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _normalize_symbol(self, text: str) -> Optional[str]:
        """Convert crypto name/symbol to Binance trading pair"""
        text_lower = text.lower().strip()

        # Direct match
        if text_lower in self.CRYPTO_SYMBOLS:
            return self.CRYPTO_SYMBOLS[text_lower]

        # Check if already a valid pair
        if text_lower.endswith("usdt"):
            return text_lower.upper()

        return None

    def detect_crypto_market(self, question: str) -> Optional[str]:
        """
        Detect if a market question is about crypto price prediction.
        Returns the crypto symbol if detected, None otherwise.
        """
        question_lower = question.lower()

        # Keywords that indicate price prediction
        price_keywords = [
            "price", "higher", "lower", "above", "below",
            "up", "down", "reach", "hit", "break", "fall",
            "rise", "drop", "pump", "dump", "moon"
        ]

        has_price_keyword = any(kw in question_lower for kw in price_keywords)

        if not has_price_keyword:
            return None

        # Check for crypto mentions
        for crypto_name, symbol in self.CRYPTO_SYMBOLS.items():
            if crypto_name in question_lower:
                return symbol

        return None

    def is_short_term_market(self, question: str, end_date: str) -> bool:
        """Check if this is a short-term market (< 24 hours)"""
        question_lower = question.lower()

        # Time indicators in question
        short_term_keywords = [
            "15 min", "15min", "15-min",
            "30 min", "30min", "30-min",
            "1 hour", "1hour", "1-hour", "one hour",
            "2 hour", "2hour", "2-hour", "two hour",
            "4 hour", "4hour", "4-hour", "four hour",
            "today", "tonight", "this afternoon",
            "by noon", "by midnight", "by end of day"
        ]

        if any(kw in question_lower for kw in short_term_keywords):
            return True

        # Check end_date if provided
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                now = datetime.utcnow()
                if end.tzinfo:
                    end = end.replace(tzinfo=None)
                hours_remaining = (end - now).total_seconds() / 3600
                return hours_remaining < 24
            except:
                pass

        return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def get_current_price(self, symbol: str = "BTCUSDT") -> float:
        """Get current price from Binance"""
        # Check cache
        if symbol in self._price_cache:
            price, cached_at = self._price_cache[symbol]
            if (datetime.utcnow() - cached_at).seconds < self._cache_ttl:
                return price

        session = await self._get_session()
        url = f"{self.BINANCE_API}/ticker/price"

        async with session.get(url, params={"symbol": symbol}) as response:
            if response.status == 200:
                data = await response.json()
                price = float(data["price"])
                self._price_cache[symbol] = (price, datetime.utcnow())
                return price
            else:
                logger.warning(f"Binance price fetch failed: {response.status}")
                return 0.0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        limit: int = 100
    ) -> List[PriceData]:
        """
        Get candlestick data from Binance.

        Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d
        """
        session = await self._get_session()
        url = f"{self.BINANCE_API}/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                candles = []
                for k in data:
                    candles.append(PriceData(
                        timestamp=datetime.fromtimestamp(k[0] / 1000),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                    ))
                return candles
            else:
                logger.warning(f"Binance klines fetch failed: {response.status}")
                return []

    def calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        return sum(prices[-period:]) / period

    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0.0

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA

        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0  # Neutral

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(
        self,
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[float, float, float]:
        """Calculate MACD, Signal line, and Histogram"""
        if len(prices) < slow:
            return 0.0, 0.0, 0.0

        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow

        # For signal line, we'd need historical MACD values
        # Simplified: use recent EMA of price differences
        signal_line = macd_line * 0.9  # Simplified approximation
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands (upper, middle, lower)"""
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return price * 1.02, price, price * 0.98

        sma = self.calculate_sma(prices, period)

        # Calculate standard deviation
        squared_diff = [(p - sma) ** 2 for p in prices[-period:]]
        std = (sum(squared_diff) / period) ** 0.5

        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        return upper, sma, lower

    def calculate_atr(self, candles: List[PriceData], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(candles) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        return sum(true_ranges[-period:]) / period

    def find_support_resistance(
        self,
        candles: List[PriceData]
    ) -> Tuple[float, float]:
        """Find recent support and resistance levels"""
        if len(candles) < 10:
            price = candles[-1].close if candles else 0
            return price * 0.98, price * 1.02

        recent = candles[-50:] if len(candles) >= 50 else candles

        highs = [c.high for c in recent]
        lows = [c.low for c in recent]

        # Simple approach: recent high/low
        resistance = max(highs)
        support = min(lows)

        return support, resistance

    def determine_trend(self, prices: List[float], period: int = 5) -> str:
        """Determine trend direction"""
        if len(prices) < period:
            return "neutral"

        recent = prices[-period:]

        # Simple linear regression slope
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n

        numerator = sum((i - x_mean) * (p - y_mean) for i, p in enumerate(recent))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "neutral"

        slope = numerator / denominator

        # Normalize by price
        slope_pct = slope / y_mean

        if slope_pct > 0.001:  # >0.1% per period
            return "bullish"
        elif slope_pct < -0.001:
            return "bearish"
        else:
            return "neutral"

    async def get_technical_indicators(
        self,
        symbol: str = "BTCUSDT"
    ) -> TechnicalIndicators:
        """
        Get comprehensive technical indicators for a crypto asset.
        """
        try:
            # Fetch different timeframe candles in parallel
            candles_1m, candles_5m, candles_15m, candles_1h = await asyncio.gather(
                self.get_klines(symbol, "1m", 100),
                self.get_klines(symbol, "5m", 50),
                self.get_klines(symbol, "15m", 50),
                self.get_klines(symbol, "1h", 50),
            )

            if not candles_1m:
                logger.warning(f"No candle data for {symbol}")
                return TechnicalIndicators(
                    symbol=symbol,
                    current_price=0,
                    timestamp=datetime.utcnow().isoformat()
                )

            current_price = candles_1m[-1].close

            # Extract close prices
            prices_1m = [c.close for c in candles_1m]
            prices_5m = [c.close for c in candles_5m]
            prices_15m = [c.close for c in candles_15m]
            prices_1h = [c.close for c in candles_1h]

            # Calculate price changes
            change_5m = (current_price - prices_1m[-5]) / prices_1m[-5] if len(prices_1m) >= 5 else 0
            change_15m = (current_price - prices_1m[-15]) / prices_1m[-15] if len(prices_1m) >= 15 else 0
            change_1h = (current_price - prices_1m[-60]) / prices_1m[-60] if len(prices_1m) >= 60 else 0
            change_4h = (current_price - prices_1h[-4]) / prices_1h[-4] if len(prices_1h) >= 4 else 0
            change_24h = (current_price - prices_1h[-24]) / prices_1h[-24] if len(prices_1h) >= 24 else 0

            # Moving averages
            sma_5 = self.calculate_sma(prices_5m, 5)
            sma_15 = self.calculate_sma(prices_15m, 15)
            sma_50 = self.calculate_sma(prices_1h, 50) if len(prices_1h) >= 50 else self.calculate_sma(prices_1h, len(prices_1h))
            ema_12 = self.calculate_ema(prices_15m, 12)
            ema_26 = self.calculate_ema(prices_15m, 26)

            # RSI
            rsi_14 = self.calculate_rsi(prices_15m, 14)

            # MACD
            macd, macd_signal, macd_hist = self.calculate_macd(prices_15m)

            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(prices_15m)

            # ATR
            atr = self.calculate_atr(candles_15m)

            # Support/Resistance
            support, resistance = self.find_support_resistance(candles_1h)

            # Trends
            trend_short = self.determine_trend(prices_5m, 5)
            trend_medium = self.determine_trend(prices_1h, 12)

            # Overall momentum
            if trend_short == "bullish" and trend_medium == "bullish":
                momentum = "bullish"
            elif trend_short == "bearish" and trend_medium == "bearish":
                momentum = "bearish"
            else:
                momentum = "neutral"

            # Volume
            volume_24h = sum(c.volume for c in candles_1h[-24:]) if len(candles_1h) >= 24 else 0

            return TechnicalIndicators(
                symbol=symbol,
                current_price=current_price,
                timestamp=datetime.utcnow().isoformat(),
                change_5m=change_5m,
                change_15m=change_15m,
                change_1h=change_1h,
                change_4h=change_4h,
                change_24h=change_24h,
                sma_5=sma_5,
                sma_15=sma_15,
                sma_50=sma_50,
                ema_12=ema_12,
                ema_26=ema_26,
                rsi_14=rsi_14,
                macd=macd,
                macd_signal=macd_signal,
                macd_histogram=macd_hist,
                bollinger_upper=bb_upper,
                bollinger_middle=bb_middle,
                bollinger_lower=bb_lower,
                atr_14=atr,
                trend_short=trend_short,
                trend_medium=trend_medium,
                momentum=momentum,
                support_level=support,
                resistance_level=resistance,
                volume_24h=volume_24h,
            )

        except Exception as e:
            logger.error(f"Error getting technical indicators for {symbol}: {e}")
            return TechnicalIndicators(
                symbol=symbol,
                current_price=0,
                timestamp=datetime.utcnow().isoformat()
            )


# Convenience function for quick price check
async def get_btc_price() -> float:
    """Quick helper to get current BTC price"""
    analyzer = CryptoAnalyzer()
    try:
        return await analyzer.get_current_price("BTCUSDT")
    finally:
        await analyzer.close()


# Test function
async def test_crypto_analyzer():
    """Test the crypto analyzer"""
    analyzer = CryptoAnalyzer()
    try:
        print("Fetching BTC technical indicators...")
        indicators = await analyzer.get_technical_indicators("BTCUSDT")
        print(indicators.get_summary())
        print()
        print(f"Prediction hint: {indicators.get_prediction_hint()}")
    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(test_crypto_analyzer())
