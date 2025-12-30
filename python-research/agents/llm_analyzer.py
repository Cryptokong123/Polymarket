"""
LLM Analyzer - Uses LLMs to analyze prediction markets
Supports both OpenAI and Anthropic models
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from .signal_types import MarketData, AnalysisResult

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """
    Analyzes prediction markets using LLMs.
    Supports OpenAI and Anthropic models.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.3,
    ):
        self.model = model
        self.temperature = temperature
        self.openai_client = None
        self.anthropic_client = None

        # Initialize OpenAI client if key provided
        if openai_api_key:
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI package not installed")

        # Initialize Anthropic client if key provided
        if anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic
                self.anthropic_client = AsyncAnthropic(api_key=anthropic_api_key)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic package not installed")

        if not self.openai_client and not self.anthropic_client:
            raise ValueError("At least one LLM API key must be provided")

    def _get_provider(self) -> str:
        """Determine which provider to use based on model name"""
        if "claude" in self.model.lower() or "anthropic" in self.model.lower():
            if self.anthropic_client:
                return "anthropic"
            elif self.openai_client:
                logger.warning(f"Anthropic model requested but no Anthropic client, falling back to OpenAI")
                return "openai"
        return "openai" if self.openai_client else "anthropic"

    async def _query_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query OpenAI API"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.openai_client.chat.completions.create(
            model=self.model if "gpt" in self.model else "gpt-4-turbo",
            messages=messages,
            temperature=self.temperature,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    async def _query_anthropic(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query Anthropic API"""
        messages = [{"role": "user", "content": prompt}]

        response = await self.anthropic_client.messages.create(
            model=self.model if "claude" in self.model else "claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt or "You are an expert prediction market analyst.",
            messages=messages,
        )
        return response.content[0].text

    async def query(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query the configured LLM"""
        provider = self._get_provider()

        try:
            if provider == "openai":
                return await self._query_openai(prompt, system_prompt)
            else:
                return await self._query_anthropic(prompt, system_prompt)
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise

    def _build_analysis_prompt(
        self,
        market: MarketData,
        context: Optional[str] = None,
    ) -> str:
        """Build the market analysis prompt"""

        yes_token = market.yes_token
        no_token = market.no_token

        yes_price = yes_token.price if yes_token else 0.5
        no_price = no_token.price if no_token else 0.5

        prompt = f"""You are an expert prediction market analyst. Analyze the following market and provide your probability estimate.

## MARKET INFORMATION

**Question:** {market.question}

**Description:** {market.description}

**Category:** {market.category}

**End Date:** {market.end_date}

**Current Prices:**
- YES: ${yes_price:.4f} ({yes_price*100:.1f}% implied probability)
- NO: ${no_price:.4f} ({no_price*100:.1f}% implied probability)

**Market Metrics:**
- Liquidity: ${market.liquidity:,.2f}
- 24h Volume: ${market.volume_24h:,.2f}
"""

        if context:
            prompt += f"""
## RELEVANT CONTEXT/NEWS

{context}
"""

        prompt += """
## YOUR TASK

Based on your analysis of the market question, current prices, and any available context:

1. Estimate the TRUE probability that YES wins (0.0 to 1.0)
2. Rate your confidence level (0.0 to 1.0)
3. Provide brief reasoning (2-3 sentences)
4. List 2-3 key factors influencing your estimate
5. Identify any risk factors or uncertainties

## IMPORTANT GUIDELINES

- Be objective and data-driven
- Consider base rates and historical precedents
- Account for time remaining until resolution
- Don't be anchored to current market prices
- If you're uncertain, reflect that in a lower confidence score

## RESPONSE FORMAT

Respond ONLY with valid JSON in this exact format:
```json
{
    "probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Your 2-3 sentence analysis...",
    "key_factors": ["factor 1", "factor 2", "factor 3"],
    "sentiment": "bullish|bearish|neutral",
    "risk_factors": ["risk 1", "risk 2"]
}
```
"""
        return prompt

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured data"""
        # Try to extract JSON from the response
        try:
            # Look for JSON block
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                # Try to find JSON object directly
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                else:
                    json_str = response

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            # Return default values
            return {
                "probability": 0.5,
                "confidence": 0.3,
                "reasoning": "Failed to parse LLM response",
                "key_factors": [],
                "sentiment": "neutral",
                "risk_factors": ["parsing_error"],
            }

    async def analyze_market(
        self,
        market: MarketData,
        context: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Analyze a prediction market and return probability estimates.

        Args:
            market: Market data to analyze
            context: Optional context from RAG (news, data, etc.)

        Returns:
            AnalysisResult with probability estimates and reasoning
        """
        system_prompt = """You are an expert prediction market analyst with deep knowledge of:
- Political forecasting and polling analysis
- Economic indicators and financial markets
- Sports analytics and statistics
- Technology trends and industry dynamics
- Geopolitical events and international relations

You provide accurate, well-calibrated probability estimates based on available evidence.
You acknowledge uncertainty and adjust confidence levels accordingly.
You are not anchored to current market prices and form independent judgments."""

        prompt = self._build_analysis_prompt(market, context)

        try:
            response = await self.query(prompt, system_prompt)
            parsed = self._parse_analysis_response(response)

            return AnalysisResult(
                predicted_probability=float(parsed.get("probability", 0.5)),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=parsed.get("reasoning", "No reasoning provided"),
                key_factors=parsed.get("key_factors", []),
                news_summary=context[:500] if context else None,
                sentiment=parsed.get("sentiment", "neutral"),
                risk_factors=parsed.get("risk_factors", []),
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            return AnalysisResult(
                predicted_probability=0.5,
                confidence=0.1,
                reasoning=f"Analysis failed: {str(e)}",
                risk_factors=["analysis_failed"],
            )

    async def analyze_multiple(
        self,
        markets: List[MarketData],
        contexts: Optional[Dict[str, str]] = None,
        max_concurrent: int = 5,
    ) -> Dict[str, AnalysisResult]:
        """
        Analyze multiple markets concurrently.

        Args:
            markets: List of markets to analyze
            contexts: Optional dict mapping market_id to context
            max_concurrent: Maximum concurrent LLM calls

        Returns:
            Dict mapping market_id to AnalysisResult
        """
        contexts = contexts or {}
        results = {}

        # Process in batches to avoid rate limits
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(market: MarketData) -> tuple[str, AnalysisResult]:
            async with semaphore:
                context = contexts.get(market.condition_id)
                result = await self.analyze_market(market, context)
                # Add small delay to avoid rate limits
                await asyncio.sleep(0.5)
                return market.condition_id, result

        tasks = [analyze_with_semaphore(m) for m in markets]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                logger.error(f"Analysis failed: {item}")
            else:
                market_id, result = item
                results[market_id] = result

        return results
