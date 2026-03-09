import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from .database import Database
from .models import DCABotConfig, ExchangeType

class DCAService:
    def __init__(self):
        self.active_bots: Dict[int, DCABotConfig] = {}
        self.running = False
    
    def add_dca_bot(self, config: DCABotConfig) -> bool:
        """Add a new DCA bot configuration"""
        try:
            self.active_bots[config.user_id] = config
            from .database import Database
            db_svc = Database()
            db_svc.save_dca_config(config)
            return True
        except Exception as e:
            print(f"Error adding DCA bot: {e}")
            return False
    
    def remove_dca_bot(self, user_id: int) -> bool:
        """Remove DCA bot for user"""
        try:
            if user_id in self.active_bots:
                self.active_bots[user_id].is_active = False
                del self.active_bots[user_id]
                from .database import Database
                db_svc = Database()
                db_svc.update_dca_config_status(user_id, False)
            return True
        except Exception as e:
            print(f"Error removing DCA bot: {e}")
            return False
    
    async def execute_dca_order(self, config: DCABotConfig, user_credentials: Dict[str, str]) -> Dict[str, Any]:
        """Execute a single DCA order"""
        try:
            current_price = await self.get_current_price(config.exchange_type, config.symbol)
            
            if not current_price:
                return {"success": False, "error": "Could not fetch current price"}
            
            from .database import Database
            db_svc = Database()
            avg_price = db_svc.get_average_purchase_price(config.user_id, config.symbol)
            
            should_buy = True
            if avg_price and config.price_deviation_threshold > 0:
                price_deviation = abs((current_price - avg_price) / avg_price) * 100
                should_buy = price_deviation >= config.price_deviation_threshold
            
            if should_buy:
                from .main import get_exchange_service
                exchange_svc = get_exchange_service()
                order_result = await exchange_svc.place_order(
                    exchange_type=config.exchange_type,
                    api_key=user_credentials['api_key'],
                    secret=user_credentials['secret'],
                    symbol=config.symbol,
                    side='buy',
                    amount=config.order_amount / current_price,
                    passphrase=user_credentials.get('passphrase')
                )
                
                db_svc.save_dca_order(
                    user_id=config.user_id,
                    symbol=config.symbol,
                    amount=config.order_amount / current_price,
                    price=current_price,
                    order_id=order_result.get('id')
                )
                
                return {
                    "success": True,
                    "order": order_result,
                    "price": current_price,
                    "amount": config.order_amount / current_price
                }
            else:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": f"Price deviation {price_deviation:.2f}% below threshold {config.price_deviation_threshold}%"
                }
                
        except Exception as e:
            print(f"Error executing DCA order: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_current_price(self, exchange_type: ExchangeType, symbol: str):
        """Get current price for symbol"""
        try:
            from .main import get_exchange_service
            exchange_svc = get_exchange_service()
            exchange = exchange_svc.get_exchange(exchange_type)
            ticker = await exchange.fetch_ticker(symbol)
            await exchange.close()
            return ticker['last']
        except Exception as e:
            print(f"Error fetching price: {e}")
            return None
    
    def start_scheduler(self):
        """Start the DCA scheduler"""
        self.running = True
        
        while self.running:
            current_time = datetime.now()
            
            if current_time.hour == 9 and current_time.minute == 0:
                asyncio.create_task(self.run_daily_dca())
            
            if current_time.weekday() == 0 and current_time.hour == 9 and current_time.minute == 0:
                asyncio.create_task(self.run_weekly_dca())
            
            if current_time.day == 1 and current_time.hour == 9 and current_time.minute == 0:
                asyncio.create_task(self.run_monthly_dca())
            
            time.sleep(60)
    
    async def run_daily_dca(self):
        """Execute daily DCA orders"""
        for config in self.active_bots.values():
            if config.is_active and config.order_frequency == "daily":
                from .database import Database
                db_svc = Database()
                user_credentials = db_svc.get_user_exchange_credentials(config.user_id, config.exchange_type)
                if user_credentials:
                    await self.execute_dca_order(config, user_credentials)
    
    async def run_weekly_dca(self):
        """Execute weekly DCA orders"""
        for config in self.active_bots.values():
            if config.is_active and config.order_frequency == "weekly":
                from .database import Database
                db_svc = Database()
                user_credentials = db_svc.get_user_exchange_credentials(config.user_id, config.exchange_type)
                if user_credentials:
                    await self.execute_dca_order(config, user_credentials)
    
    async def run_monthly_dca(self):
        """Execute monthly DCA orders"""
        for config in self.active_bots.values():
            if config.is_active and config.order_frequency == "monthly":
                from .database import Database
                db_svc = Database()
                user_credentials = db_svc.get_user_exchange_credentials(config.user_id, config.exchange_type)
                if user_credentials:
                    await self.execute_dca_order(config, user_credentials)
    
    def stop_scheduler(self):
        """Stop the DCA scheduler"""
        self.running = False
