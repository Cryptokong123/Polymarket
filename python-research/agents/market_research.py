"""
Market Researcher - Fetches market data and context from various sources
Integrates with Polymarket APIs and news sources
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from .signal_types import MarketData, MarketToken

logger = logging.getLogger(__name__)


class MarketResearcher:
    """
    Fetches and processes market data from Polymarket and external sources.
    """

    def __init__(
        self,
        gamma_url: str = "https://gamma-api.polymarket.com",
        clob_url: str = "https://clob.polymarket.com",
        newsapi_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
    ):
        self.gamma_url = gamma_url.rstrip("/")
        self.clob_url = clob_url.rstrip("/")
        self.newsapi_key = newsapi_key
        self.tavily_api_key = tavily_api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_json(self, url: str, params: Optional[Dict] = None) -> Any:
        """Fetch JSON from URL with retry logic"""
        session = await self._get_session()
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_all_markets(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MarketData]:
        """
        Fetch all markets from Polymarket Gamma API.

        Args:
            active_only: Only return active markets
            limit: Maximum number of markets to return
            offset: Pagination offset

        Returns:
            List of MarketData objects
        """
        params = {
            "limit": limit,
            "offset": offset,
            "active": "true" if active_only else "false",
            "closed": "false",
        }

        try:
            url = f"{self.gamma_url}/markets"
            data = await self._fetch_json(url, params)

            markets = []
            for item in data:
                try:
                    market = self._parse_market(item)
                    if market:
                        markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def _parse_market(self, data: Dict[str, Any]) -> Optional[MarketData]:
        """Parse raw market data into MarketData object"""
        try:
            # Extract tokens
            tokens = []
            clob_rewards = data.get("clobRewards", [])

            # Parse tokens from various possible structures
            outcomes = data.get("outcomes", [])
            outcome_prices = data.get("outcomePrices", [])

            if outcomes and outcome_prices:
                for i, outcome in enumerate(outcomes):
                    price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.5
                    token_id = ""

                    # Try to get token ID from clobRewards
                    if clob_rewards and i < len(clob_rewards):
                        token_id = clob_rewards[i].get("assetAddress", "")

                    tokens.append(MarketToken(
                        token_id=token_id,
                        outcome=outcome,
                        price=price,
                    ))

            # Also check for tokens in clob_token_ids format
            if not tokens:
                clob_token_ids = data.get("clobTokenIds", [])
                for i, token_id in enumerate(clob_token_ids):
                    outcome = "Yes" if i == 0 else "No"
                    tokens.append(MarketToken(
                        token_id=token_id,
                        outcome=outcome,
                        price=0.5,  # Will be updated with order book data
                    ))

            if len(tokens) < 2:
                return None

            return MarketData(
                condition_id=data.get("conditionId", data.get("id", "")),
                question=data.get("question", ""),
                description=data.get("description", ""),
                category=data.get("category", data.get("groupItemTitle", "")),
                end_date=data.get("endDate", data.get("endDateIso", "")),
                active=data.get("active", True),
                closed=data.get("closed", False),
                tokens=tokens,
                liquidity=float(data.get("liquidity", 0)),
                volume_24h=float(data.get("volume24hr", 0)),
                volume_total=float(data.get("volume", 0)),
                created_at=data.get("createdAt"),
            )

        except Exception as e:
            logger.error(f"Failed to parse market data: {e}")
            return None

    async def get_market_by_id(self, condition_id: str) -> Optional[MarketData]:
        """Fetch a specific market by its condition ID"""
        try:
            url = f"{self.gamma_url}/markets/{condition_id}"
            data = await self._fetch_json(url)
            return self._parse_market(data)
        except Exception as e:
            logger.error(f"Failed to fetch market {condition_id}: {e}")
            return None

    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Fetch order book for a token.

        Args:
            token_id: Token ID to fetch order book for

        Returns:
            Dict with 'bids' and 'asks' lists
        """
        try:
            url = f"{self.clob_url}/book"
            params = {"token_id": token_id}
            data = await self._fetch_json(url, params)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch order book for {token_id}: {e}")
            return {"bids": [], "asks": []}

    async def get_midpoint_price(self, token_id: str) -> float:
        """Get midpoint price for a token"""
        try:
            url = f"{self.clob_url}/midpoint"
            params = {"token_id": token_id}
            data = await self._fetch_json(url, params)
            return float(data.get("mid", 0.5))
        except Exception as e:
            logger.error(f"Failed to fetch midpoint for {token_id}: {e}")
            return 0.5

    async def calculate_liquidity(self, token_id: str) -> float:
        """Calculate total liquidity from order book"""
        book = await self.get_order_book(token_id)

        total = 0.0
        for bid in book.get("bids", []):
            total += float(bid.get("size", 0)) * float(bid.get("price", 0))
        for ask in book.get("asks", []):
            total += float(ask.get("size", 0)) * float(ask.get("price", 0))

        return total

    async def enrich_market_with_prices(self, market: MarketData) -> MarketData:
        """Enrich market data with current prices from CLOB"""
        for token in market.tokens:
            if token.token_id:
                try:
                    price = await self.get_midpoint_price(token.token_id)
                    token.price = price
                except Exception as e:
                    logger.warning(f"Failed to get price for token {token.token_id}: {e}")

        return market

    async def get_tradeable_markets(
        self,
        min_liquidity: float = 1000,
        limit: int = 50,
    ) -> List[MarketData]:
        """
        Get markets that meet trading criteria.

        Args:
            min_liquidity: Minimum liquidity required
            limit: Maximum markets to return

        Returns:
            List of tradeable markets sorted by liquidity
        """
        all_markets = await self.get_all_markets(active_only=True, limit=200)

        # Filter by liquidity
        tradeable = [m for m in all_markets if m.liquidity >= min_liquidity]

        # Sort by liquidity descending
        tradeable.sort(key=lambda m: m.liquidity, reverse=True)

        # Limit results
        tradeable = tradeable[:limit]

        # Enrich with current prices
        enriched = []
        for market in tradeable:
            try:
                enriched.append(await self.enrich_market_with_prices(market))
            except Exception as e:
                logger.warning(f"Failed to enrich market: {e}")
                enriched.append(market)

        return enriched

    async def search_news(self, query: str, days_back: int = 7) -> List[Dict[str, Any]]:
        """
        Search for relevant news articles.

        Args:
            query: Search query
            days_back: How many days back to search

        Returns:
            List of news articles
        """
        articles = []

        # Try NewsAPI if configured
        if self.newsapi_key:
            try:
                from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                session = await self._get_session()

                async with session.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "from": from_date,
                        "sortBy": "relevancy",
                        "pageSize": 10,
                        "apiKey": self.newsapi_key,
                    },
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for article in data.get("articles", []):
                            articles.append({
                                "title": article.get("title", ""),
                                "description": article.get("description", ""),
                                "source": article.get("source", {}).get("name", ""),
                                "published": article.get("publishedAt", ""),
                                "url": article.get("url", ""),
                            })
            except Exception as e:
                logger.warning(f"NewsAPI search failed: {e}")

        # Try Tavily if configured
        if self.tavily_api_key:
            try:
                session = await self._get_session()
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 10,
                    },
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for result in data.get("results", []):
                            articles.append({
                                "title": result.get("title", ""),
                                "description": result.get("content", ""),
                                "source": result.get("url", "").split("/")[2] if result.get("url") else "",
                                "published": "",
                                "url": result.get("url", ""),
                            })
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        return articles

    async def get_context_for_market(self, market: MarketData) -> str:
        """
        Get relevant context for a market from news sources.

        Args:
            market: Market to get context for

        Returns:
            Formatted context string
        """
        # Extract key terms from question for search
        question = market.question

        # Search for news
        articles = await self.search_news(question, days_back=14)

        if not articles:
            return ""

        # Format context
        context_parts = []
        for article in articles[:5]:  # Limit to 5 most relevant
            context_parts.append(
                f"**{article['title']}** ({article['source']})\n{article['description']}"
            )

        return "\n\n".join(context_parts)

    async def get_market_history(
        self,
        condition_id: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Get price history for a market.

        Note: This is a placeholder - actual implementation depends on
        available historical data APIs.
        """
        # TODO: Implement with actual historical data source
        return []
