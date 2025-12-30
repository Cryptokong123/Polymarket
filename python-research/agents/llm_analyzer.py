"""
LLM Analyzer - Uses LLMs to analyze prediction markets
Supports FREE providers (Ollama, Groq, Google) and paid (OpenAI, Anthropic)
"""

import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from .signal_types import MarketData, AnalysisResult

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """
    Analyzes prediction markets using LLMs.

    Supported providers (in order of recommendation):
    1. Ollama (FREE - runs locally, no API limits)
    2. Groq (FREE - cloud API, very fast)
    3. Google Gemini (FREE tier available)
    4. OpenAI (paid)
    5. Anthropic (paid)
    """

    def __init__(
        self,
        provider: str = "ollama",
        # Ollama settings
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1:8b",
        # Groq settings
        groq_api_key: Optional[str] = None,
        groq_model: str = "llama-3.3-70b-versatile",
        # Google settings
        google_api_key: Optional[str] = None,
        google_model: str = "gemini-1.5-flash",
        # OpenAI settings
        openai_api_key: Optional[str] = None,
        # Anthropic settings
        anthropic_api_key: Optional[str] = None,
        # General settings
        model: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.provider = provider.lower()
        self.temperature = temperature

        # Store all settings
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_model = ollama_model
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.google_api_key = google_api_key
        self.google_model = google_model
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.model = model

        # HTTP session for async requests
        self._session: Optional[aiohttp.ClientSession] = None

        # Initialize paid provider clients if needed
        self.openai_client = None
        self.anthropic_client = None

        if self.provider == "openai" and openai_api_key:
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI package not installed. Run: pip install openai")

        if self.provider == "anthropic" and anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic
                self.anthropic_client = AsyncAnthropic(api_key=anthropic_api_key)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic package not installed. Run: pip install anthropic")

        logger.info(f"LLM Analyzer initialized with provider: {self.provider}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    # =========================================
    # OLLAMA (FREE - Local)
    # =========================================
    async def _query_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query Ollama running locally - 100% FREE"""
        session = await self._get_session()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            }
        }

        try:
            async with session.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama error: {error_text}")

                data = await response.json()
                return data["message"]["content"]

        except aiohttp.ClientConnectorError:
            raise Exception(
                "Cannot connect to Ollama. Make sure it's running:\n"
                "  1. Install: curl -fsSL https://ollama.com/install.sh | sh\n"
                "  2. Pull model: ollama pull llama3.1:8b\n"
                "  3. Start server: ollama serve"
            )

    # =========================================
    # GROQ (FREE - Cloud, Very Fast)
    # =========================================
    async def _query_groq(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query Groq API - FREE tier with generous limits"""
        session = await self._get_session()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 2000,
        }

        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Groq API error: {error_text}")

            data = await response.json()
            return data["choices"][0]["message"]["content"]

    # =========================================
    # GOOGLE GEMINI (FREE Tier)
    # =========================================
    async def _query_google(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query Google Gemini API - FREE tier available"""
        session = await self._get_session()

        # Combine system prompt with user prompt for Gemini
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 2000,
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.google_model}:generateContent?key={self.google_api_key}"

        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Google Gemini API error: {error_text}")

            data = await response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    # =========================================
    # OPENAI (Paid)
    # =========================================
    async def _query_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query OpenAI API (paid)"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized. Check API key.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = self.model if self.model and "gpt" in self.model else "gpt-4-turbo"

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    # =========================================
    # ANTHROPIC (Paid)
    # =========================================
    async def _query_anthropic(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query Anthropic API (paid)"""
        if not self.anthropic_client:
            raise Exception("Anthropic client not initialized. Check API key.")

        messages = [{"role": "user", "content": prompt}]
        model = self.model if self.model and "claude" in self.model else "claude-3-5-sonnet-20241022"

        response = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt or "You are an expert prediction market analyst.",
            messages=messages,
        )
        return response.content[0].text

    # =========================================
    # Main Query Method
    # =========================================
    async def query(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Query the configured LLM provider"""
        try:
            if self.provider == "ollama":
                return await self._query_ollama(prompt, system_prompt)
            elif self.provider == "groq":
                return await self._query_groq(prompt, system_prompt)
            elif self.provider == "google":
                return await self._query_google(prompt, system_prompt)
            elif self.provider == "openai":
                return await self._query_openai(prompt, system_prompt)
            elif self.provider == "anthropic":
                return await self._query_anthropic(prompt, system_prompt)
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")

        except Exception as e:
            logger.error(f"LLM query failed ({self.provider}): {e}")
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

        # Adjust concurrency based on provider
        if self.provider == "ollama":
            max_concurrent = 1  # Ollama processes one at a time
        elif self.provider == "groq":
            max_concurrent = 3  # Groq has rate limits

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(market: MarketData) -> tuple[str, AnalysisResult]:
            async with semaphore:
                context = contexts.get(market.condition_id)
                result = await self.analyze_market(market, context)
                await asyncio.sleep(0.5)  # Rate limiting
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
