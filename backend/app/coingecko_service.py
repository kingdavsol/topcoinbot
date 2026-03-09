import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CoinGeckoService:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = None
    
    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_top_gainers(self, period: str = "24h", limit: int = 10) -> Optional[List[Dict]]:
        """Get top gaining cryptocurrencies from CoinGecko API"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,7d"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if period == "24h":
                        sorted_coins = sorted(data, key=lambda x: x.get("price_change_percentage_24h_in_currency", 0), reverse=True)
                    else:
                        sorted_coins = sorted(data, key=lambda x: x.get("price_change_percentage_7d_in_currency", 0), reverse=True)
                    
                    top_gainers = []
                    for coin in sorted_coins[:limit]:
                        if period == "24h":
                            change_pct = coin.get("price_change_percentage_24h_in_currency", 0)
                        else:
                            change_pct = coin.get("price_change_percentage_7d_in_currency", 0)
                        if change_pct > 0:
                            top_gainers.append({
                                "symbol": f"{coin['symbol'].upper()}/USDT",
                                "price": coin["current_price"],
                                "change": round(change_pct, 2),
                                "volume": coin["total_volume"]
                            })
                    
                    return top_gainers
                else:
                    logger.error(f"CoinGecko API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching top gainers from CoinGecko: {e}")
            return None

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_historical_prices(self, coin_id: str, vs_currency: str = "usd", days: int = 30) -> Optional[List[Dict]]:
        """Get historical price data for a cryptocurrency"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": vs_currency,
                "days": days,
                "interval": "hourly" if days <= 90 else "daily"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = []
                    for timestamp, price in data.get("prices", []):
                        prices.append({
                            "timestamp": timestamp,
                            "price": price,
                            "datetime": datetime.fromtimestamp(timestamp / 1000)
                        })
                    return prices
                else:
                    logger.error(f"CoinGecko API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching historical prices: {e}")
            return None
    
    async def simulate_momentum_strategy(self, coin_id: str, timeframe_minutes: int = 10, days: int = 30) -> Dict:
        """Simulate momentum trading strategy using historical data"""
        try:
            prices = await self.get_historical_prices(coin_id, days=days)
            if not prices:
                return {"error": "Could not fetch price data"}
            
            timeframe_data = self._resample_to_timeframe(prices, timeframe_minutes)
            
            results = self._run_momentum_simulation(timeframe_data)
            
            return {
                "coin_id": coin_id,
                "timeframe_minutes": timeframe_minutes,
                "simulation_days": days,
                "total_trades": results["total_trades"],
                "winning_trades": results["winning_trades"],
                "losing_trades": results["losing_trades"],
                "win_rate": results["win_rate"],
                "total_return": results["total_return"],
                "max_drawdown": results["max_drawdown"],
                "sharpe_ratio": results.get("sharpe_ratio", 0),
                "trades": results["trades"][:10]  # Return first 10 trades as examples
            }
        except Exception as e:
            logger.error(f"Error in momentum simulation: {e}")
            return {"error": str(e)}
    
    def _resample_to_timeframe(self, prices: List[Dict], timeframe_minutes: int) -> List[Dict]:
        """Resample hourly data to specified timeframe"""
        if timeframe_minutes >= 60:
            step = timeframe_minutes // 60
            return prices[::step]
        else:
            resampled = []
            for i in range(0, len(prices) - 1):
                current = prices[i]
                next_price = prices[i + 1]
                
                resampled.append(current)
                
                time_diff = next_price["timestamp"] - current["timestamp"]
                price_diff = next_price["price"] - current["price"]
                
                intervals = 60 // timeframe_minutes  # How many intervals in an hour
                for j in range(1, intervals):
                    interpolated_time = current["timestamp"] + (time_diff * j / intervals)
                    interpolated_price = current["price"] + (price_diff * j / intervals)
                    resampled.append({
                        "timestamp": interpolated_time,
                        "price": interpolated_price,
                        "datetime": datetime.fromtimestamp(interpolated_time / 1000)
                    })
            
            return resampled
    
    def _run_momentum_simulation(self, price_data: List[Dict]) -> Dict:
        """Run momentum trading simulation on price data"""
        if len(price_data) < 20:
            return {"error": "Insufficient data for simulation"}
        
        trades = []
        position = None
        balance = 10000  # Starting with $10,000
        peak_balance = balance
        max_drawdown = 0
        
        for i in range(10, len(price_data)):
            current_price = price_data[i]["price"]
            
            ma_10 = sum(p["price"] for p in price_data[i-10:i]) / 10
            
            if current_price > ma_10 and position is None:
                position = {
                    "entry_price": current_price,
                    "entry_time": price_data[i]["datetime"],
                    "quantity": balance / current_price
                }
            
            elif current_price < ma_10 and position is not None:
                exit_price = current_price
                pnl = (exit_price - position["entry_price"]) * position["quantity"]
                balance += pnl
                
                trades.append({
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "entry_time": position["entry_time"].isoformat(),
                    "exit_time": price_data[i]["datetime"].isoformat(),
                    "pnl": pnl,
                    "return_pct": (exit_price - position["entry_price"]) / position["entry_price"] * 100
                })
                
                position = None
                
                if balance > peak_balance:
                    peak_balance = balance
                else:
                    drawdown = (peak_balance - balance) / peak_balance * 100
                    max_drawdown = max(max_drawdown, drawdown)
        
        if position is not None:
            final_price = price_data[-1]["price"]
            pnl = (final_price - position["entry_price"]) * position["quantity"]
            balance += pnl
            
            trades.append({
                "entry_price": position["entry_price"],
                "exit_price": final_price,
                "entry_time": position["entry_time"].isoformat(),
                "exit_time": price_data[-1]["datetime"].isoformat(),
                "pnl": pnl,
                "return_pct": (final_price - position["entry_price"]) / position["entry_price"] * 100
            })
        
        winning_trades = len([t for t in trades if t["pnl"] > 0])
        losing_trades = len([t for t in trades if t["pnl"] <= 0])
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_return = (balance - 10000) / 10000 * 100
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "final_balance": balance,
            "trades": trades
        }
