"""
Signal Types - Data structures for trading signals and market data
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import uuid


class Side(str, Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class TokenType(str, Enum):
    """Token type in binary market"""
    YES = "YES"
    NO = "NO"


class SignalStatus(str, Enum):
    """Signal processing status"""
    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class MarketToken:
    """Token within a market"""
    token_id: str
    outcome: str  # "Yes" or "No"
    price: float
    winner: Optional[bool] = None


@dataclass
class MarketData:
    """Market information from Polymarket"""
    condition_id: str
    question: str
    description: str
    category: str
    end_date: str
    active: bool
    closed: bool
    tokens: List[MarketToken]
    liquidity: float = 0.0
    volume_24h: float = 0.0
    volume_total: float = 0.0
    created_at: Optional[str] = None

    @property
    def yes_token(self) -> Optional[MarketToken]:
        """Get YES token"""
        for token in self.tokens:
            if token.outcome.upper() == "YES":
                return token
        return None

    @property
    def no_token(self) -> Optional[MarketToken]:
        """Get NO token"""
        for token in self.tokens:
            if token.outcome.upper() == "NO":
                return token
        return None

    @property
    def implied_probability(self) -> float:
        """Get implied probability from YES price"""
        yes = self.yes_token
        return yes.price if yes else 0.5


@dataclass
class AnalysisResult:
    """Result from LLM market analysis"""
    predicted_probability: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasoning: str
    key_factors: List[str] = field(default_factory=list)
    news_summary: Optional[str] = None
    sentiment: Optional[str] = None  # "bullish", "bearish", "neutral"
    risk_factors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TradingSignal:
    """Trading signal to be consumed by the executor"""
    # Identification
    signal_id: str = field(default_factory=lambda: f"sig_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Market info
    market_id: str = ""
    token_id: str = ""
    market_question: str = ""

    # Trade parameters
    side: str = "BUY"  # "BUY" or "SELL"
    token_type: str = "YES"  # "YES" or "NO"
    current_price: float = 0.0
    predicted_probability: float = 0.0
    expected_value: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""

    # Execution parameters
    suggested_size: float = 0.0  # Size in USDC
    max_price: float = 0.0  # Don't buy above this
    min_price: float = 0.0  # Don't sell below this

    # Timing
    expires_at: str = field(default_factory=lambda: (datetime.utcnow() + timedelta(hours=24)).isoformat())

    # Status
    status: str = "pending"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingSignal":
        """Create signal from dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "TradingSignal":
        """Create signal from JSON string"""
        return cls.from_dict(json.loads(json_str))

    def is_valid(self) -> bool:
        """Check if signal is still valid"""
        if self.status != "pending":
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            return datetime.utcnow() < expires.replace(tzinfo=None)
        except:
            return False

    def calculate_ev(self, current_price: float) -> float:
        """Recalculate expected value with current price"""
        if self.side == "BUY":
            # EV = (prob_win * profit) - (prob_lose * cost)
            # profit = 1 - price, cost = price
            return (self.predicted_probability * (1 - current_price)) - ((1 - self.predicted_probability) * current_price)
        else:
            # For SELL, opposite calculation
            return ((1 - self.predicted_probability) * current_price) - (self.predicted_probability * (1 - current_price))


@dataclass
class ExecutionResult:
    """Result of executing a trading signal"""
    signal_id: str
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    filled_size: Optional[float] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    gas_used: Optional[float] = None
    transaction_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class Position:
    """Current position in a market"""
    market_id: str
    token_id: str
    token_type: str  # "YES" or "NO"
    size: float  # Number of tokens
    entry_price: float
    current_price: float
    unrealized_pnl: float
    entry_time: str
    signal_id: str

    @property
    def value(self) -> float:
        """Current position value"""
        return self.size * self.current_price

    @property
    def cost_basis(self) -> float:
        """Original cost"""
        return self.size * self.entry_price


@dataclass
class PortfolioState:
    """Current portfolio state"""
    positions: List[Position] = field(default_factory=list)
    total_value: float = 0.0
    available_balance: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def position_count(self) -> int:
        """Number of open positions"""
        return len(self.positions)
