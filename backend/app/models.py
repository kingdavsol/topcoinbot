from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ExchangeType(str, Enum):
    BITMART = "bitmart"
    MEXC = "mexc"
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    KUCOIN = "kucoin"
    GATE_IO = "gateio"
    BINANCE_US = "binanceus"
    CRYPTO_COM = "cryptocom"
    BYBIT = "bybit"
    UPBIT = "upbit"
    OKX = "okx"
    HTX = "htx"
    HUOBI = "huobi"
    BITFINEX = "bitfinex"
    UNISWAP_V3 = "uniswap_v3"
    PANCAKESWAP_V2 = "pancakeswap_v2"
    PANCAKESWAP_V3 = "pancakeswap_v3"
    ONEINCH = "1inch"
    JUPITER_SWAP = "jupiter_swap"
    HYPERLIQUID = "hyperliquid"
    SUSHISWAP = "sushiswap"
    CURVE = "curve"
    RAYDIUM = "raydium"
    ORCA = "orca"

class WalletType(str, Enum):
    METAMASK = "metamask"
    WALLETCONNECT = "walletconnect"
    COINBASE_WALLET = "coinbase_wallet"
    TRUST_WALLET = "trust_wallet"
    TANGEM = "tangem"

class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TradingStrategy(str, Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"
    DCA = "dca"
    GRID = "grid"
    STAKING_OPTIMIZER = "staking_optimizer"

class UserRegistration(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    agreed_to_terms: bool = Field(..., description="User agreed to terms and conditions")
    agreed_to_risks: bool = Field(..., description="User acknowledged crypto trading risks")

class UserLogin(BaseModel):
    email: str
    password: str

class ExchangeCredentials(BaseModel):
    exchange_type: ExchangeType
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    uid: Optional[str] = None

class WalletConnection(BaseModel):
    wallet_type: WalletType
    wallet_address: str
    signature: str

class TradingBotConfig(BaseModel):
    user_id: int
    exchange_type: ExchangeType
    trading_pairs: List[str] = Field(default=["BTC/USDT", "ETH/USDT"])
    investment_amount: float = Field(..., ge=100, le=5000, description="Investment amount in USDC")
    stop_loss_percentage: float = Field(..., ge=1.0, le=5.0, description="Stop loss percentage")
    strategy: TradingStrategy = TradingStrategy.MOMENTUM
    timeframe: str = Field(default="1m", description="Trading timeframe: 1m, 5m, 15m, 1h, 4h, 1d")
    is_active: bool = True

class MarketData(BaseModel):
    symbol: str
    price: float
    change_24h: float
    change_7d: float
    volume_24h: float
    market_cap: Optional[float] = None
    timestamp: datetime

class Trade(BaseModel):
    id: Optional[int] = None
    user_id: int
    exchange_type: ExchangeType
    symbol: str
    side: str  # buy/sell
    amount: float
    price: float
    status: OrderStatus
    profit_loss: Optional[float] = None
    fees: Optional[float] = None
    created_at: datetime
    executed_at: Optional[datetime] = None

class ProfitShare(BaseModel):
    trade_id: int
    user_id: int
    profit_amount: float
    share_amount: float
    transaction_hash: Optional[str] = None
    status: str
    created_at: datetime

class User(BaseModel):
    id: Optional[int] = None
    email: str
    wallet_address: Optional[str] = None
    total_invested: float = 0.0
    total_profit: float = 0.0
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class TopGainers(BaseModel):
    period: str  # "24h" or "7d"
    gainers: List[Dict[str, Any]]

class BuyInOption(BaseModel):
    amount: int
    label: str
    popular: bool = False

class ComplianceWarning(BaseModel):
    title: str
    content: str
    severity: str  # "high", "medium", "low"
    required_acknowledgment: bool = True

class DCABotConfig(BaseModel):
    user_id: int
    exchange_type: ExchangeType
    symbol: str
    total_investment: float = Field(..., ge=100, description="Total investment amount")
    order_frequency: str = Field(..., description="daily, weekly, monthly")
    order_amount: float = Field(..., ge=10, description="Amount per DCA order")
    price_deviation_threshold: float = Field(default=5.0, ge=1.0, le=20.0, description="Price deviation % to trigger buy")
    is_active: bool = True

class GridBotConfig(BaseModel):
    user_id: int
    exchange_type: ExchangeType
    symbol: str
    investment_amount: float = Field(..., ge=100, description="Total grid investment")
    grid_count: int = Field(..., ge=5, le=50, description="Number of grid levels")
    price_range_low: float = Field(..., gt=0, description="Lower price range")
    price_range_high: float = Field(..., gt=0, description="Upper price range")
    profit_per_grid: float = Field(default=1.0, ge=0.1, le=10.0, description="Profit % per grid level")
    is_active: bool = True

class StakingOpportunity(BaseModel):
    platform: str
    token: str
    apy: float
    minimum_stake: float
    lock_period: str  # "flexible", "30d", "90d", "1y"
    risk_level: str  # "low", "medium", "high"
    auto_compound: bool = False

class PortfolioItem(BaseModel):
    exchange_type: ExchangeType
    symbol: str
    balance: float
    value_usd: float
    allocation_percentage: float
    profit_loss: float
    profit_loss_percentage: float

class Portfolio(BaseModel):
    user_id: int
    total_value_usd: float
    total_profit_loss: float
    total_profit_loss_percentage: float
    items: List[PortfolioItem]
    last_updated: datetime

class InfinityBotConfig(BaseModel):
    user_id: int
    exchange_type: ExchangeType
    symbol: str
    investment_amount: float = Field(..., ge=100, description="Total investment amount")
    trailing_percentage: float = Field(default=2.0, ge=0.1, le=10.0, description="Trailing stop percentage")
    take_profit_percentage: float = Field(default=5.0, ge=1.0, le=50.0, description="Take profit percentage")
    max_drawdown: float = Field(default=10.0, ge=1.0, le=20.0, description="Maximum drawdown percentage")
    is_active: bool = True

class ReferralProgram(BaseModel):
    user_id: int
    referral_code: str
    referred_users: List[int] = []
    total_earnings: float = 0.0
    commission_rate: float = 0.1  # 10% commission
    is_active: bool = True

class WalletAuthRequest(BaseModel):
    wallet_address: str
    signature: str
    message: str

class WalletLoginResponse(BaseModel):
    token: str
    user: User
    wallet_verified: bool = True

class OnboardingStep(str, Enum):
    EXCHANGE_CONNECTED = "exchange_connected"
    WALLET_CONNECTED = "wallet_connected"
    BOT_FUNDED = "bot_funded"
    SETTINGS_CONFIGURED = "settings_configured"
    BOT_LAUNCHED = "bot_launched"

class OnboardingProgress(BaseModel):
    id: Optional[int] = None
    user_id: int
    current_step: OnboardingStep = OnboardingStep.EXCHANGE_CONNECTED
    exchange_connected: bool = False
    wallet_connected: bool = False
    bot_funded: bool = False
    settings_configured: bool = False
    bot_launched: bool = False
    completion_percentage: float = 0.0
    created_at: datetime
    updated_at: datetime

class OnboardingStepUpdate(BaseModel):
    step: OnboardingStep
    completed: bool = True
