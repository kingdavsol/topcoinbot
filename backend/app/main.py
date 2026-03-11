from typing import Optional
from typing import List, Dict, Any


try:
    import pydantic.typing as _pdt
    from typing import Any as _Any, ForwardRef as _ForwardRef, cast as _cast
    def _devin_eval_fr(type_: _ForwardRef, globalns: _Any, localns: _Any) -> _Any:
        return _cast(_Any, type_)._evaluate(globalns, localns, recursive_guard=set())
    _pdt.evaluate_forwardref = _devin_eval_fr  # type: ignore[attr-defined]
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import hashlib
import secrets
import hmac
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv

from .models import (
    UserRegistration, UserLogin, ExchangeCredentials, WalletConnection,
    TradingBotConfig, ExchangeType, ComplianceWarning, BuyInOption,
    MarketData, Trade, ProfitShare, User, TopGainers, WalletType,
    OrderStatus, TradingStrategy, DCABotConfig, GridBotConfig, InfinityBotConfig, Portfolio, StakingOpportunity, ReferralProgram,
    WalletAuthRequest, WalletLoginResponse, OnboardingProgress, OnboardingStepUpdate, OnboardingStep
)
from .database import Database
from .exchange_service import ExchangeService
from .web3_service import Web3Service
from .dca_service import DCAService
from .portfolio_service import PortfolioService
from .staking_service import StakingService
from .momentum_service import MomentumService
from .coingecko_service import CoinGeckoService
from .encryption import encrypt_string, decrypt_string

print("Starting Coinpicker application...")
load_dotenv()
print(f"DATABASE_URL environment variable: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET'}")
print(f"PORT environment variable: {os.getenv('PORT', 'NOT SET')}")

db = None
exchange_service = None
web3_service = None
dca_service = None
portfolio_service = None
staking_service = None

def get_db():
    global db
    if db is None:
        db = Database()
    return db

def get_exchange_service():
    global exchange_service
    if exchange_service is None:
        exchange_service = ExchangeService()
    return exchange_service

def get_web3_service():
    global web3_service
    if web3_service is None:
        web3_service = Web3Service()
    return web3_service

def get_dca_service():
    global dca_service
    if dca_service is None:
        dca_service = DCAService()
    return dca_service

def get_portfolio_service():
    global portfolio_service
    if portfolio_service is None:
        portfolio_service = PortfolioService()
    return portfolio_service

def get_staking_service():
    global staking_service
    if staking_service is None:
        staking_service = StakingService()
    return staking_service
momentum_service = None
def get_momentum_service():
    global momentum_service
    if momentum_service is None:
        momentum_service = MomentumService()
    return momentum_service

coingecko_service = CoinGeckoService()

grid_service = None
def get_grid_service():
    global grid_service
    if grid_service is None:
        from .grid_service import GridService
        grid_service = GridService()
    return grid_service

infinity_service = None
def get_infinity_service():
    global infinity_service
    if infinity_service is None:
        from .infinity_service import InfinityService
        infinity_service = InfinityService()
    return infinity_service



app = FastAPI(
    title="Crypto Trading Bot API",
    description="Advanced crypto trading bot with exchange integration and Web3 wallet support",
    version="1.0.0"
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key")

def hash_password(password: str) -> str:
    """Hash password with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        salt, password_hash = hashed.split(':')
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() == password_hash
    except:
        return False

def create_jwt_token(user_id: int, email: str) -> str:
    """Create JWT token"""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health():
    try:
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        if db.is_postgresql:
            cursor.execute("SELECT 1")
        else:
            cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "postgresql" if db.is_postgresql else "sqlite",
            "database_url_set": bool(os.getenv("DATABASE_URL")),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "database_url_set": bool(os.getenv("DATABASE_URL")),
        }

@app.get("/api/simulation/momentum")
async def simulate_momentum_bot(
    coin_id: str = "bitcoin",
    timeframe_minutes: int = 10,
    days: int = 30
):
    """Simulate momentum bot performance with CoinGecko data"""
    try:
        result = await coingecko_service.simulate_momentum_strategy(
            coin_id=coin_id,
            timeframe_minutes=timeframe_minutes,
            days=days
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    await coingecko_service.close()

@app.get("/api/compliance/warnings")
async def get_compliance_warnings():
    """Get compliance warnings and risk disclosures"""
    warnings = [
        ComplianceWarning(
            title="High Risk Investment Warning",
            content="Cryptocurrency trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results.",
            severity="high",
            required_acknowledgment=True
        ),
        ComplianceWarning(
            title="No Guarantee of Profit",
            content="There is no guarantee that this trading bot will generate profits. You may lose some or all of your invested capital.",
            severity="high",
            required_acknowledgment=True
        ),
        ComplianceWarning(
            title="Regulatory Compliance",
            content="By using this service, you confirm that cryptocurrency trading is legal in your jurisdiction and you comply with all applicable laws.",
            severity="medium",
            required_acknowledgment=True
        ),
        ComplianceWarning(
            title="Technical Risks",
            content="Trading bots may experience technical failures, connectivity issues, or other malfunctions that could result in losses.",
            severity="medium",
            required_acknowledgment=False
        )
    ]
    return {"warnings": warnings}

@app.get("/api/market/top-gainers")
async def get_top_gainers(period: str = "24h", limit: int = 10):
    """Get top gaining cryptocurrencies"""
    try:
        exchange_svc = get_exchange_service()
        gainers = await exchange_svc.get_top_gainers(period, limit)
        return {
            "period": period,
            "gainers": gainers,
            "disclaimer": "Past performance does not guarantee future results. All investments carry risk of loss."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")

@app.get("/api/market/data")
async def get_market_data(symbols: Optional[str] = None):
    """Get current market data"""
    try:
        symbol_list = symbols.split(',') if symbols else None
        exchange_svc = get_exchange_service()
        bitmart_data = await exchange_svc.fetch_market_data(ExchangeType.BITMART, symbol_list)
        mexc_data = await exchange_svc.fetch_market_data(ExchangeType.MEXC, symbol_list)
        
        return {
            "bitmart": [data.dict() for data in bitmart_data],
            "mexc": [data.dict() for data in mexc_data],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")

@app.get("/api/trading/buy-in-options")
async def get_buy_in_options():
    """Get available buy-in amounts"""
    options = [
        BuyInOption(amount=100, label="$100 USDC", popular=False),
        BuyInOption(amount=300, label="$300 USDC", popular=True),
        BuyInOption(amount=500, label="$500 USDC", popular=True),
        BuyInOption(amount=1000, label="$1,000 USDC", popular=True),
        BuyInOption(amount=2000, label="$2,000 USDC", popular=False),
        BuyInOption(amount=5000, label="$5,000 USDC", popular=False)
    ]
    return {"options": options}

@app.post("/api/auth/register")
async def register_user(user_data: UserRegistration):
    try:
        db_svc = get_db()
        existing_user = db_svc.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        password_hash = hash_password(user_data.password)
        user_id = db_svc.create_user(
            email=user_data.email,
            password_hash=password_hash,
            full_name=(getattr(user_data, "full_name", None) or ""),
            country=(getattr(user_data, "country", None) or ""),
        )
        
        token = create_jwt_token(user_id, user_data.email)
        
        return {
            "message": "Registration successful",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user_data.email,
                "wallet_address": None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/api/auth/login")
async def login_user(login_data: UserLogin):
    try:
        db_svc = get_db()
        user = db_svc.get_user_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_jwt_token(user["id"], user["email"])
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "wallet_address": user.get("wallet_address")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/api/web3/network-info")
async def get_web3_network_info():
    """Get Web3 network information"""
    web3_svc = get_web3_service()
    return web3_svc.get_network_info()

@app.get("/api/web3/supported-wallets")
async def get_supported_wallets():
    """Get supported wallet types"""
    web3_svc = get_web3_service()
    return {"wallets": web3_svc.get_supported_wallets()}

@app.post("/api/web3/verify-wallet")
async def verify_wallet_connection(wallet_data: WalletConnection, user: Dict = Depends(verify_jwt_token)):
    """Verify wallet connection and signature"""
    try:
        message = f"Connect wallet to Crypto Trading Bot - User ID: {user['user_id']}"
        web3_svc = get_web3_service()
        is_valid = web3_svc.verify_wallet_signature(
            wallet_data.wallet_address, 
            message, 
            wallet_data.signature
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid wallet signature")
        
        usdc_balance = web3_svc.get_usdc_balance(wallet_data.wallet_address)
        eth_balance = web3_svc.get_eth_balance(wallet_data.wallet_address)
        
        return {
            "verified": True,
            "wallet_address": wallet_data.wallet_address,
            "wallet_type": wallet_data.wallet_type,
            "balances": {
                "usdc": usdc_balance,
                "eth": eth_balance
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wallet verification failed: {str(e)}")

@app.get("/api/user/profile")
async def get_user_profile(user: Dict = Depends(verify_jwt_token)):
    """Get user profile"""
    try:
        db_svc = get_db()
        user_data = db_svc.get_user_by_email(user['email'])
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        bot_configs = db_svc.get_user_bot_configs(user['user_id'])
        
        recent_trades = db_svc.get_user_trades(user['user_id'], limit=10)
        
        return {
            "user": {
                "id": user_data['id'],
                "email": user_data['email'],
                "full_name": user_data['full_name'],
                "country": user_data['country'],
                "wallet_address": user_data['wallet_address'],
                "total_invested": user_data['total_invested'],
                "total_profit": user_data['total_profit'],
                "created_at": user_data['created_at']
            },
            "bot_configs": bot_configs,
            "recent_trades": recent_trades
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")

@app.post("/api/trading/configure-bot")
async def configure_trading_bot(config: TradingBotConfig, user: Dict = Depends(verify_jwt_token)):
    """Configure trading bot"""
    try:
        config.user_id = user['user_id']
        
        db_svc = get_db()
        config_id = db_svc.save_bot_config(
            user_id=config.user_id,
            exchange_type=config.exchange_type.value,
            trading_pairs=config.trading_pairs,
            investment_amount=config.investment_amount,
            stop_loss_percentage=config.stop_loss_percentage,
            strategy=config.strategy.value
        )
        
        return {
            "message": "Trading bot configured successfully",
            "config_id": config_id,
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")

@app.post("/api/exchange/connect")
async def connect_exchange(credentials: ExchangeCredentials, user: Dict = Depends(verify_jwt_token)):
    """Connect exchange account"""
    try:
        exchange_svc = get_exchange_service()
        is_connected = await exchange_svc.check_connection(
            credentials.exchange_type,
            credentials.api_key,
            credentials.secret_key,
            credentials.passphrase
        )
        
        if not is_connected:
            raise HTTPException(status_code=400, detail="Invalid exchange credentials")
        
        encrypted_api_key = encrypt_string(credentials.api_key)
        encrypted_secret = encrypt_string(credentials.secret_key)
        encrypted_passphrase = encrypt_string(credentials.passphrase) if credentials.passphrase else None
        
        db_svc = get_db()
        db_svc.save_exchange_credentials(
            user_id=user['user_id'],
            exchange_type=credentials.exchange_type.value,
            encrypted_api_key=encrypted_api_key,
            encrypted_secret_key=encrypted_secret,
            encrypted_passphrase=encrypted_passphrase
        )
        
        return {
            "message": f"{credentials.exchange_type.value.title()} exchange connected successfully",
            "exchange": credentials.exchange_type.value
        }
    except HTTPException:
        raise
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Exchange connection failed: {str(e)}")

@app.get("/api/analytics/dashboard")
async def get_analytics_dashboard(user: Dict = Depends(verify_jwt_token)):
    """Get analytics dashboard data"""
    try:
        db_svc = get_db()
        trades = db_svc.get_user_trades(user['user_id'], limit=100)
        
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t.get('profit_loss', 0) > 0])
        total_profit = sum([t.get('profit_loss', 0) for t in trades])
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        exchange_svc = get_exchange_service()
        top_gainers_24h = await exchange_svc.get_top_gainers("24h", 5)
        top_gainers_7d = await exchange_svc.get_top_gainers("7d", 5)
        
        return {
            "trading_stats": {
                "total_trades": total_trades,
                "profitable_trades": profitable_trades,
                "total_profit": total_profit,
                "win_rate": win_rate
            },
            "market_overview": {
                "top_gainers_24h": top_gainers_24h,
                "top_gainers_7d": top_gainers_7d
            },
            "recent_trades": trades[:10]
        }
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Error fetching analytics: {str(e)}")
@app.post("/api/exchange/test")
async def test_exchange_connection(creds: ExchangeCredentials, user: Dict = Depends(verify_jwt_token)):
    try:
        exchange_svc = get_exchange_service()
        
        credentials_dict = {
            'api_key': creds.api_key,
            'secret_key': creds.secret_key,
            'passphrase': creds.passphrase,
            'uid': creds.uid
        }
        
        result = await exchange_svc.test_connection(creds.exchange_type.value, credentials_dict)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

class MomentumStart(BaseModel):
    config: TradingBotConfig
    paper_mode: bool = True

@app.post("/api/momentum/start")
async def start_momentum(payload: MomentumStart, user: Dict = Depends(verify_jwt_token)):
    svc = get_momentum_service()
    exchange_svc = get_exchange_service()
    await svc.start_bot(user["user_id"], payload.config, exchange_svc, paper_mode=payload.paper_mode)
    return {"started": True}

@app.post("/api/momentum/stop")
async def stop_momentum(user: Dict = Depends(verify_jwt_token)):
    svc = get_momentum_service()
    await svc.stop_bot(user["user_id"])
    return {"stopped": True}

@app.get("/api/momentum/status")
async def momentum_status(user: Dict = Depends(verify_jwt_token)):
    svc = get_momentum_service()
    return svc.get_status(user["user_id"])


def get_current_user(user: dict = Depends(verify_jwt_token)) -> dict:
    """Get current user from JWT token"""
    return user

@app.post("/api/dca/configure")
async def configure_dca_bot(config: DCABotConfig, current_user: dict = Depends(get_current_user)):
    config.user_id = current_user["user_id"]
    dca_svc = get_dca_service()
    success = dca_svc.add_dca_bot(config)
    return {"success": success}

@app.get("/api/portfolio")
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    portfolio_svc = get_portfolio_service()
    portfolio = await portfolio_svc.get_user_portfolio(current_user["user_id"])
    return portfolio

@app.get("/api/staking/opportunities")
async def get_staking_opportunities(period: str = "1y", risk: str = "all"):
    staking_svc = get_staking_service()
    opportunities = await staking_svc.get_top_staking_opportunities(period, risk)
    return opportunities

@app.post("/api/staking/optimize")
async def optimize_staking(request: dict, current_user: dict = Depends(get_current_user)):
    db_svc = get_db()
    user_exchanges = db_svc.get_user_exchanges(current_user["user_id"])
    available_balance = {}
    
    for exchange_config in user_exchanges:
        try:
            exchange_svc = get_exchange_service()
            balance = await exchange_svc.get_account_balance(
                exchange_config['exchange_type'],
                exchange_config['credentials']['api_key'],
                exchange_config['credentials']['secret'],
                exchange_config['credentials'].get('passphrase'),
                exchange_config['credentials'].get('uid')
            )
            for currency, amount in balance['total'].items():
                if amount > 0:
                    available_balance[currency] = available_balance.get(currency, 0) + amount
        except Exception as e:
            print(f"Error fetching balance for {exchange_config['exchange_type']}: {e}")
            continue
    
    staking_svc = get_staking_service()
    optimization = await staking_svc.optimize_staking_allocation(
        current_user["user_id"], 
        available_balance, 
        request.get('target_period', '1y')
    )
    return optimization

@app.get("/api/referral")
async def get_referral_data(current_user: dict = Depends(get_current_user)):
    db_svc = get_db()
    referral_data = db_svc.get_user_referral_data(current_user["user_id"])
    return referral_data

@app.post("/api/grid/configure")
async def configure_grid_bot(config: GridBotConfig, current_user: dict = Depends(get_current_user)):
    config.user_id = current_user["user_id"]
    grid_svc = get_grid_service()
    success = grid_svc.add_grid_bot(config)
    return {"success": success}

@app.post("/api/grid/start")
async def start_grid_bot(user: Dict = Depends(verify_jwt_token)):
    grid_svc = get_grid_service()
    user_id = user["user_id"]
    
    db_svc = get_db()
    credentials = db_svc.get_user_exchange_credentials(user_id)
    
    if not credentials:
        return {"success": False, "error": "No exchange credentials found"}
    
    if user_id in grid_svc.active_bots:
        config = grid_svc.active_bots[user_id]
        result = await grid_svc.execute_grid_orders(config, credentials[0])
        return result
    
    return {"success": False, "error": "No grid bot configured"}

@app.get("/api/grid/status")
async def grid_bot_status(user: Dict = Depends(verify_jwt_token)):
    grid_svc = get_grid_service()
    user_id = user["user_id"]
    return grid_svc.get_bot_status(user_id)

@app.post("/api/infinity/configure")
async def configure_infinity_bot(config: InfinityBotConfig, current_user: dict = Depends(get_current_user)):
    config.user_id = current_user["user_id"]
    infinity_svc = get_infinity_service()
    success = infinity_svc.add_infinity_bot(config)
    return {"success": success}

@app.post("/api/infinity/start")
async def start_infinity_bot(user: Dict = Depends(verify_jwt_token)):
    infinity_svc = get_infinity_service()
    user_id = user["user_id"]
    
    db_svc = get_db()
    credentials = db_svc.get_user_exchange_credentials(user_id)
    
    if not credentials:
        return {"success": False, "error": "No exchange credentials found"}
    
    result = await infinity_svc.execute_infinity_strategy(user_id, credentials[0])
    return result

@app.get("/api/infinity/status")
async def infinity_bot_status(user: Dict = Depends(verify_jwt_token)):
    infinity_svc = get_infinity_service()
    user_id = user["user_id"]
    return infinity_svc.get_bot_status(user_id)

@app.post("/api/auth/wallet-message")
async def get_wallet_message():
    """Get message to sign for wallet authentication"""
    import time
    timestamp = int(time.time())
    message = f"Sign this message to authenticate with Coinpicker V1.0\nTimestamp: {timestamp}"
    return {"message": message}

@app.post("/api/auth/wallet-login")
async def wallet_login(wallet_auth: WalletAuthRequest):
    try:
        web3_svc = get_web3_service()
        
        is_valid = web3_svc.verify_wallet_signature(
            wallet_auth.wallet_address,
            wallet_auth.message,
            wallet_auth.signature
        )
        
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid wallet signature")
        
        db_svc = get_db()
        user = db_svc.get_user_by_wallet_address(wallet_auth.wallet_address)
        
        if not user:
            user_id = db_svc.create_wallet_user(wallet_auth.wallet_address)
            user = db_svc.get_user_by_wallet_address(wallet_auth.wallet_address)
        
        db_svc.update_user_login(user['id'])
        
        token = create_jwt_token(user['id'], user.get('email', f"wallet-{wallet_auth.wallet_address[:8]}"))
        
        try:
            db = Database()
            progress = db.get_onboarding_progress(user['id'])
            if not progress:
                progress = {
                    "user_id": user['id'],
                    "current_step": "exchange_connected",
                    "exchange_connected": False,
                    "wallet_connected": True,
                    "bot_funded": False,
                    "settings_configured": False,
                    "bot_launched": False,
                    "completion_percentage": 20.0
                }
                db.create_onboarding_progress(progress)
            elif not progress.get("wallet_connected"):
                progress["wallet_connected"] = True
                if progress.get("current_step") == "wallet_connected":
                    progress["current_step"] = "exchange_connected"
                steps = ["exchange_connected", "wallet_connected", "bot_funded", "settings_configured", "bot_launched"]
                completed_steps = sum(1 for step in steps if progress.get(step, False))
                progress["completion_percentage"] = (completed_steps / len(steps)) * 100
                db.update_onboarding_progress(user['id'], progress)
        except Exception as e:
            print(f"Warning: Failed to update onboarding progress: {e}")
        
        return {
            "token": token,
            "user": {
                "id": user['id'],
                "email": user.get('email', f"wallet-{wallet_auth.wallet_address[:8]}@wallet.local"),
                "wallet_address": user['wallet_address'],
                "total_invested": user['total_invested'],
                "total_profit": user['total_profit']
            },
            "wallet_verified": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wallet login failed: {str(e)}")


@app.get("/api/onboarding/progress")
async def get_onboarding_progress(current_user: dict = Depends(get_current_user)):
    """Get user's onboarding progress"""
    try:
        db = Database()
        progress = db.get_onboarding_progress(current_user["id"])
        
        if not progress:
            progress = {
                "user_id": current_user["id"],
                "current_step": "exchange_connected",
                "exchange_connected": False,
                "wallet_connected": True,
                "bot_funded": False,
                "settings_configured": False,
                "bot_launched": False,
                "completion_percentage": 20.0
            }
            db.create_onboarding_progress(progress)
        
        return progress
        
    except Exception as e:
        print(f"Error getting onboarding progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to get onboarding progress")

@app.post("/api/onboarding/update")
async def update_onboarding_step(
    step_update: OnboardingStepUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update onboarding step completion"""
    try:
        db = Database()
        
        progress = db.get_onboarding_progress(current_user["id"])
        if not progress:
            raise HTTPException(status_code=404, detail="Onboarding progress not found")
        
        step_field = f"{step_update.step.value}"
        progress[step_field] = step_update.completed
        
        steps = ["exchange_connected", "wallet_connected", "bot_funded", "settings_configured", "bot_launched"]
        completed_steps = sum(1 for step in steps if progress.get(step, False))
        progress["completion_percentage"] = (completed_steps / len(steps)) * 100
        
        if step_update.completed:
            step_order = ["exchange_connected", "wallet_connected", "bot_funded", "settings_configured", "bot_launched"]
            current_index = step_order.index(step_update.step.value)
            if current_index < len(step_order) - 1:
                progress["current_step"] = step_order[current_index + 1]
        
        db.update_onboarding_progress(current_user["id"], progress)
        
        return progress
        
    except Exception as e:
        print(f"Error updating onboarding step: {e}")
        raise HTTPException(status_code=500, detail="Failed to update onboarding step")

@app.post("/api/auth/google")
async def google_auth(token_data: dict):
    """Google OAuth authentication - verify ID token"""
    try:
        id_token_str = token_data.get('token') or token_data.get('credential')
        if not id_token_str:
            raise HTTPException(status_code=400, detail="No token provided")
        
        import os
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(
            id_token_str, 
            google_requests.Request(), 
            client_id
        )
        
        email = idinfo.get('email')
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in token")
        
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute("""
                INSERT INTO users (email, password_hash, auth_method, full_name)
                VALUES (?, ?, ?, ?)
            """, (email, '', 'google', idinfo.get('name', '')))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = user[0]
        
        conn.close()
        
        token = create_jwt_token(user_id, email)
        
        return {
            "token": token,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "total_invested": 0.0,
                "total_profit": 0.0
            }
        }
        
    except ValueError as e:
        print(f"Google token verification error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        print(f"Google auth error: {e}")
        raise HTTPException(status_code=500, detail="Google authentication failed")

@app.post("/api/auth/apple")
async def apple_auth(token_data: dict):
    """Apple OAuth authentication"""
    try:
        mock_user = {
            "id": 999999,
            "email": "user@icloud.com",
            "total_invested": 0.0,
            "total_profit": 0.0
        }
        
        token = create_jwt_token(mock_user["id"], mock_user["email"])
        
        return {
            "token": token,
            "user": mock_user
        }
        
    except Exception as e:
        print(f"Apple auth error: {e}")
        raise HTTPException(status_code=500, detail="Apple authentication failed")

@app.post("/api/auth/discord")
async def discord_auth(token_data: dict):
    """Discord OAuth authentication"""
    try:
        mock_user = {
            "id": 999998,
            "email": "user@discord.com",
            "total_invested": 0.0,
            "total_profit": 0.0
        }
        
        token = create_jwt_token(mock_user["id"], mock_user["email"])
        
        return {
            "token": token,
            "user": mock_user
        }
        
    except Exception as e:
        print(f"Discord auth error: {e}")
        raise HTTPException(status_code=500, detail="Discord authentication failed")

@app.post("/api/auth/telegram")
async def telegram_auth(auth_data: dict):
    """Telegram Widget authentication with HMAC verification"""
    try:
        import os
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="Telegram bot token not configured")
        
        received_hash = auth_data.get('hash')
        if not received_hash:
            raise HTTPException(status_code=400, detail="No hash provided")
        
        check_data = []
        for key in sorted(auth_data.keys()):
            if key != 'hash':
                check_data.append(f"{key}={auth_data[key]}")
        data_check_string = '\n'.join(check_data)
        
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != received_hash:
            raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")
        
        telegram_id = auth_data.get('id')
        first_name = auth_data.get('first_name', '')
        last_name = auth_data.get('last_name', '')
        username = auth_data.get('username', '')
        
        email = f"{username}@telegram.org" if username else f"user{telegram_id}@telegram.org"
        
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            full_name = f"{first_name} {last_name}".strip()
            cursor.execute("""
                INSERT INTO users (email, password_hash, auth_method, full_name)
                VALUES (?, ?, ?, ?)
            """, (email, '', 'telegram', full_name))
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id = user[0]
        
        conn.close()
        
        token = create_jwt_token(user_id, email)
        
        return {
            "token": token,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "total_invested": 0.0,
                "total_profit": 0.0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Telegram auth error: {e}")
        raise HTTPException(status_code=500, detail="Telegram authentication failed")

@app.get("/api/bot/wallet-address")
async def get_bot_wallet_address():
    """Get the bot's wallet address for funding"""
    import os
    return {
        "address": os.getenv("BOT_WALLET_ADDRESS", "0x98F2BE0AFb97C766317734ea89EcaC1E7A0FF5d0"),
        "network": "Base",
        "currency": "USDC"
    }

@app.post("/api/bot/generate-wallet")
async def generate_bot_wallet(request: dict, current_user: dict = Depends(get_current_user)):
    """Generate a unique wallet for a user's bot"""
    try:
        from app.pricing import get_bot_fee
        
        web3_svc = get_web3_service()
        wallet_data = web3_svc.generate_bot_wallet()
        
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        bot_type = request.get('bot_type', 'momentum')
        bot_fee = get_bot_fee(bot_type)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_type TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                encrypted_private_key TEXT NOT NULL,
                bot_fee REAL NOT NULL,
                fee_paid BOOLEAN DEFAULT FALSE,
                fee_transaction_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, bot_type)
            )
        """)
        
        cursor.execute("""
            SELECT wallet_address, bot_fee FROM bot_wallets 
            WHERE user_id = ? AND bot_type = ?
        """, (current_user["user_id"], bot_type))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return {
                "address": existing[0],
                "private_key": "Already generated - check your records",
                "network": "Base",
                "currency": "USDC",
                "bot_fee": existing[1],
                "note": "Wallet already exists for this bot type"
            }
        
        cursor.execute("""
            INSERT INTO bot_wallets (user_id, bot_type, wallet_address, encrypted_private_key, bot_fee)
            VALUES (?, ?, ?, ?, ?)
        """, (current_user["user_id"], bot_type, wallet_data["address"], wallet_data["private_key"], bot_fee))
        
        conn.commit()
        conn.close()
        
        wallet_data["bot_fee"] = bot_fee
        return wallet_data
        
    except Exception as e:
        print(f"Error generating bot wallet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate wallet: {str(e)}")

@app.post("/api/bot/check-deposit")
async def check_bot_deposit(request: dict, current_user: dict = Depends(get_current_user)):
    """Check wallet balance and process fee deduction if deposit detected"""
    try:
        from app.pricing import get_bot_fee
        
        bot_type = request.get('bot_type', 'momentum')
        
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT wallet_address, encrypted_private_key, bot_fee, fee_paid, fee_transaction_hash
            FROM bot_wallets 
            WHERE user_id = ? AND bot_type = ?
        """, (current_user["user_id"], bot_type))
        
        wallet_data = cursor.fetchone()
        if not wallet_data:
            conn.close()
            raise HTTPException(status_code=404, detail="Bot wallet not found")
        
        wallet_address, private_key, bot_fee, fee_paid, fee_tx_hash = wallet_data
        
        web3_svc = get_web3_service()
        current_balance = web3_svc.get_usdc_balance(wallet_address)
        
        if fee_paid:
            conn.close()
            return {
                "success": True,
                "balance": current_balance,
                "fee_paid": True,
                "fee_amount": bot_fee,
                "transaction_hash": fee_tx_hash,
                "available_for_trading": current_balance
            }
        
        if current_balance >= bot_fee:
            result = web3_svc.transfer_bot_fee(private_key, bot_fee)
            
            if result["success"]:
                cursor.execute("""
                    UPDATE bot_wallets
                    SET fee_paid = TRUE, fee_transaction_hash = ?
                    WHERE user_id = ? AND bot_type = ?
                """, (result["transaction_hash"], current_user["user_id"], bot_type))
                conn.commit()
                
                final_balance = web3_svc.get_usdc_balance(wallet_address)
                
                conn.close()
                return {
                    "success": True,
                    "balance": final_balance,
                    "fee_paid": True,
                    "fee_amount": bot_fee,
                    "transaction_hash": result["transaction_hash"],
                    "available_for_trading": final_balance,
                    "message": f"Bot fee of ${bot_fee} successfully deducted"
                }
            else:
                conn.close()
                raise HTTPException(status_code=500, detail=f"Fee transfer failed: {result.get('error', 'Unknown error')}")
        else:
            conn.close()
            return {
                "success": True,
                "balance": current_balance,
                "fee_paid": False,
                "fee_amount": bot_fee,
                "available_for_trading": 0,
                "message": f"Waiting for deposit. Minimum: ${bot_fee} USDC"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking deposit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/configure")
async def configure_bot(config: dict, current_user: dict = Depends(get_current_user)):
    """Save bot configuration"""
    try:
        db_svc = get_db()
        bot_id = db_svc.save_bot_config(
            user_id=current_user["user_id"],
            exchange_type=config.get('exchange_type', 'bitmart'),
            trading_pairs=config.get('trading_pairs', []),
            investment_amount=config.get('investment_amount', 0),
            stop_loss_percentage=config.get('stop_loss_percentage', 2.0),
            strategy=config.get('bot_type', 'momentum')
        )
        
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE onboarding_progress 
            SET settings_configured = TRUE
            WHERE user_id = ?
        """, (current_user["user_id"],))
        conn.commit()
        conn.close()
        
        return {"success": True, "bot_id": bot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/settings")
async def get_user_settings(current_user: dict = Depends(get_current_user)):
    """Get user settings"""
    try:
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email, full_name, default_risk_level, default_stop_loss,
                   auto_restart, email_notifications, trade_alerts, 
                   profit_alerts, loss_alerts
            FROM users WHERE id = ?
        """, (current_user["user_id"],))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "email": row[0],
                "full_name": row[1] or "",
                "default_risk_level": row[2] or "moderate",
                "default_stop_loss": row[3] or 2.0,
                "auto_restart": row[4] if row[4] is not None else True,
                "email_notifications": row[5] if row[5] is not None else True,
                "trade_alerts": row[6] if row[6] is not None else True,
                "profit_alerts": row[7] if row[7] is not None else True,
                "loss_alerts": row[8] if row[8] is not None else True
            }
        
        return {"error": "User not found"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/user/settings")
async def update_user_settings(settings: dict, current_user: dict = Depends(get_current_user)):
    """Update user settings"""
    try:
        db_svc = get_db()
        conn = db_svc.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET
                full_name = ?,
                default_risk_level = ?,
                default_stop_loss = ?,
                auto_restart = ?,
                email_notifications = ?,
                trade_alerts = ?,
                profit_alerts = ?,
                loss_alerts = ?
            WHERE id = ?
        """, (
            settings.get('full_name'),
            settings.get('default_risk_level'),
            settings.get('default_stop_loss'),
            settings.get('auto_restart'),
            settings.get('email_notifications'),
            settings.get('trade_alerts'),
            settings.get('profit_alerts'),
            settings.get('loss_alerts'),
            current_user["user_id"]
        ))
        
        conn.commit()
        conn.close()
        
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
