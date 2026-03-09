import asyncio
import time
from typing import Dict, Set
from datetime import datetime
from .database import Database
from .web3_service import Web3Service
from web3 import Web3

class DepositMonitor:
    """Background service to monitor blockchain for incoming deposits"""
    
    def __init__(self, db: Database, web3_service: Web3Service):
        self.db = db
        self.w3_service = web3_service
        self.w3 = web3_service.w3
        self.usdc_contract = web3_service.usdc_contract
        self.running = False
        self.poll_interval = 30
        self.confirmation_threshold = 6
        self.monitored_addresses: Set[str] = set()
        self.last_balances: Dict[str, float] = {}
        
    async def start(self):
        """Start the monitoring service"""
        self.running = True
        print("✅ Deposit monitor started - polling every 30 seconds")
        
        while self.running:
            try:
                await self.check_all_deposits()
                await self.update_confirmations()
            except Exception as e:
                print(f"❌ Error in deposit monitor loop: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the monitoring service"""
        self.running = False
        print("🛑 Deposit monitor stopped")
    
    async def check_all_deposits(self):
        """Check all user wallets for new deposits"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('SELECT user_id, deposit_address FROM user_wallets')
            else:
                cursor.execute('SELECT user_id, deposit_address FROM user_wallets')
            
            wallets = cursor.fetchall()
            conn.close()
            
            for wallet in wallets:
                wallet_dict = dict(wallet)
                user_id = wallet_dict['user_id']
                address = wallet_dict['deposit_address']
                
                await self.check_wallet_balance(user_id, address)
                
        except Exception as e:
            print(f"Error checking deposits: {e}")
    
    async def check_wallet_balance(self, user_id: int, address: str):
        """Check a single wallet for balance changes using event scanning"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    SELECT COALESCE(MAX(block_number), 0) as last_block
                    FROM deposits 
                    WHERE user_id = %s
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COALESCE(MAX(block_number), 0) as last_block
                    FROM deposits 
                    WHERE user_id = ?
                ''', (user_id,))
            
            row = cursor.fetchone()
            last_block = dict(row)['last_block']
            conn.close()
            
            from_block = max(last_block + 1, self.w3.eth.block_number - 1000)
            
            transfers = self.w3_service.get_usdc_transfers_to_address(
                to_address=address,
                from_block=from_block,
                to_block='latest'
            )
            
            for transfer in transfers:
                await self.record_new_deposit(
                    user_id=user_id,
                    address=address,
                    amount=transfer['amount'],
                    from_address=transfer['from_address'],
                    tx_hash=transfer['tx_hash'],
                    block_number=transfer['block_number']
                )
                
        except Exception as e:
            print(f"Error checking wallet {address}: {e}")
    
    async def record_new_deposit(self, user_id: int, address: str, amount: float, 
                                from_address: str, tx_hash: str, block_number: int):
        """Record a newly detected deposit with actual sender address"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('SELECT id FROM deposits WHERE tx_hash = %s', (tx_hash,))
            else:
                cursor.execute('SELECT id FROM deposits WHERE tx_hash = ?', (tx_hash,))
            
            if cursor.fetchone():
                conn.close()
                return
            
            conn.close()
            
            wallet = self.db.get_user_wallet(user_id)
            if not wallet:
                return
            
            wallet_id = wallet['id']
            
            if not wallet.get('authorized_wallet'):
                success = self.db.set_authorized_wallet(user_id, from_address)
                if success:
                    print(f"✅ Set authorized wallet for user {user_id}: {from_address}")
            
            deposit_id = self.db.create_deposit(
                user_id=user_id,
                wallet_id=wallet_id,
                tx_hash=tx_hash,
                from_address=from_address,
                to_address=address,
                amount=amount,
                block_number=block_number,
                block_timestamp=int(time.time()),
                status='pending'
            )
            
            print(f"✅ New deposit detected: {amount} USDC from {from_address} for user {user_id} (deposit_id: {deposit_id})")
            
        except Exception as e:
            print(f"Error recording deposit: {e}")
    
    async def update_confirmations(self):
        """Update confirmation counts and credit balances for confirmed deposits"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    SELECT id, user_id, amount, block_number 
                    FROM deposits 
                    WHERE status = 'pending'
                ''')
            else:
                cursor.execute('''
                    SELECT id, user_id, amount, block_number 
                    FROM deposits 
                    WHERE status = 'pending'
                ''')
            
            pending = cursor.fetchall()
            conn.close()
            
            current_block = self.w3.eth.block_number
            
            for deposit in pending:
                deposit_dict = dict(deposit)
                deposit_id = deposit_dict['id']
                user_id = deposit_dict['user_id']
                amount = float(deposit_dict['amount'])
                block_number = deposit_dict['block_number']
                
                confirmations = current_block - block_number
                
                conn = self.db.get_connection()
                cursor = conn.cursor()
                
                if self.db.is_postgresql:
                    cursor.execute('''
                        UPDATE deposits 
                        SET confirmations = %s 
                        WHERE id = %s
                    ''', (confirmations, deposit_id))
                else:
                    cursor.execute('''
                        UPDATE deposits 
                        SET confirmations = ? 
                        WHERE id = ?
                    ''', (confirmations, deposit_id))
                
                conn.commit()
                conn.close()
                
                if confirmations >= self.confirmation_threshold:
                    await self.confirm_deposit(deposit_id, user_id, amount)
                    
        except Exception as e:
            print(f"Error updating confirmations: {e}")
    
    async def confirm_deposit(self, deposit_id: int, user_id: int, amount: float):
        """Confirm a deposit and credit user balance"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    UPDATE deposits 
                    SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                ''', (deposit_id,))
            else:
                cursor.execute('''
                    UPDATE deposits 
                    SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (deposit_id,))
            
            conn.commit()
            conn.close()
            
            self.db.credit_user_balance(user_id, amount)
            
            print(f"✅ Deposit {deposit_id} confirmed - credited {amount} USDC to user {user_id}")
            
        except Exception as e:
            print(f"Error confirming deposit: {e}")
