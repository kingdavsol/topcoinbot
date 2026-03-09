import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from .database import Database
from .models import GridBotConfig, ExchangeType

class GridService:
    def __init__(self):
        self.active_bots: Dict[int, GridBotConfig] = {}
        self.running = False
    
    def add_grid_bot(self, config: GridBotConfig) -> bool:
        try:
            self.active_bots[config.user_id] = config
            db_svc = Database()
            db_svc.save_grid_config(config)
            return True
        except Exception as e:
            print(f"Error adding Grid bot: {e}")
            return False
    
    def remove_grid_bot(self, user_id: int) -> bool:
        try:
            if user_id in self.active_bots:
                del self.active_bots[user_id]
            return True
        except Exception as e:
            print(f"Error removing Grid bot: {e}")
            return False
    
    async def get_current_price(self, exchange_type: ExchangeType, symbol: str) -> Optional[float]:
        try:
            from .main import get_exchange_service
            exchange_svc = get_exchange_service()
            data = await exchange_svc.fetch_market_data(exchange_type, [symbol])
            if data and len(data) > 0:
                return data[0].price
            return None
        except Exception as e:
            print(f"Error fetching current price: {e}")
            return None
    
    async def execute_grid_orders(self, config: GridBotConfig, user_credentials: Dict[str, str]):
        try:
            current_price = await self.get_current_price(config.exchange_type, config.symbol)
            if not current_price:
                return {"success": False, "error": "Could not fetch current price"}
            
            price_range = config.price_range_high - config.price_range_low
            grid_step = price_range / config.grid_count
            
            from .main import get_exchange_service
            exchange_svc = get_exchange_service()
            
            orders_placed = 0
            for i in range(config.grid_count):
                buy_price = config.price_range_low + (i * grid_step)
                sell_price = buy_price * (1 + config.profit_per_grid / 100)
                
                if current_price > buy_price:
                    order_amount = config.investment_amount / config.grid_count / buy_price
                    try:
                        if order_amount <= 0:
                            continue
                        await exchange_svc.place_order(
                            exchange_type=config.exchange_type,
                            api_key=user_credentials['api_key'],
                            secret=user_credentials['secret'],
                            symbol=config.symbol,
                            side='buy',
                            amount=order_amount,
                            price=buy_price,
                            passphrase=user_credentials.get('passphrase'),
                            dry_run=True
                        )
                        orders_placed += 1
                    except Exception as order_error:
                        print(f"Error placing grid order: {order_error}")
            
            return {"success": True, "orders_placed": orders_placed}
        except Exception as e:
            print(f"Error executing grid orders: {e}")
            return {"success": False, "error": str(e)}
    
    def get_bot_status(self, user_id: int) -> Dict[str, Any]:
        if user_id in self.active_bots:
            config = self.active_bots[user_id]
            return {
                "status": "active",
                "symbol": config.symbol,
                "grid_count": config.grid_count,
                "investment_amount": config.investment_amount,
                "price_range": f"{config.price_range_low} - {config.price_range_high}",
                "profit_per_grid": config.profit_per_grid
            }
        return {"status": "inactive"}
