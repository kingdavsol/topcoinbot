from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from .database import Database
import os

class SubscriptionService:
    def __init__(self):
        self.db = Database()
        self.pricing = {
            "grid": 7.49,
            "infinity": 7.49,
            "dca": 7.49,
            "momentum": 19.49,
            "grid_infinity_dca_bundle": 17.99,
            "all_bots": 29.49
        }
        
        self.plan_bot_access = {
            "grid": ["grid"],
            "infinity": ["infinity"],
            "dca": ["dca"],
            "momentum": ["momentum"],
            "grid_infinity_dca_bundle": ["grid", "infinity", "dca"],
            "all_bots": ["grid", "infinity", "dca", "momentum"]
        }
    
    def get_pricing_tiers(self) -> List[Dict[str, Any]]:
        """Get all available pricing tiers"""
        return [
            {
                "plan_type": "grid",
                "name": "Grid Bot",
                "price": 7.49,
                "currency": "USD",
                "interval": "month",
                "bots": ["Grid Trading Bot"],
                "features": ["Automated grid trading", "Profit from volatility", "24/7 monitoring"]
            },
            {
                "plan_type": "infinity",
                "name": "Infinity Bot",
                "price": 7.49,
                "currency": "USD",
                "interval": "month",
                "bots": ["Infinity Trading Bot"],
                "features": ["Trailing stop strategy", "Momentum capture", "Dynamic exits"]
            },
            {
                "plan_type": "dca",
                "name": "DCA Bot",
                "price": 7.49,
                "currency": "USD",
                "interval": "month",
                "bots": ["Dollar Cost Averaging Bot"],
                "features": ["Scheduled purchases", "Risk averaging", "Long-term strategy"]
            },
            {
                "plan_type": "momentum",
                "name": "Momentum Bot",
                "price": 19.49,
                "currency": "USD",
                "interval": "month",
                "bots": ["Momentum Trading Bot"],
                "features": ["Trend following", "Smart exits", "Risk management"]
            },
            {
                "plan_type": "grid_infinity_dca_bundle",
                "name": "Starter Bundle",
                "price": 17.99,
                "currency": "USD",
                "interval": "month",
                "bots": ["Grid Bot", "Infinity Bot", "DCA Bot"],
                "features": ["3 bot types", "Save $4.48/month", "Best for beginners"],
                "badge": "POPULAR"
            },
            {
                "plan_type": "all_bots",
                "name": "All Bots Access",
                "price": 29.49,
                "currency": "USD",
                "interval": "month",
                "bots": ["Grid", "Infinity", "DCA", "Momentum"],
                "features": ["All 4 bot types", "Save $14.47/month", "Complete trading suite"],
                "badge": "BEST VALUE"
            }
        ]
    
    def create_subscription(self, user_id: int, plan_type: str, payment_method: str, 
                          trial_days: int = 7) -> Dict[str, Any]:
        """Create a new subscription with 7-day trial"""
        try:
            if plan_type not in self.pricing:
                return {"success": False, "error": "Invalid plan type"}
            
            existing = self.get_user_subscription(user_id)
            if existing and existing["status"] in ["active", "trialing"]:
                return {"success": False, "error": "User already has an active subscription"}
            
            amount = self.pricing[plan_type]
            trial_end = datetime.utcnow() + timedelta(days=trial_days)
            next_billing = trial_end + timedelta(days=30)
            status = "trialing"
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    INSERT INTO subscriptions (user_id, plan_type, status, payment_method, amount, 
                                             next_billing_date, trial_end_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                ''', (user_id, plan_type, status, payment_method, amount, next_billing, trial_end))
                subscription_id = cursor.fetchone()['id']
            else:
                cursor.execute('''
                    INSERT INTO subscriptions (user_id, plan_type, status, payment_method, amount,
                                             next_billing_date, trial_end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, plan_type, status, payment_method, amount, next_billing, trial_end))
                subscription_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "plan_type": plan_type,
                "status": status,
                "next_billing_date": next_billing.isoformat(),
                "trial_end_date": trial_end.isoformat()
            }
        except Exception as e:
            print(f"Error creating subscription: {e}")
            return {"success": False, "error": str(e)}
    
    def get_user_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's active subscription"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    SELECT * FROM subscriptions 
                    WHERE user_id = %s AND status IN ('active', 'trialing', 'past_due')
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM subscriptions 
                    WHERE user_id = ? AND status IN ('active', 'trialing', 'past_due')
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting subscription: {e}")
            return None
    
    def has_bot_access(self, user_id: int, bot_type: str) -> bool:
        """Check if user has access to specific bot type"""
        subscription = self.get_user_subscription(user_id)
        
        if not subscription:
            return False
        
        if subscription["status"] not in ["active", "trialing"]:
            return False
        
        plan_type = subscription["plan_type"]
        allowed_bots = self.plan_bot_access.get(plan_type, [])
        
        return bot_type.lower() in allowed_bots
    
    def cancel_subscription(self, user_id: int) -> Dict[str, Any]:
        """Cancel user's subscription"""
        try:
            subscription = self.get_user_subscription(user_id)
            if not subscription:
                return {"success": False, "error": "No active subscription found"}
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    UPDATE subscriptions 
                    SET status = %s, canceled_at = %s, updated_at = %s
                    WHERE id = %s
                ''', ('canceled', datetime.utcnow(), datetime.utcnow(), subscription['id']))
            else:
                cursor.execute('''
                    UPDATE subscriptions 
                    SET status = ?, canceled_at = ?, updated_at = ?
                    WHERE id = ?
                ''', ('canceled', datetime.utcnow(), datetime.utcnow(), subscription['id']))
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Subscription canceled"}
        except Exception as e:
            print(f"Error canceling subscription: {e}")
            return {"success": False, "error": str(e)}
    
    def record_payment(self, subscription_id: int, user_id: int, amount: float,
                      currency: str, payment_method: str, tx_hash: str = None) -> int:
        """Record a subscription payment"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    INSERT INTO subscription_payments (subscription_id, user_id, amount, currency,
                                                      payment_method, status, crypto_tx_hash, paid_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                ''', (subscription_id, user_id, amount, currency, payment_method, 'completed', tx_hash, datetime.utcnow()))
                payment_id = cursor.fetchone()['id']
            else:
                cursor.execute('''
                    INSERT INTO subscription_payments (subscription_id, user_id, amount, currency,
                                                      payment_method, status, crypto_tx_hash, paid_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (subscription_id, user_id, amount, currency, payment_method, 'completed', tx_hash, datetime.utcnow()))
                payment_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            return payment_id
        except Exception as e:
            print(f"Error recording payment: {e}")
            return 0
    
    def update_subscription_status(self, subscription_id: int, status: str, 
                                  stripe_subscription_id: str = None,
                                  stripe_customer_id: str = None) -> bool:
        """Update subscription status and Stripe IDs"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                if stripe_subscription_id and stripe_customer_id:
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET status = %s, stripe_subscription_id = %s, stripe_customer_id = %s, 
                            updated_at = %s
                        WHERE id = %s
                    ''', (status, stripe_subscription_id, stripe_customer_id, datetime.utcnow(), subscription_id))
                else:
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET status = %s, updated_at = %s
                        WHERE id = %s
                    ''', (status, datetime.utcnow(), subscription_id))
            else:
                if stripe_subscription_id and stripe_customer_id:
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET status = ?, stripe_subscription_id = ?, stripe_customer_id = ?, 
                            updated_at = ?
                        WHERE id = ?
                    ''', (status, stripe_subscription_id, stripe_customer_id, datetime.utcnow(), subscription_id))
                else:
                    cursor.execute('''
                        UPDATE subscriptions 
                        SET status = ?, updated_at = ?
                        WHERE id = ?
                    ''', (status, datetime.utcnow(), subscription_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating subscription status: {e}")
            return False
