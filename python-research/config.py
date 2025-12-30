"""
Configuration management for the Polymarket Trading Bot
Loads settings from environment variables with sensible defaults
"""

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")


@dataclass
class WalletConfig:
    """Wallet and authentication configuration"""
    private_key: str = field(default_factory=lambda: os.getenv("POLYGON_WALLET_PRIVATE_KEY", ""))
    address: str = field(default_factory=lambda: os.getenv("WALLET_ADDRESS", ""))

    def validate(self) -> bool:
        """Check if wallet is configured"""
        return bool(self.private_key and self.address)


@dataclass
class PolymarketConfig:
    """Polymarket API configuration"""
    clob_url: str = field(default_factory=lambda: os.getenv("CLOB_API_URL", "https://clob.polymarket.com"))
    gamma_url: str = field(default_factory=lambda: os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com"))
    api_key: str = field(default_factory=lambda: os.getenv("CLOB_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("CLOB_API_SECRET", ""))
    api_passphrase: str = field(default_factory=lambda: os.getenv("CLOB_API_PASSPHRASE", ""))
    chain_id: int = 137  # Polygon mainnet


@dataclass
class LLMConfig:
    """LLM configuration for market analysis - supports free and paid providers"""
    # Provider selection
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama"))

    # Ollama (FREE - Local)
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b"))

    # Groq (FREE - Cloud)
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))

    # Google Gemini (FREE tier)
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    google_model: str = field(default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"))

    # Paid options
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))

    def get_provider(self) -> str:
        """Get the configured LLM provider"""
        return self.provider.lower()

    def validate(self) -> bool:
        """Check if the selected provider is properly configured"""
        provider = self.get_provider()

        if provider == "ollama":
            # Ollama just needs the URL (running locally)
            return bool(self.ollama_base_url)
        elif provider == "groq":
            return bool(self.groq_api_key)
        elif provider == "google":
            return bool(self.google_api_key)
        elif provider == "openai":
            return bool(self.openai_api_key)
        elif provider == "anthropic":
            return bool(self.anthropic_api_key)

        # Fallback: check if any provider is configured
        return bool(
            self.ollama_base_url or
            self.groq_api_key or
            self.google_api_key or
            self.openai_api_key or
            self.anthropic_api_key
        )


@dataclass
class TradingConfig:
    """Trading parameters and risk management"""
    max_position_size: float = field(default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE", "100")))
    min_expected_value: float = field(default_factory=lambda: float(os.getenv("MIN_EXPECTED_VALUE", "0.05")))
    max_positions: int = field(default_factory=lambda: int(os.getenv("MAX_POSITIONS", "10")))
    min_liquidity: float = field(default_factory=lambda: float(os.getenv("MIN_LIQUIDITY", "1000")))
    max_slippage: float = field(default_factory=lambda: float(os.getenv("MAX_SLIPPAGE", "0.02")))
    max_daily_loss: float = field(default_factory=lambda: float(os.getenv("MAX_DAILY_LOSS", "500")))
    min_trade_interval: int = field(default_factory=lambda: int(os.getenv("MIN_TRADE_INTERVAL", "60")))
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "false").lower() == "true")

    # New market edge settings
    prioritize_new_markets: bool = field(default_factory=lambda: os.getenv("PRIORITIZE_NEW_MARKETS", "true").lower() == "true")
    new_market_hours: int = field(default_factory=lambda: int(os.getenv("NEW_MARKET_HOURS", "48")))  # Markets < 48 hours old
    new_market_ev_bonus: float = field(default_factory=lambda: float(os.getenv("NEW_MARKET_EV_BONUS", "0.02")))  # +2% EV bonus


@dataclass
class ResearchConfig:
    """Research and analysis parameters"""
    news_sources: List[str] = field(default_factory=lambda: os.getenv("NEWS_SOURCES", "polymarket,twitter,newsapi").split(","))
    scan_interval: int = field(default_factory=lambda: int(os.getenv("SCAN_INTERVAL", "300")))
    chroma_db_path: str = field(default_factory=lambda: os.getenv("CHROMA_DB_PATH", "./data/chroma"))
    max_markets_per_scan: int = field(default_factory=lambda: int(os.getenv("MAX_MARKETS_PER_SCAN", "50")))
    newsapi_key: str = field(default_factory=lambda: os.getenv("NEWSAPI_KEY", ""))
    twitter_bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))


@dataclass
class TelegramConfig:
    """Telegram notification configuration"""
    bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    enabled: bool = field(default_factory=lambda: os.getenv("TELEGRAM_ENABLED", "false").lower() == "true")

    def validate(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.chat_id) if self.enabled else True


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:./data/trades.db"))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "./data/bot.log"))


@dataclass
class Config:
    """Main configuration container"""
    wallet: WalletConfig = field(default_factory=WalletConfig)
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Shared paths
    signals_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "shared" / "signals")
    executed_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "shared" / "executed")
    results_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "shared" / "results")

    def __post_init__(self):
        """Create required directories"""
        for dir_path in [self.signals_dir, self.executed_dir, self.results_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def validate(self) -> tuple[bool, list[str]]:
        """Validate all required configuration"""
        errors = []

        if not self.wallet.validate():
            errors.append("Wallet configuration missing (POLYGON_WALLET_PRIVATE_KEY, WALLET_ADDRESS)")

        if not self.llm.validate():
            provider = self.llm.get_provider()
            if provider == "ollama":
                errors.append("Ollama not configured. Install with: curl -fsSL https://ollama.com/install.sh | sh")
            elif provider == "groq":
                errors.append("GROQ_API_KEY missing. Get free key at: https://console.groq.com/keys")
            elif provider == "google":
                errors.append("GOOGLE_API_KEY missing. Get free key at: https://aistudio.google.com/apikey")
            else:
                errors.append(f"LLM provider '{provider}' not configured properly")

        if not self.telegram.validate():
            errors.append("Telegram enabled but not properly configured")

        return len(errors) == 0, errors


# Global config instance
config = Config()
