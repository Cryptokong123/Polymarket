"""
Market Sentiment Analyzer - Aggregates sentiment from multiple sources

Provides:
- Finnhub: News sentiment, market status, economic calendar
- Fear & Greed Index: Crypto market sentiment (0-100)
- Market overview for AI context

All APIs are FREE (Finnhub free tier, Fear/Greed is public)
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class MarketSentiment:
    """Aggregated market sentiment data"""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Fear & Greed Index (0-100)
    fear_greed_value: int = 50
    fear_greed_label: str = "Neutral"  # Extreme Fear, Fear, Neutral, Greed, Extreme Greed
    fear_greed_yesterday: int = 50
    fear_greed_week_ago: int = 50

    # Finnhub Market Status
    market_open: bool = True
    market_holiday: Optional[str] = None

    # News Sentiment (from Finnhub)
    news_sentiment_score: float = 0.0  # -1 to 1
    news_sentiment_label: str = "neutral"  # bullish, bearish, neutral
    recent_headlines: List[str] = field(default_factory=list)

    # Economic Events
    upcoming_events: List[Dict[str, Any]] = field(default_factory=list)

    # Overall assessment
    overall_sentiment: str = "neutral"  # bullish, bearish, neutral
    sentiment_strength: float = 0.5  # 0 to 1

    def get_summary(self) -> str:
        """Get formatted summary for LLM context"""
        lines = [
            "=== MARKET SENTIMENT OVERVIEW ===",
            "",
            f"Fear & Greed Index: {self.fear_greed_value}/100 ({self.fear_greed_label})",
            f"  Yesterday: {self.fear_greed_yesterday} | Week ago: {self.fear_greed_week_ago}",
            "",
            f"News Sentiment: {self.news_sentiment_label.upper()} (score: {self.news_sentiment_score:+.2f})",
        ]

        if self.recent_headlines:
            lines.append("")
            lines.append("Recent Headlines:")
            for headline in self.recent_headlines[:3]:
                lines.append(f"  - {headline[:80]}...")

        if self.upcoming_events:
            lines.append("")
            lines.append("Upcoming Economic Events:")
            for event in self.upcoming_events[:3]:
                lines.append(f"  - {event.get('event', 'Unknown')} ({event.get('date', '')})")

        lines.append("")
        lines.append(f"Overall Market Mood: {self.overall_sentiment.upper()}")

        return "\n".join(lines)

    def get_trading_bias(self) -> str:
        """Get a simple trading bias hint"""
        if self.fear_greed_value < 25:
            return "EXTREME FEAR - Potential buying opportunity (contrarian)"
        elif self.fear_greed_value < 40:
            return "FEAR - Market pessimistic, watch for reversals"
        elif self.fear_greed_value > 75:
            return "EXTREME GREED - Potential top, be cautious"
        elif self.fear_greed_value > 60:
            return "GREED - Market optimistic, momentum likely"
        else:
            return "NEUTRAL - No strong directional bias"


class SentimentAnalyzer:
    """
    Aggregates market sentiment from multiple free sources.

    APIs used:
    - Fear & Greed Index: https://alternative.me/crypto/fear-and-greed-index/
    - Finnhub: https://finnhub.io/ (free tier: 60 calls/minute)
    """

    FEAR_GREED_API = "https://api.alternative.me/fng/"
    FINNHUB_API = "https://finnhub.io/api/v1"

    def __init__(self, finnhub_api_key: Optional[str] = None):
        self.finnhub_api_key = finnhub_api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache:
            return False
        cached_at = self._cache.get(f"{key}_time", datetime.min)
        return (datetime.utcnow() - cached_at).seconds < self._cache_ttl

    # =========================================
    # Fear & Greed Index (FREE - No API key)
    # =========================================
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """
        Get Crypto Fear & Greed Index from alternative.me

        Returns dict with:
        - value: 0-100 (0=Extreme Fear, 100=Extreme Greed)
        - value_classification: "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
        """
        cache_key = "fear_greed"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        try:
            session = await self._get_session()
            params = {"limit": 7}  # Get last 7 days

            async with session.get(self.FEAR_GREED_API, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = {
                        "current": data["data"][0] if data.get("data") else {},
                        "yesterday": data["data"][1] if len(data.get("data", [])) > 1 else {},
                        "week_ago": data["data"][6] if len(data.get("data", [])) > 6 else {},
                    }
                    self._cache[cache_key] = result
                    self._cache[f"{cache_key}_time"] = datetime.utcnow()
                    return result
                else:
                    logger.warning(f"Fear & Greed API error: {response.status}")
                    return {}

        except Exception as e:
            logger.error(f"Fear & Greed fetch failed: {e}")
            return {}

    # =========================================
    # Finnhub APIs (FREE tier: 60 calls/min)
    # =========================================
    async def _finnhub_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make a request to Finnhub API"""
        if not self.finnhub_api_key:
            return None

        session = await self._get_session()
        params = params or {}
        params["token"] = self.finnhub_api_key

        try:
            url = f"{self.FINNHUB_API}/{endpoint}"
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    logger.warning("Finnhub rate limit hit")
                    return None
                else:
                    logger.warning(f"Finnhub API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Finnhub request failed: {e}")
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=3))
    async def get_market_news_sentiment(self, category: str = "general") -> Dict[str, Any]:
        """
        Get news sentiment from Finnhub.

        Categories: general, forex, crypto, merger
        """
        cache_key = f"finnhub_news_{category}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        data = await self._finnhub_request("news", {"category": category})

        if not data:
            return {"articles": [], "sentiment_score": 0, "sentiment_label": "neutral"}

        # Analyze sentiment from headlines
        positive_words = ["surge", "rally", "gain", "rise", "bull", "up", "high", "record", "soar", "jump"]
        negative_words = ["crash", "fall", "drop", "bear", "down", "low", "plunge", "sink", "tumble", "fear"]

        articles = data[:10] if isinstance(data, list) else []
        headlines = [a.get("headline", "") for a in articles]

        positive_count = 0
        negative_count = 0

        for headline in headlines:
            headline_lower = headline.lower()
            positive_count += sum(1 for word in positive_words if word in headline_lower)
            negative_count += sum(1 for word in negative_words if word in headline_lower)

        total = positive_count + negative_count
        if total > 0:
            sentiment_score = (positive_count - negative_count) / total
        else:
            sentiment_score = 0

        if sentiment_score > 0.2:
            sentiment_label = "bullish"
        elif sentiment_score < -0.2:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"

        result = {
            "articles": articles,
            "headlines": headlines[:5],
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
        }

        self._cache[cache_key] = result
        self._cache[f"{cache_key}_time"] = datetime.utcnow()

        return result

    async def get_economic_calendar(self) -> List[Dict[str, Any]]:
        """Get upcoming economic events from Finnhub"""
        cache_key = "economic_calendar"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Get next 7 days of events
        from_date = datetime.utcnow().strftime("%Y-%m-%d")
        to_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        data = await self._finnhub_request("calendar/economic", {
            "from": from_date,
            "to": to_date,
        })

        if not data or "economicCalendar" not in data:
            return []

        # Filter for high-impact events
        events = data.get("economicCalendar", [])
        high_impact = [
            e for e in events
            if e.get("impact") == "high" or any(
                keyword in e.get("event", "").lower()
                for keyword in ["fed", "rate", "cpi", "gdp", "employment", "inflation", "fomc"]
            )
        ]

        result = high_impact[:10]
        self._cache[cache_key] = result
        self._cache[f"{cache_key}_time"] = datetime.utcnow()

        return result

    async def get_market_status(self) -> Dict[str, Any]:
        """Get current market status (open/closed/holiday)"""
        data = await self._finnhub_request("stock/market-status", {"exchange": "US"})

        if not data:
            return {"isOpen": True, "holiday": None}

        return {
            "isOpen": data.get("isOpen", True),
            "holiday": data.get("holiday"),
        }

    # =========================================
    # Aggregated Sentiment
    # =========================================
    async def get_market_sentiment(self) -> MarketSentiment:
        """
        Get aggregated market sentiment from all sources.
        This is the main method to call.
        """
        sentiment = MarketSentiment()

        try:
            # Fetch all data concurrently
            fear_greed_task = self.get_fear_greed_index()
            news_task = self.get_market_news_sentiment("general")
            crypto_news_task = self.get_market_news_sentiment("crypto")

            # Only fetch Finnhub data if API key is set
            if self.finnhub_api_key:
                calendar_task = self.get_economic_calendar()
                market_status_task = self.get_market_status()

                results = await asyncio.gather(
                    fear_greed_task,
                    news_task,
                    crypto_news_task,
                    calendar_task,
                    market_status_task,
                    return_exceptions=True
                )

                fear_greed, news, crypto_news, calendar, market_status = results

                # Market status
                if isinstance(market_status, dict):
                    sentiment.market_open = market_status.get("isOpen", True)
                    sentiment.market_holiday = market_status.get("holiday")

                # Economic calendar
                if isinstance(calendar, list):
                    sentiment.upcoming_events = calendar
            else:
                results = await asyncio.gather(
                    fear_greed_task,
                    news_task,
                    crypto_news_task,
                    return_exceptions=True
                )
                fear_greed, news, crypto_news = results

            # Fear & Greed Index
            if isinstance(fear_greed, dict) and fear_greed.get("current"):
                current = fear_greed["current"]
                sentiment.fear_greed_value = int(current.get("value", 50))
                sentiment.fear_greed_label = current.get("value_classification", "Neutral")

                if fear_greed.get("yesterday"):
                    sentiment.fear_greed_yesterday = int(fear_greed["yesterday"].get("value", 50))
                if fear_greed.get("week_ago"):
                    sentiment.fear_greed_week_ago = int(fear_greed["week_ago"].get("value", 50))

            # News sentiment (combine general + crypto)
            if isinstance(news, dict) and isinstance(crypto_news, dict):
                combined_score = (
                    news.get("sentiment_score", 0) * 0.4 +
                    crypto_news.get("sentiment_score", 0) * 0.6
                )
                sentiment.news_sentiment_score = combined_score

                if combined_score > 0.2:
                    sentiment.news_sentiment_label = "bullish"
                elif combined_score < -0.2:
                    sentiment.news_sentiment_label = "bearish"
                else:
                    sentiment.news_sentiment_label = "neutral"

                # Combine headlines
                headlines = []
                headlines.extend(crypto_news.get("headlines", [])[:3])
                headlines.extend(news.get("headlines", [])[:2])
                sentiment.recent_headlines = headlines

            # Calculate overall sentiment
            fear_greed_normalized = (sentiment.fear_greed_value - 50) / 50  # -1 to 1
            combined = (fear_greed_normalized * 0.6) + (sentiment.news_sentiment_score * 0.4)

            if combined > 0.2:
                sentiment.overall_sentiment = "bullish"
            elif combined < -0.2:
                sentiment.overall_sentiment = "bearish"
            else:
                sentiment.overall_sentiment = "neutral"

            sentiment.sentiment_strength = min(1.0, abs(combined))

        except Exception as e:
            logger.error(f"Error aggregating sentiment: {e}")

        return sentiment

    async def get_sentiment_for_market(self, market_question: str) -> str:
        """
        Get sentiment context relevant to a specific market question.
        Returns a formatted string for LLM context.
        """
        sentiment = await self.get_market_sentiment()

        # Check if market is crypto-related
        crypto_keywords = ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "doge"]
        is_crypto = any(kw in market_question.lower() for kw in crypto_keywords)

        # Check if market is economy/fed related
        econ_keywords = ["fed", "rate", "inflation", "cpi", "gdp", "recession", "employment"]
        is_econ = any(kw in market_question.lower() for kw in econ_keywords)

        lines = [sentiment.get_summary()]

        if is_crypto:
            lines.append("")
            lines.append(f"CRYPTO TRADING BIAS: {sentiment.get_trading_bias()}")

        if is_econ and sentiment.upcoming_events:
            lines.append("")
            lines.append("Note: Check economic calendar events above for relevant data releases.")

        return "\n".join(lines)


# Convenience function
async def get_quick_sentiment() -> MarketSentiment:
    """Quick helper to get current market sentiment"""
    analyzer = SentimentAnalyzer()
    try:
        return await analyzer.get_market_sentiment()
    finally:
        await analyzer.close()


# Test function
async def test_sentiment():
    """Test the sentiment analyzer"""
    import os
    analyzer = SentimentAnalyzer(finnhub_api_key=os.getenv("FINNHUB_API_KEY"))
    try:
        print("Fetching market sentiment...")
        sentiment = await analyzer.get_market_sentiment()
        print(sentiment.get_summary())
        print()
        print(f"Trading bias: {sentiment.get_trading_bias()}")
    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(test_sentiment())
