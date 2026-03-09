import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from .models import Portfolio, PortfolioItem, ExchangeType

class PortfolioService:
    def __init__(self):
        self.cache_duration = 300  # 5 minutes cache
        self.portfolio_cache: Dict[int, Dict] = {}
    
    async def get_user_portfolio(self, user_id: int) -> Portfolio:
        """Get comprehensive portfolio for user across all exchanges"""
        try:
            cache_key = f"portfolio_{user_id}"
            now = datetime.now()
            
            if cache_key in self.portfolio_cache:
                cached_data = self.portfolio_cache[cache_key]
                if (now - cached_data['timestamp']).seconds < self.cache_duration:
                    return cached_data['portfolio']
            
            from .main import get_db
            db_svc = get_db()
            user_exchanges = db_svc.get_user_exchanges(user_id)
            portfolio_items = []
            total_value = 0.0
            total_profit_loss = 0.0
            
            for exchange_config in user_exchanges:
                exchange_portfolio = await self.get_exchange_portfolio(
                    user_id, 
                    exchange_config['exchange_type'],
                    exchange_config['credentials']
                )
                portfolio_items.extend(exchange_portfolio['items'])
                total_value += exchange_portfolio['total_value']
                total_profit_loss += exchange_portfolio['profit_loss']
            
            total_profit_loss_percentage = (total_profit_loss / total_value * 100) if total_value > 0 else 0.0
            
            for item in portfolio_items:
                item.allocation_percentage = (item.value_usd / total_value * 100) if total_value > 0 else 0.0
            
            portfolio = Portfolio(
                user_id=user_id,
                total_value_usd=total_value,
                total_profit_loss=total_profit_loss,
                total_profit_loss_percentage=total_profit_loss_percentage,
                items=portfolio_items,
                last_updated=now
            )
            
            self.portfolio_cache[cache_key] = {
                'portfolio': portfolio,
                'timestamp': now
            }
            
            return portfolio
            
        except Exception as e:
            print(f"Error getting user portfolio: {e}")
            return Portfolio(
                user_id=user_id,
                total_value_usd=0.0,
                total_profit_loss=0.0,
                total_profit_loss_percentage=0.0,
                items=[],
                last_updated=datetime.now()
            )
    
    async def get_exchange_portfolio(self, user_id: int, exchange_type: ExchangeType, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Get portfolio for specific exchange"""
        try:
            from .main import get_exchange_service
            exchange_svc = get_exchange_service()
            balance = await exchange_svc.get_account_balance(
                exchange_type=exchange_type,
                api_key=credentials['api_key'],
                secret=credentials['secret'],
                passphrase=credentials.get('passphrase')
            )
            
            portfolio_items = []
            total_value = 0.0
            total_profit_loss = 0.0
            
            for currency, balance_info in balance['total'].items():
                if balance_info > 0:
                    symbol = f"{currency}/USDT"
                    current_price = await self.get_current_price(exchange_type, symbol)
                    
                    if current_price:
                        value_usd = balance_info * current_price
                        
                        from .main import get_db
                        db_svc = get_db()
                        avg_purchase_price = db_svc.get_average_purchase_price(user_id, symbol)
                        profit_loss = 0.0
                        profit_loss_percentage = 0.0
                        
                        if avg_purchase_price:
                            profit_loss = (current_price - avg_purchase_price) * balance_info
                            profit_loss_percentage = ((current_price - avg_purchase_price) / avg_purchase_price) * 100
                        
                        portfolio_item = PortfolioItem(
                            exchange_type=exchange_type,
                            symbol=symbol,
                            balance=balance_info,
                            value_usd=value_usd,
                            allocation_percentage=0.0,  # Will be calculated later
                            profit_loss=profit_loss,
                            profit_loss_percentage=profit_loss_percentage
                        )
                        
                        portfolio_items.append(portfolio_item)
                        total_value += value_usd
                        total_profit_loss += profit_loss
            
            return {
                'items': portfolio_items,
                'total_value': total_value,
                'profit_loss': total_profit_loss
            }
            
        except Exception as e:
            print(f"Error getting exchange portfolio: {e}")
            return {'items': [], 'total_value': 0.0, 'profit_loss': 0.0}
    
    async def get_current_price(self, exchange_type: ExchangeType, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            from .main import get_exchange_service
            exchange_svc = get_exchange_service()
            exchange = exchange_svc.get_exchange(exchange_type)
            ticker = await exchange.fetch_ticker(symbol)
            await exchange.close()
            return ticker['last']
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def get_portfolio_performance(self, user_id: int, period: str = "24h") -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        try:
            current_portfolio = await self.get_user_portfolio(user_id)
            from .main import get_db
            db_svc = get_db()
            historical_value = db_svc.get_historical_portfolio_value(user_id, period)
            
            if historical_value:
                value_change = current_portfolio.total_value_usd - historical_value
                percentage_change = (value_change / historical_value * 100) if historical_value > 0 else 0.0
            else:
                value_change = 0.0
                percentage_change = 0.0
            
            return {
                'current_value': current_portfolio.total_value_usd,
                'value_change': value_change,
                'percentage_change': percentage_change,
                'period': period,
                'profit_loss': current_portfolio.total_profit_loss,
                'profit_loss_percentage': current_portfolio.total_profit_loss_percentage
            }
            
        except Exception as e:
            print(f"Error getting portfolio performance: {e}")
            return {
                'current_value': 0.0,
                'value_change': 0.0,
                'percentage_change': 0.0,
                'period': period,
                'profit_loss': 0.0,
                'profit_loss_percentage': 0.0
            }
