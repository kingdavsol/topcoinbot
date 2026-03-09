import ccxt
import asyncio
import random
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .database import Database
from .models import ExchangeType, MarketData

class ExchangeService:
    def __init__(self):
        self.exchanges = {}
        self.supported_exchanges = {
            ExchangeType.BITMART: ccxt.bitmart,
            ExchangeType.MEXC: ccxt.mexc,
            ExchangeType.BINANCE: ccxt.binance,
            ExchangeType.COINBASE: ccxt.coinbase,
            ExchangeType.KRAKEN: ccxt.kraken,
            ExchangeType.KUCOIN: ccxt.kucoin,
            ExchangeType.GATE_IO: ccxt.gateio,
            ExchangeType.BINANCE_US: ccxt.binanceus,
            ExchangeType.CRYPTO_COM: ccxt.cryptocom,
            ExchangeType.BYBIT: ccxt.bybit,
            ExchangeType.UPBIT: ccxt.upbit,
            ExchangeType.OKX: ccxt.okx,
            ExchangeType.HTX: ccxt.htx
        }
        
        self.dex_aggregators = {
            'uniswap_v3': 'https://api.uniswap.org/v1',
            'pancakeswap_v2': 'https://api.pancakeswap.info/api/v2',
            'pancakeswap_v3': 'https://api.pancakeswap.info/api/v2',
            '1inch': 'https://api.1inch.dev/swap/v5.2/1',
            'jupiter_swap': 'https://quote-api.jup.ag/v6',
            'hyperliquid': 'https://api.hyperliquid.xyz',
            'sushiswap': 'https://api.sushi.com',
            'curve': 'https://api.curve.fi',
            'raydium': 'https://api.raydium.io',
            'orca': 'https://api.orca.so'
        }

    async def _with_backoff(self, fn, *args, **kwargs):
        delay = 0.5
        for _ in range(5):
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except (ccxt.RateLimitExceeded, ccxt.NetworkError) as e:
                await asyncio.sleep(delay + random.random() * 0.2)
                delay = min(delay * 2, 8.0)
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    def get_exchange(self, exchange_type: ExchangeType, api_key: Optional[str] = None, 
                    secret: Optional[str] = None, passphrase: Optional[str] = None, uid: Optional[str] = None) -> ccxt.Exchange:
        exchange_class = self.supported_exchanges.get(exchange_type)
        if not exchange_class:
            raise ValueError(f"Unsupported exchange: {exchange_type}")
        
        config: Dict[str, Any] = {
            'sandbox': False,
            'enableRateLimit': True,
        }
        
        if api_key and secret:
            config.update({
                'apiKey': api_key,
                'secret': secret,
            })
            if passphrase and exchange_type in (ExchangeType.BITMART, ExchangeType.OKX, ExchangeType.KUCOIN):
                config['password'] = passphrase
            
            # For Bitmart, CCXT requires uid parameter (should be set to memo/passphrase)
            if exchange_type == ExchangeType.BITMART:
                if uid:
                    config['uid'] = uid
                elif passphrase:
                    config['uid'] = passphrase
        
        return exchange_class(config)
    
    async def fetch_market_data(self, exchange_type: ExchangeType, symbols: Optional[List[str]] = None) -> List[MarketData]:
        exchange = None
        try:
            exchange = self.get_exchange(exchange_type)
            
            if not symbols:
                symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT', 
                          'XRP/USDT', 'DOT/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT']
            
            market_data = []
            
            for symbol in symbols:
                try:
                    ticker = await self._with_backoff(exchange.fetch_ticker, symbol)
                    ohlcv_24h = await self._with_backoff(exchange.fetch_ohlcv, symbol, '1d', None, 2)
                    ohlcv_7d = await self._with_backoff(exchange.fetch_ohlcv, symbol, '1d', None, 8)
                    
                    current_price = ticker.get('last') or 0.0
                    change_24h = 0.0
                    change_7d = 0.0
                    
                    if ohlcv_24h and len(ohlcv_24h) >= 2 and ohlcv_24h[-2][4]:
                        price_24h_ago = ohlcv_24h[-2][4]
                        if price_24h_ago:
                            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
                    
                    if ohlcv_7d and len(ohlcv_7d) >= 8 and ohlcv_7d[-8][4]:
                        price_7d_ago = ohlcv_7d[-8][4]
                        if price_7d_ago:
                            change_7d = ((current_price - price_7d_ago) / price_7d_ago) * 100
                    
                    market_data_item = MarketData(
                        symbol=symbol,
                        price=current_price,
                        change_24h=change_24h,
                        change_7d=change_7d,
                        volume_24h=(ticker.get('quoteVolume') or 0),
                        timestamp=datetime.now()
                    )
                    
                    market_data.append(market_data_item)
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    continue
            
            return market_data
            
        except Exception as e:
            print(f"Error fetching market data from {exchange_type}: {e}")
            return []
        finally:
            if exchange and hasattr(exchange, 'close'):
                try:
                    await exchange.close()
                except:
                    pass
    
    async def get_top_gainers(self, period: str = "24h", limit: int = 10) -> List[Dict[str, Any]]:
        """Get top gaining cryptocurrencies from CoinGecko API with fallback to sample data"""
        try:
            from .main import coingecko_service
            coingecko_gainers = await coingecko_service.get_top_gainers(period, limit)
            
            if coingecko_gainers and len(coingecko_gainers) > 0:
                top_gainers = []
                for data in coingecko_gainers:
                    top_gainers.append({
                        "symbol": data["symbol"],
                        "price": data["price"],
                        "change": data["change"],
                        "volume": data["volume"],
                        "potential_profit": self.calculate_potential_profit(data["change"])
                    })
                return top_gainers
            
            print(f"CoinGecko API failed, using sample data for {period}")
            
        except Exception as e:
            print(f"Error getting CoinGecko data, falling back to sample data: {e}")
        
        sample_gainers_24h = [
            {"symbol": "PEPE/USDT", "price": 0.00001234, "change": 45.67, "volume": 125000000},
            {"symbol": "SHIB/USDT", "price": 0.00002456, "change": 32.45, "volume": 89000000},
            {"symbol": "DOGE/USDT", "price": 0.08765, "change": 28.91, "volume": 156000000},
            {"symbol": "FLOKI/USDT", "price": 0.00015678, "change": 25.34, "volume": 67000000},
            {"symbol": "BONK/USDT", "price": 0.00003421, "change": 22.18, "volume": 78000000},
        ]
        
        sample_gainers_7d = [
            {"symbol": "SOL/USDT", "price": 142.56, "change": 78.23, "volume": 234000000},
            {"symbol": "AVAX/USDT", "price": 28.91, "change": 65.47, "volume": 145000000},
            {"symbol": "NEAR/USDT", "price": 4.67, "change": 58.92, "volume": 98000000},
            {"symbol": "FTM/USDT", "price": 0.45, "change": 52.34, "volume": 87000000},
            {"symbol": "MATIC/USDT", "price": 0.89, "change": 48.76, "volume": 156000000},
        ]
        
        sample_data = sample_gainers_24h if period == "24h" else sample_gainers_7d
        
        top_gainers = []
        for data in sample_data[:limit]:
            top_gainers.append({
                "symbol": data["symbol"],
                "price": data["price"],
                "change": data["change"],
                "volume": data["volume"],
                "potential_profit": self.calculate_potential_profit(data["change"])
            })
        
        return top_gainers
    
    def calculate_potential_profit(self, percentage_gain: float, investment: float = 1000) -> Dict[str, float]:
        profit = (investment * percentage_gain) / 100
        return {
            "investment": investment,
            "profit": profit,
            "total": investment + profit,
            "roi": percentage_gain
        }
    
    async def place_order(self, exchange_type: ExchangeType, api_key: str, secret: str,
                         symbol: str, side: str, amount: float, price: Optional[float] = None,
                         passphrase: Optional[str] = None, uid: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        try:
            if amount <= 0:
                raise ValueError("amount_must_be_positive")
            if dry_run:
                ts = datetime.utcnow().isoformat()
                return {
                    "id": f"paper-{int(datetime.utcnow().timestamp())}",
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "price": price,
                    "status": "filled",
                    "type": "limit" if price else "market",
                    "timestamp": ts
                }
            exchange = self.get_exchange(exchange_type, api_key, secret, passphrase, uid)
            if price:
                order = await self._with_backoff(exchange.create_limit_order, symbol, side, amount, price)
            else:
                order = await self._with_backoff(exchange.create_market_order, symbol, side, amount)
            if hasattr(exchange, 'close'):
                try:
                    await exchange.close()
                except:
                    pass
            return order
        except Exception as e:
            print(f"Error placing order: {e}")
            raise e
    
    async def get_account_balance(self, exchange_type: ExchangeType, api_key: str, 
                                secret: str, passphrase: Optional[str] = None, uid: Optional[str] = None) -> Dict[str, Any]:
        try:
            exchange = self.get_exchange(exchange_type, api_key, secret, passphrase, uid)
            balance = self._with_backoff(exchange.fetch_balance)
            if hasattr(exchange, 'close'):
                try:
                    await exchange.close()
                except:
                    pass
            return balance
        except Exception as e:
            print(f"Error fetching balance: {e}")
            raise e
    
    async def check_connection(self, exchange_type: ExchangeType, api_key: str, 
                             secret: str, passphrase: Optional[str] = None, uid: Optional[str] = None) -> bool:
        try:
            exchange = self.get_exchange(exchange_type, api_key, secret, passphrase, uid)
            self._with_backoff(exchange.fetch_balance)
            if hasattr(exchange, 'close'):
                try:
                    await exchange.close()
                except:
                    pass
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    async def test_connection(self, exchange_type: str, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Test connection to exchange with provided credentials"""
        try:
            if exchange_type in self.supported_exchanges:
                exchange_class = self.supported_exchanges[exchange_type]
                config = {
                    'apiKey': credentials.get('api_key', ''),
                    'secret': credentials.get('secret_key', ''),
                    'password': credentials.get('passphrase', ''),
                    'sandbox': False,
                    'enableRateLimit': True,
                }
                
                # For Bitmart, CCXT requires uid parameter (should be set to memo/passphrase)
                if exchange_type == 'bitmart':
                    if credentials.get('uid'):
                        config['uid'] = credentials.get('uid')
                    elif credentials.get('passphrase'):
                        config['uid'] = credentials.get('passphrase')
                
                exchange = exchange_class(config)
                
                balance = self._with_backoff(exchange.fetch_balance)
                
                if balance:
                    return {"ok": True, "message": "Connection successful"}
                else:
                    return {"ok": False, "error": "Failed to fetch account data"}
            
            elif exchange_type in self.dex_aggregators:
                import aiohttp
                api_url = self.dex_aggregators[exchange_type]
                
                async with aiohttp.ClientSession() as session:
                    if exchange_type == 'jupiter_swap':
                        test_url = f"{api_url}/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000"
                    elif exchange_type == 'hyperliquid':
                        test_url = f"{api_url}/info"
                    elif exchange_type == 'uniswap_v3':
                        test_url = f"{api_url}/tokens/ETH"
                    elif exchange_type == 'pancakeswap_v2' or exchange_type == 'pancakeswap_v3':
                        test_url = f"{api_url}/summary"
                    elif exchange_type == '1inch':
                        test_url = f"{api_url}/tokens"
                    elif exchange_type == 'sushiswap':
                        test_url = f"{api_url}/pools"
                    elif exchange_type == 'curve':
                        test_url = f"{api_url}/getPools"
                    elif exchange_type == 'raydium':
                        test_url = f"{api_url}/pairs"
                    elif exchange_type == 'orca':
                        test_url = f"{api_url}/whirlpools"
                    else:
                        test_url = f"{api_url}/swap/v1/tokens"
                    
                    if exchange_type == 'hyperliquid':
                        async with session.post(test_url, json={"type": "allMids"}) as response:
                            if response.status == 200:
                                return {"ok": True, "message": "DEX aggregator connection successful"}
                            else:
                                return {"ok": False, "error": f"DEX API returned status {response.status}"}
                    else:
                        async with session.get(test_url) as response:
                            if response.status == 200:
                                return {"ok": True, "message": "DEX aggregator connection successful"}
                            else:
                                return {"ok": False, "error": f"DEX API returned status {response.status}"}
            
            else:
                return {"ok": False, "error": f"Exchange {exchange_type} not supported"}
                
        except Exception as e:
            return {"ok": False, "error": str(e)}
