from typing import Dict, Optional, List
import asyncio
from datetime import datetime
from .models import TradingBotConfig, ExchangeType
from .exchange_service import ExchangeService

class MomentumService:
    def __init__(self):
        self.active_bots: Dict[int, Dict] = {}

    async def start_bot(self, user_id: int, config: TradingBotConfig, exchange_svc: ExchangeService, paper_mode: bool = True):
        self.active_bots[user_id] = {
            "config": config,
            "status": "running",
            "last_run": None,
            "last_tick_at": None,
            "last_error": None,
            "paper_mode": paper_mode,
            "current_position": None,
        }
        asyncio.create_task(self._run_loop(user_id, exchange_svc))

    async def stop_bot(self, user_id: int):
        if user_id in self.active_bots:
            self.active_bots[user_id]["status"] = "stopped"

    def get_status(self, user_id: int):
        return self.active_bots.get(user_id) or {"status": "idle"}

    async def _run_loop(self, user_id: int, exchange_svc: ExchangeService):
        while user_id in self.active_bots and self.active_bots[user_id]["status"] == "running":
            try:
                cfg: TradingBotConfig = self.active_bots[user_id]["config"]
                symbols = cfg.trading_pairs or ["BTC/USDT", "ETH/USDT"]
                
                timeframe_seconds = self._get_timeframe_seconds(getattr(cfg, 'timeframe', '1m'))
                
                data = await exchange_svc.fetch_market_data(cfg.exchange_type, symbols)
                if not data:
                    await asyncio.sleep(timeframe_seconds)
                    continue
                top = max(data, key=lambda d: d.change_24h)
                state = self.active_bots[user_id]
                if not state["current_position"]:
                    if state["paper_mode"]:
                        state["current_position"] = {"symbol": top.symbol, "price": top.price, "ts": datetime.utcnow().isoformat()}
                state["last_run"] = datetime.utcnow().isoformat()
                state["last_tick_at"] = state["last_run"]
                state["last_error"] = None
            except Exception as e:
                print(f"Momentum loop error for user {user_id}: {e}")
                if user_id in self.active_bots:
                    self.active_bots[user_id]["last_error"] = str(e)
            await asyncio.sleep(timeframe_seconds)
    
    def _get_timeframe_seconds(self, timeframe: str) -> int:
        timeframes = {"1m": 60, "5m": 300, "10m": 600, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        return timeframes.get(timeframe, 60)
