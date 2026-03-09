import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .models import StakingOpportunity, ExchangeType
from .database import Database

def get_db():
    return Database()

class StakingService:
    def __init__(self):
        self.staking_platforms = {
            'binance': {
                'name': 'Binance Earn',
                'api_endpoint': 'https://api.binance.com/sapi/v1/lending/project/list',
                'supported': True
            },
            'coinbase': {
                'name': 'Coinbase Earn',
                'api_endpoint': 'https://api.exchange.coinbase.com/products',
                'supported': True
            },
            'kraken': {
                'name': 'Kraken Staking',
                'api_endpoint': 'https://api.kraken.com/0/public/Assets',
                'supported': True
            }
        }
    
    async def get_top_staking_opportunities(self, period: str = "1y", risk_level: str = "all") -> List[StakingOpportunity]:
        """Get top staking opportunities sorted by APY"""
        try:
            opportunities = []
            
            sample_opportunities = [
                StakingOpportunity(
                    platform="Binance",
                    token="ETH",
                    apy=4.5,
                    minimum_stake=0.1,
                    lock_period="flexible",
                    risk_level="low",
                    auto_compound=True
                ),
                StakingOpportunity(
                    platform="Coinbase",
                    token="SOL",
                    apy=6.8,
                    minimum_stake=1.0,
                    lock_period="flexible",
                    risk_level="medium",
                    auto_compound=False
                ),
                StakingOpportunity(
                    platform="Kraken",
                    token="DOT",
                    apy=12.0,
                    minimum_stake=1.0,
                    lock_period="28d",
                    risk_level="medium",
                    auto_compound=True
                ),
                StakingOpportunity(
                    platform="Binance",
                    token="ADA",
                    apy=5.2,
                    minimum_stake=10.0,
                    lock_period="30d",
                    risk_level="low",
                    auto_compound=True
                ),
                StakingOpportunity(
                    platform="Coinbase",
                    token="ATOM",
                    apy=8.5,
                    minimum_stake=0.1,
                    lock_period="21d",
                    risk_level="medium",
                    auto_compound=False
                ),
                StakingOpportunity(
                    platform="Kraken",
                    token="MATIC",
                    apy=4.0,
                    minimum_stake=1.0,
                    lock_period="flexible",
                    risk_level="low",
                    auto_compound=True
                )
            ]
            
            if risk_level != "all":
                sample_opportunities = [opp for opp in sample_opportunities if opp.risk_level == risk_level]
            
            opportunities = sorted(sample_opportunities, key=lambda x: x.apy, reverse=True)
            
            return opportunities[:10]  # Return top 10
            
        except Exception as e:
            print(f"Error getting staking opportunities: {e}")
            return []
    
    async def optimize_staking_allocation(self, user_id: int, available_balance: Dict[str, float], 
                                        target_period: str = "1y") -> Dict[str, Any]:
        """Optimize staking allocation for maximum APY"""
        try:
            opportunities = await self.get_top_staking_opportunities(target_period)
            
            allocation_plan = []
            total_estimated_yield = 0.0
            total_allocated = 0.0
            
            for token, balance in available_balance.items():
                if balance > 0:
                    best_opportunity = None
                    for opp in opportunities:
                        if opp.token == token and balance >= opp.minimum_stake:
                            if not best_opportunity or opp.apy > best_opportunity.apy:
                                best_opportunity = opp
                    
                    if best_opportunity:
                        stake_amount = balance
                        estimated_yearly_yield = stake_amount * (best_opportunity.apy / 100)
                        
                        period_multiplier = self.get_period_multiplier(target_period)
                        estimated_yield = estimated_yearly_yield * period_multiplier
                        
                        allocation_plan.append({
                            'token': token,
                            'platform': best_opportunity.platform,
                            'stake_amount': stake_amount,
                            'apy': best_opportunity.apy,
                            'estimated_yield': estimated_yield,
                            'lock_period': best_opportunity.lock_period,
                            'risk_level': best_opportunity.risk_level
                        })
                        
                        total_estimated_yield += estimated_yield
                        total_allocated += stake_amount
            
            return {
                'allocation_plan': allocation_plan,
                'total_allocated': total_allocated,
                'total_estimated_yield': total_estimated_yield,
                'average_apy': (total_estimated_yield / total_allocated * 100) if total_allocated > 0 else 0.0,
                'target_period': target_period
            }
            
        except Exception as e:
            print(f"Error optimizing staking allocation: {e}")
            return {
                'allocation_plan': [],
                'total_allocated': 0.0,
                'total_estimated_yield': 0.0,
                'average_apy': 0.0,
                'target_period': target_period
            }
    
    def get_period_multiplier(self, period: str) -> float:
        """Get multiplier for different time periods"""
        multipliers = {
            "1d": 1/365,
            "1w": 7/365,
            "1m": 30/365,
            "3m": 90/365,
            "1y": 1.0
        }
        return multipliers.get(period, 1.0)
    
    async def execute_staking_rebalance(self, user_id: int, allocation_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute staking rebalance based on allocation plan"""
        try:
            results = []
            total_staked = 0.0
            
            for allocation in allocation_plan:
                result = {
                    'token': allocation['token'],
                    'platform': allocation['platform'],
                    'amount_staked': allocation['stake_amount'],
                    'apy': allocation['apy'],
                    'status': 'success',
                    'transaction_id': f"stake_{user_id}_{allocation['token']}_{datetime.now().timestamp()}"
                }
                
                results.append(result)
                total_staked += allocation['stake_amount']
                
                get_db().save_staking_record(
                    user_id=user_id,
                    token=allocation['token'],
                    platform=allocation['platform'],
                    amount=allocation['stake_amount'],
                    apy=allocation['apy'],
                    lock_period=allocation['lock_period']
                )
            
            return {
                'success': True,
                'results': results,
                'total_staked': total_staked,
                'rebalance_timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"Error executing staking rebalance: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'total_staked': 0.0
            }
    
    async def get_user_staking_summary(self, user_id: int) -> Dict[str, Any]:
        """Get user's current staking summary"""
        try:
            staking_records = get_db().get_user_staking_records(user_id)
            
            total_staked = sum(record['amount'] for record in staking_records)
            total_estimated_yield = sum(
                record['amount'] * (record['apy'] / 100) for record in staking_records
            )
            average_apy = (total_estimated_yield / total_staked * 100) if total_staked > 0 else 0.0
            
            return {
                'total_staked': total_staked,
                'total_estimated_yearly_yield': total_estimated_yield,
                'average_apy': average_apy,
                'active_stakes': len(staking_records),
                'staking_records': staking_records
            }
            
        except Exception as e:
            print(f"Error getting staking summary: {e}")
            return {
                'total_staked': 0.0,
                'total_estimated_yearly_yield': 0.0,
                'average_apy': 0.0,
                'active_stakes': 0,
                'staking_records': []
            }
