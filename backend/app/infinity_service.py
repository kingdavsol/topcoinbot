import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from .database import Database
from .models import InfinityBotConfig, ExchangeType

class InfinityService:
    def __init__(self):
        self.active_bots: Dict[int, Dict[str, Any]] = {}
        self.running = False
    
    def add_infinity_bot(self, config: InfinityBotConfig) -> bool:
        try:
            self.active_bots[config.user_id] = {
                "config": config,
                "status": "idle",
                "entry_price": None,
                "highest_price": None,
                "current_position": None,
                "trailing_stop_price": None,
                "last_run": None
            }
            db_svc = Database()
            db_svc.save_infinity_config(config)
            return True
        except Exception as e:
            print(f"Error adding Infinity bot: {e}")
            return False
    
    def remove_infinity_bot(self, user_id: int) -> bool:
        try:
            if user_id in self.active_bots:
                del self.active_bots[user_id]
            return True
        except Exception as e:
            print(f"Error removing Infinity bot: {e}")
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
    
    async def execute_infinity_strategy(self, user_id: int, user_credentials: Dict[str, str]):
        try:
            if user_id not in self.active_bots:
                return {"success": False, "error": "Bot not configured"}
            
            bot_state = self.active_bots[user_id]
            config: InfinityBotConfig = bot_state["config"]
            
            current_price = await self.get_current_price(config.exchange_type, config.symbol)
            if not current_price:
                return {"success": False, "error": "Could not fetch current price"}
            
            if not bot_state["current_position"]:
                order_amount = config.investment_amount / current_price
                from .main import get_exchange_service
                exchange_svc = get_exchange_service()
                
                try:
                    await exchange_svc.place_order(
                        exchange_type=config.exchange_type,
                        api_key=user_credentials['api_key'],
                        secret=user_credentials['secret'],
                        symbol=config.symbol,
                        side='buy',
                        amount=order_amount,
                        price=current_price,
                        passphrase=user_credentials.get('passphrase'),
                        dry_run=True
                    )
                    
                    bot_state["entry_price"] = current_price
                    bot_state["highest_price"] = current_price
                    bot_state["current_position"] = {"amount": order_amount, "entry_price": current_price}
                    bot_state["trailing_stop_price"] = current_price * (1 - config.trailing_percentage / 100)
                    
                except Exception as order_error:
                    return {"success": False, "error": f"Failed to place entry order: {order_error}"}
            else:
                if current_price > bot_state["highest_price"]:
                    bot_state["highest_price"] = current_price
                    bot_state["trailing_stop_price"] = current_price * (1 - config.trailing_percentage / 100)
                
                profit_percentage = ((current_price - bot_state["entry_price"]) / bot_state["entry_price"]) * 100
                
                should_exit = False
                exit_reason = ""
                
                if current_price <= bot_state["trailing_stop_price"]:
                    should_exit = True
                    exit_reason = "trailing_stop"
                elif profit_percentage >= config.take_profit_percentage:
                    should_exit = True
                    exit_reason = "take_profit"
                elif profit_percentage <= -config.max_drawdown:
                    should_exit = True
                    exit_reason = "max_drawdown"
                
                if should_exit:
                    from .main import get_exchange_service
                    exchange_svc = get_exchange_service()
                    
                    try:
                        await exchange_svc.place_order(
                            exchange_type=config.exchange_type,
                            api_key=user_credentials['api_key'],
                            secret=user_credentials['secret'],
                            symbol=config.symbol,
                            side='sell',
                            amount=bot_state["current_position"]["amount"],
                            price=current_price,
                            passphrase=user_credentials.get('passphrase'),
                            dry_run=True
                        )
                        
                        bot_state["current_position"] = None
                        bot_state["entry_price"] = None
                        bot_state["highest_price"] = None
                        bot_state["trailing_stop_price"] = None
                        
                        return {"success": True, "action": "position_closed", "reason": exit_reason, "profit_percentage": profit_percentage}
                    except Exception as order_error:
                        return {"success": False, "error": f"Failed to place exit order: {order_error}"}
            
            bot_state["last_run"] = datetime.utcnow().isoformat()
            return {"success": True, "action": "monitoring", "current_price": current_price}
            
        except Exception as e:
            print(f"Error executing infinity strategy: {e}")
            return {"success": False, "error": str(e)}
    
    def get_bot_status(self, user_id: int) -> Dict[str, Any]:
        if user_id in self.active_bots:
            bot_state = self.active_bots[user_id]
            config = bot_state["config"]
            return {
                "status": "active" if bot_state["current_position"] else "idle",
                "symbol": config.symbol,
                "investment_amount": config.investment_amount,
                "trailing_percentage": config.trailing_percentage,
                "take_profit_percentage": config.take_profit_percentage,
                "current_position": bot_state["current_position"],
                "entry_price": bot_state["entry_price"],
                "highest_price": bot_state["highest_price"],
                "trailing_stop_price": bot_state["trailing_stop_price"]
            }
        return {"status": "inactive"}
