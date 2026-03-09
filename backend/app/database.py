import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import hashlib
import secrets
from app.encryption import encrypt_string, decrypt_string

try:
    import psycopg2 as psycopg
    from psycopg2.extras import RealDictCursor
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False
    psycopg = None
    RealDictCursor = None

class Database:
    def __init__(self, db_path: str = "trading_bot.db"):
        self.db_path = db_path
        self.database_url = os.getenv('DATABASE_URL')
        self.is_postgresql = self.database_url and self.database_url.startswith('postgresql') and PSYCOPG_AVAILABLE
        
        print(f"Database initialization - DATABASE_URL set: {bool(self.database_url)}")
        print(f"PostgreSQL available: {PSYCOPG_AVAILABLE}")
        if self.database_url:
            print(f"Database URL prefix: {self.database_url[:30]}...")
        print(f"Using PostgreSQL: {self.is_postgresql}")
        
        try:
            self.init_database()
            self.create_onboarding_table()
            print("Database initialization successful")
        except Exception as e:
            print(f"Database initialization failed: {e}")
            if self.is_postgresql:
                print("Falling back to SQLite due to PostgreSQL connection failure")
                self.database_url = None
                self.is_postgresql = False
                self.init_database()
                self.create_onboarding_table()
                print("SQLite fallback successful")
    def create_onboarding_table(self):
        """Create onboarding_progress table with PostgreSQL/SQLite compatibility"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    current_step TEXT NOT NULL,
                    exchange_connected BOOLEAN DEFAULT false,
                    wallet_connected BOOLEAN DEFAULT false,
                    bot_funded BOOLEAN DEFAULT false,
                    settings_configured BOOLEAN DEFAULT false,
                    bot_launched BOOLEAN DEFAULT false,
                    completion_percentage REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    current_step TEXT NOT NULL,
                    exchange_connected BOOLEAN DEFAULT 0,
                    wallet_connected BOOLEAN DEFAULT 0,
                    bot_funded BOOLEAN DEFAULT 0,
                    settings_configured BOOLEAN DEFAULT 0,
                    bot_launched BOOLEAN DEFAULT 0,
                    completion_percentage REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        conn.commit()
        conn.close()


    
    def get_connection(self):
        if self.is_postgresql and PSYCOPG_AVAILABLE:
            conn = psycopg.connect(self.database_url, cursor_factory=RealDictCursor)
            return conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    full_name TEXT,
                    country TEXT,
                    wallet_address TEXT UNIQUE,
                    total_invested REAL DEFAULT 0.0,
                    total_profit REAL DEFAULT 0.0,
                    is_active BOOLEAN DEFAULT true,
                    auth_method TEXT DEFAULT 'email',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    CONSTRAINT email_or_wallet CHECK (
                        (auth_method = 'email' AND email IS NOT NULL AND password_hash IS NOT NULL) OR
                        (auth_method = 'wallet' AND wallet_address IS NOT NULL)
                    )
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    full_name TEXT,
                    country TEXT,
                    wallet_address TEXT UNIQUE,
                    total_invested REAL DEFAULT 0.0,
                    total_profit REAL DEFAULT 0.0,
                    is_active BOOLEAN DEFAULT 1,
                    auth_method TEXT DEFAULT 'email',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    default_risk_level TEXT DEFAULT 'moderate',
                    default_stop_loss REAL DEFAULT 2.0,
                    auto_restart BOOLEAN DEFAULT 1,
                    email_notifications BOOLEAN DEFAULT 1,
                    trade_alerts BOOLEAN DEFAULT 1,
                    profit_alerts BOOLEAN DEFAULT 1,
                    loss_alerts BOOLEAN DEFAULT 1
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exchange_credentials (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    encrypted_secret_key TEXT NOT NULL,
                    encrypted_passphrase TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exchange_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    encrypted_secret_key TEXT NOT NULL,
                    encrypted_passphrase TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_configs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    trading_pairs TEXT NOT NULL,
                    investment_amount REAL NOT NULL,
                    stop_loss_percentage REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    trading_pairs TEXT NOT NULL,
                    investment_amount REAL NOT NULL,
                    stop_loss_percentage REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL,
                    profit_loss REAL,
                    fees REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL,
                    profit_loss REAL,
                    fees REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profit_shares (
                    id SERIAL PRIMARY KEY,
                    trade_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    profit_amount REAL NOT NULL,
                    share_amount REAL NOT NULL,
                    transaction_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trade_id) REFERENCES trades (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profit_shares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    profit_amount REAL NOT NULL,
                    share_amount REAL NOT NULL,
                    transaction_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trade_id) REFERENCES trades (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_data (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_24h REAL NOT NULL,
                    change_7d REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    market_cap REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_24h REAL NOT NULL,
                    change_7d REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    market_cap REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dca_configs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    total_investment REAL NOT NULL,
                    order_frequency TEXT NOT NULL,
                    order_amount REAL NOT NULL,
                    price_deviation_threshold REAL DEFAULT 5.0,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dca_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    total_investment REAL NOT NULL,
                    order_frequency TEXT NOT NULL,
                    order_amount REAL NOT NULL,
                    price_deviation_threshold REAL DEFAULT 5.0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staking_records (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    amount REAL NOT NULL,
                    apy REAL NOT NULL,
                    lock_period TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staking_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    amount REAL NOT NULL,
                    apy REAL NOT NULL,
                    lock_period TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        if self.is_postgresql:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    referral_code TEXT UNIQUE NOT NULL,
                    referred_users TEXT DEFAULT '[]',
                    total_earnings REAL DEFAULT 0.0,
                    commission_rate REAL DEFAULT 0.1,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    referral_code TEXT UNIQUE NOT NULL,
                    referred_users TEXT DEFAULT '[]',
                    total_earnings REAL DEFAULT 0.0,
                    commission_rate REAL DEFAULT 0.1,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, email: str, password_hash: str, full_name: str = "", country: str = "") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO users (email, password_hash, full_name, country, auth_method)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            ''', (email, password_hash, full_name, country, 'email'))
            user_id = cursor.fetchone()[0]
            
            import secrets
            referral_code = secrets.token_urlsafe(8)
            cursor.execute('''
                INSERT INTO referrals (user_id, referral_code)
                VALUES (%s, %s)
            ''', (user_id, referral_code))
        else:
            cursor.execute('''
                INSERT INTO users (email, password_hash, full_name, country, auth_method)
                VALUES (?, ?, ?, ?, ?)
            ''', (email, password_hash, full_name, country, 'email'))
            
            user_id = cursor.lastrowid
            
            import secrets
            referral_code = secrets.token_urlsafe(8)
            cursor.execute('''
                INSERT INTO referrals (user_id, referral_code)
                VALUES (?, ?)
            ''', (user_id, referral_code))
        
        conn.commit()
        conn.close()
        return user_id or 0
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        else:
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        conn.close()
        return dict(user) if user else None
    
    def update_user_login(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
            ''', (user_id,))
        else:
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def save_exchange_credentials(self, user_id: int, exchange_type: str, 
                                encrypted_api_key: str, encrypted_secret_key: str, 
                                encrypted_passphrase: Optional[str] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                DELETE FROM exchange_credentials 
                WHERE user_id = %s AND exchange_type = %s
            ''', (user_id, exchange_type))
            
            cursor.execute('''
                INSERT INTO exchange_credentials 
                (user_id, exchange_type, encrypted_api_key, encrypted_secret_key, encrypted_passphrase)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, exchange_type, encrypted_api_key, encrypted_secret_key, encrypted_passphrase))
        else:
            cursor.execute('''
                DELETE FROM exchange_credentials 
                WHERE user_id = ? AND exchange_type = ?
            ''', (user_id, exchange_type))
            
            cursor.execute('''
                INSERT INTO exchange_credentials 
                (user_id, exchange_type, encrypted_api_key, encrypted_secret_key, encrypted_passphrase)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, exchange_type, encrypted_api_key, encrypted_secret_key, encrypted_passphrase))
        
        conn.commit()
        conn.close()
    
    def get_exchange_credentials(self, user_id: int, exchange_type: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM exchange_credentials 
                WHERE user_id = %s AND exchange_type = %s
            ''', (user_id, exchange_type))
        else:
            cursor.execute('''
                SELECT * FROM exchange_credentials 
                WHERE user_id = ? AND exchange_type = ?
            ''', (user_id, exchange_type))
        
        credentials = cursor.fetchone()
        conn.close()
        
        if not credentials:
            return None
            
        creds_dict = dict(credentials)
        
        try:
            creds_dict['encrypted_api_key'] = decrypt_string(creds_dict['encrypted_api_key'])
            creds_dict['encrypted_secret_key'] = decrypt_string(creds_dict['encrypted_secret_key'])
            if creds_dict.get('encrypted_passphrase'):
                creds_dict['encrypted_passphrase'] = decrypt_string(creds_dict['encrypted_passphrase'])
        except Exception as e:
            print(f"Warning: Failed to decrypt credentials for user {user_id}: {e}")
            
        return creds_dict
    
    def save_bot_config(self, user_id: int, exchange_type: str, trading_pairs: List[str], 
                       investment_amount: float, stop_loss_percentage: float, strategy: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO bot_configs 
                (user_id, exchange_type, trading_pairs, investment_amount, stop_loss_percentage, strategy)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            ''', (user_id, exchange_type, json.dumps(trading_pairs), investment_amount, stop_loss_percentage, strategy))
            config_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO bot_configs 
                (user_id, exchange_type, trading_pairs, investment_amount, stop_loss_percentage, strategy)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, exchange_type, json.dumps(trading_pairs), investment_amount, stop_loss_percentage, strategy))
            config_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return config_id or 0
    
    def get_user_bot_configs(self, user_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM bot_configs WHERE user_id = %s AND is_active = true
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM bot_configs WHERE user_id = ? AND is_active = 1
            ''', (user_id,))
        
        configs = cursor.fetchall()
        conn.close()
        
        result = []
        for config in configs:
            config_dict = dict(config)
            config_dict['trading_pairs'] = json.loads(config_dict['trading_pairs'])
            result.append(config_dict)
        
        return result
    
    def save_trade(self, user_id: int, exchange_type: str, symbol: str, side: str, 
                  amount: float, price: float, status: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO trades 
                (user_id, exchange_type, symbol, side, amount, price, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            ''', (user_id, exchange_type, symbol, side, amount, price, status))
            trade_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO trades 
                (user_id, exchange_type, symbol, side, amount, price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, exchange_type, symbol, side, amount, price, status))
            trade_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return trade_id or 0
    
    def update_trade(self, trade_id: int, status: str, profit_loss: Optional[float] = None,
                    fees: Optional[float] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                UPDATE trades 
                SET status = %s, profit_loss = %s, fees = %s, executed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (status, profit_loss, fees, trade_id))
        else:
            cursor.execute('''
                UPDATE trades 
                SET status = ?, profit_loss = ?, fees = ?, executed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, profit_loss, fees, trade_id))
        
        conn.commit()
        conn.close()
    
    def get_user_trades(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM trades WHERE user_id = %s 
                ORDER BY created_at DESC LIMIT %s
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM trades WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit))
        
        trades = cursor.fetchall()
        conn.close()
        return [dict(trade) for trade in trades]
    
    def save_market_data(self, symbol: str, price: float, change_24h: float, 
                        change_7d: float, volume_24h: float, market_cap: Optional[float] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO market_data 
            (symbol, price, change_24h, change_7d, volume_24h, market_cap)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, price, change_24h, change_7d, volume_24h, market_cap))
        
        conn.commit()
        conn.close()
    
    def get_top_gainers(self, period: str = "24h", limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if period == "24h":
            order_by = "change_24h DESC"
        else:
            order_by = "change_7d DESC"
        
        if self.is_postgresql:
            cursor.execute(f'''
                SELECT * FROM market_data 
                WHERE timestamp > NOW() - INTERVAL '1 hour'
                ORDER BY {order_by} LIMIT %s
            ''', (limit,))
        else:
            cursor.execute(f'''
                SELECT * FROM market_data 
                WHERE timestamp > datetime('now', '-1 hour')
                ORDER BY {order_by} LIMIT ?
            ''', (limit,))
        
        gainers = cursor.fetchall()
        conn.close()
        return [dict(gainer) for gainer in gainers]
    
    def save_dca_config(self, config):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO dca_configs 
                (user_id, exchange_type, symbol, total_investment, order_frequency, order_amount, price_deviation_threshold, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, exchange_type, symbol) DO UPDATE SET
                    total_investment = EXCLUDED.total_investment,
                    order_frequency = EXCLUDED.order_frequency,
                    order_amount = EXCLUDED.order_amount,
                    price_deviation_threshold = EXCLUDED.price_deviation_threshold,
                    is_active = EXCLUDED.is_active
            ''', (config.user_id, config.exchange_type.value, config.symbol, config.total_investment, 
                  config.order_frequency, config.order_amount, config.price_deviation_threshold, config.is_active))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO dca_configs 
                (user_id, exchange_type, symbol, total_investment, order_frequency, order_amount, price_deviation_threshold, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (config.user_id, config.exchange_type.value, config.symbol, config.total_investment, 
                  config.order_frequency, config.order_amount, config.price_deviation_threshold, config.is_active))
        
        conn.commit()
        conn.close()
    
    def update_dca_config_status(self, user_id: int, is_active: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                UPDATE dca_configs SET is_active = %s WHERE user_id = %s
            ''', (is_active, user_id))
        else:
            cursor.execute('''
                UPDATE dca_configs SET is_active = ? WHERE user_id = ?
            ''', (is_active, user_id))
        
        conn.commit()
        conn.close()
    
    def get_user_exchanges(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM exchange_credentials WHERE user_id = %s
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM exchange_credentials WHERE user_id = ?
            ''', (user_id,))
        
        credentials = cursor.fetchall()
        conn.close()
        
        user_exchanges = []
        for cred in credentials:
            user_exchanges.append({
                'exchange_type': cred['exchange_type'],
                'credentials': {
                    'api_key': cred['encrypted_api_key'],
                    'secret': cred['encrypted_secret_key'],
                    'passphrase': cred['encrypted_passphrase']
                }
            })
        return user_exchanges
    
    def get_user_exchange_credentials(self, user_id: int, exchange_type: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM exchange_credentials WHERE user_id = %s AND exchange_type = %s
            ''', (user_id, exchange_type))
        else:
            cursor.execute('''
                SELECT * FROM exchange_credentials WHERE user_id = ? AND exchange_type = ?
            ''', (user_id, exchange_type))
        
        cred = cursor.fetchone()
        conn.close()
        
        if cred:
            return {
                'api_key': cred['encrypted_api_key'],
                'secret': cred['encrypted_secret_key'],
                'passphrase': cred['encrypted_passphrase']
            }
        return None
    
    def get_average_purchase_price(self, user_id: int, symbol: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT amount, price FROM trades 
                WHERE user_id = %s AND symbol = %s AND side = 'buy'
            ''', (user_id, symbol))
        else:
            cursor.execute('''
                SELECT amount, price FROM trades 
                WHERE user_id = ? AND symbol = ? AND side = 'buy'
            ''', (user_id, symbol))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return None
        
        total_cost = sum(trade['amount'] * trade['price'] for trade in trades)
        total_amount = sum(trade['amount'] for trade in trades)
        return total_cost / total_amount if total_amount > 0 else None
    
    def save_dca_order(self, user_id: int, symbol: str, amount: float, price: float, order_id: str):
        return self.save_trade(user_id, 'dca_bot', symbol, 'buy', amount, price, 'filled')
    
    def get_historical_portfolio_value(self, user_id: int, period: str):
        return 10000.0
    
    def save_staking_record(self, user_id: int, token: str, platform: str, amount: float, apy: float, lock_period: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO staking_records (user_id, token, platform, amount, apy, lock_period)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            ''', (user_id, token, platform, amount, apy, lock_period))
            record_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO staking_records (user_id, token, platform, amount, apy, lock_period)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, token, platform, amount, apy, lock_period))
            record_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return record_id or 0
    
    def get_user_staking_records(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM staking_records WHERE user_id = %s
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM staking_records WHERE user_id = ?
            ''', (user_id,))
        
        records = cursor.fetchall()
        conn.close()
        return [dict(record) for record in records]
    
    def get_user_referral_data(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                SELECT * FROM referrals WHERE user_id = %s
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM referrals WHERE user_id = ?
            ''', (user_id,))
        
        referral = cursor.fetchone()
        conn.close()
        
        if referral:
            referred_users = json.loads(referral['referred_users']) if referral['referred_users'] else []
            return {
                'referral_code': referral['referral_code'],
                'referred_users': len(referred_users),
                'total_earnings': referral['total_earnings'],
                'commission_rate': referral['commission_rate']
            }
        return {
            'referral_code': 'NEWUSER',
            'referred_users': 0,
            'total_earnings': 0.0,
            'commission_rate': 0.1
        }
    
    def save_grid_config(self, config):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bot_configs (user_id, exchange_type, trading_pairs, investment_amount, 
                                   stop_loss_percentage, strategy, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (config.user_id, config.exchange_type.value, config.symbol, 
              config.investment_amount, 0, 'grid', config.is_active))
        conn.commit()
        conn.close()

    def save_infinity_config(self, config):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bot_configs (user_id, exchange_type, trading_pairs, investment_amount, 
                                   stop_loss_percentage, strategy, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (config.user_id, config.exchange_type.value, config.symbol, 
              config.investment_amount, config.max_drawdown, 'infinity', config.is_active))
        conn.commit()
        conn.close()

    def create_wallet_user(self, wallet_address: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('''
                INSERT INTO users (wallet_address, auth_method, full_name, country)
                VALUES (%s, %s, %s, %s) RETURNING id
            ''', (wallet_address, 'wallet', '', ''))
            user_id = cursor.fetchone()[0]
            
            import secrets
            referral_code = secrets.token_urlsafe(8)
            cursor.execute('''
                INSERT INTO referrals (user_id, referral_code)
                VALUES (%s, %s)
            ''', (user_id, referral_code))
        else:
            cursor.execute('''
                INSERT INTO users (wallet_address, auth_method, full_name, country)
                VALUES (?, ?, ?, ?)
            ''', (wallet_address, 'wallet', '', ''))
            
            user_id = cursor.lastrowid
            
            import secrets
            referral_code = secrets.token_urlsafe(8)
            cursor.execute('''
                INSERT INTO referrals (user_id, referral_code)
                VALUES (?, ?)
            ''', (user_id, referral_code))
        
        conn.commit()
        conn.close()
        return user_id or 0

    def get_user_by_wallet_address(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_postgresql:
            cursor.execute('SELECT * FROM users WHERE wallet_address = %s', (wallet_address,))
        else:
            cursor.execute('SELECT * FROM users WHERE wallet_address = ?', (wallet_address,))
        user = cursor.fetchone()
        
        conn.close()
        return dict(user) if user else None

    def get_onboarding_progress(self, user_id: int) -> dict:
        """Get user's onboarding progress"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.is_postgresql:
                cursor.execute("""
                    SELECT * FROM onboarding_progress WHERE user_id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT * FROM onboarding_progress WHERE user_id = ?
                """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "current_step": row[2],
                    "exchange_connected": bool(row[3]),
                    "wallet_connected": bool(row[4]),
                    "bot_funded": bool(row[5]),
                    "settings_configured": bool(row[6]),
                    "bot_launched": bool(row[7]),
                    "completion_percentage": row[8],
                    "created_at": row[9],
                    "updated_at": row[10]
                }
            return None
            
        except Exception as e:
            print(f"Error getting onboarding progress: {e}")
            return None
        finally:
            conn.close()

    def create_onboarding_progress(self, progress_data: dict) -> int:
        """Create initial onboarding progress record"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.is_postgresql:
                cursor.execute("""
                    INSERT INTO onboarding_progress (
                        user_id, current_step, exchange_connected, wallet_connected,
                        bot_funded, settings_configured, bot_launched, completion_percentage,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    progress_data["user_id"],
                    progress_data["current_step"],
                    progress_data["exchange_connected"],
                    progress_data["wallet_connected"],
                    progress_data["bot_funded"],
                    progress_data["settings_configured"],
                    progress_data["bot_launched"],
                    progress_data["completion_percentage"],
                    datetime.now(),
                    datetime.now()
                ))
                progress_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO onboarding_progress (
                        user_id, current_step, exchange_connected, wallet_connected,
                        bot_funded, settings_configured, bot_launched, completion_percentage,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    progress_data["user_id"],
                    progress_data["current_step"],
                    progress_data["exchange_connected"],
                    progress_data["wallet_connected"],
                    progress_data["bot_funded"],
                    progress_data["settings_configured"],
                    progress_data["bot_launched"],
                    progress_data["completion_percentage"],
                    datetime.now(),
                    datetime.now()
                ))
                progress_id = cursor.lastrowid
            
            conn.commit()
            return progress_id
            
        except Exception as e:
            print(f"Error creating onboarding progress: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_onboarding_progress(self, user_id: int, progress_data: dict):
        """Update onboarding progress"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.is_postgresql:
                cursor.execute("""
                    UPDATE onboarding_progress SET
                        current_step = %s,
                        exchange_connected = %s,
                        wallet_connected = %s,
                        bot_funded = %s,
                        settings_configured = %s,
                        bot_launched = %s,
                        completion_percentage = %s,
                        updated_at = %s
                    WHERE user_id = %s
                """, (
                    progress_data["current_step"],
                    progress_data["exchange_connected"],
                    progress_data["wallet_connected"],
                    progress_data["bot_funded"],
                    progress_data["settings_configured"],
                    progress_data["bot_launched"],
                    progress_data["completion_percentage"],
                    datetime.now(),
                    user_id
                ))
            else:
                cursor.execute("""
                    UPDATE onboarding_progress SET
                        current_step = ?,
                        exchange_connected = ?,
                        wallet_connected = ?,
                        bot_funded = ?,
                        settings_configured = ?,
                        bot_launched = ?,
                        completion_percentage = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (
                    progress_data["current_step"],
                    progress_data["exchange_connected"],
                    progress_data["wallet_connected"],
                    progress_data["bot_funded"],
                    progress_data["settings_configured"],
                    progress_data["bot_launched"],
                    progress_data["completion_percentage"],
                    datetime.now(),
                    user_id
                ))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating onboarding progress: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
