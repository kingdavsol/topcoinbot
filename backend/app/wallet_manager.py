from web3 import Web3
from eth_account import Account
import os
from typing import Dict, Any, Optional
from .database import Database
from .encryption_service import EncryptionService

class WalletManager:
    """Manages user deposit wallets for the multi-wallet architecture"""
    
    def __init__(self, db: Database):
        self.db = db
        self.encryption = EncryptionService()
        self.w3 = Web3(Web3.HTTPProvider(os.getenv("BASE_RPC_URL", "https://mainnet.base.org")))
        
        self.usdc_contract_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        self.usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        self.usdc_contract = self.w3.eth.contract(
            address=self.usdc_contract_address,
            abi=self.usdc_abi
        )
    
    def generate_user_wallet(self, user_id: int) -> Dict[str, Any]:
        """
        Generate a new wallet for a user
        Returns the deposit address (private key stored encrypted in DB)
        """
        existing = self.db.get_user_wallet(user_id)
        if existing:
            return {
                "success": False,
                "error": "User already has a deposit wallet",
                "address": existing["deposit_address"]
            }
        
        account = Account.create()
        address = account.address
        private_key = account.key.hex()
        
        encrypted_key = self.encryption.encrypt(private_key)
        
        wallet_id = self.db.create_user_wallet(
            user_id=user_id,
            deposit_address=address,
            private_key_encrypted=encrypted_key
        )
        
        self.db.initialize_user_balance(user_id)
        
        return {
            "success": True,
            "wallet_id": wallet_id,
            "deposit_address": address,
            "message": "Deposit wallet created successfully"
        }
    
    def get_user_deposit_address(self, user_id: int) -> Optional[str]:
        """Get user's deposit address (create if doesn't exist)"""
        wallet = self.db.get_user_wallet(user_id)
        
        if not wallet:
            result = self.generate_user_wallet(user_id)
            if result["success"]:
                return result["deposit_address"]
            return None
        
        return wallet["deposit_address"]
    
    def get_wallet_balance(self, user_id: int) -> Dict[str, Any]:
        """Get current on-chain balance of user's deposit wallet"""
        wallet = self.db.get_user_wallet(user_id)
        if not wallet:
            return {"success": False, "error": "User wallet not found"}
        
        address = wallet["deposit_address"]
        
        try:
            usdc_balance_wei = self.usdc_contract.functions.balanceOf(address).call()
            usdc_balance = usdc_balance_wei / 1e6
            
            eth_balance_wei = self.w3.eth.get_balance(address)
            eth_balance = float(self.w3.from_wei(eth_balance_wei, 'ether'))
            
            return {
                "success": True,
                "address": address,
                "usdc_balance": usdc_balance,
                "eth_balance": eth_balance
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch balance: {str(e)}"
            }
    
    def record_deposit(self, user_id: int, tx_hash: str, amount: float, from_address: str) -> Dict[str, Any]:
        """
        Record a deposit transaction (for manual tracking in MVP)
        In full implementation, this would be called by deposit monitoring service
        """
        wallet = self.db.get_user_wallet(user_id)
        if not wallet:
            return {"success": False, "error": "User wallet not found"}
        
        try:
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            block = self.w3.eth.get_block(tx_receipt['blockNumber'])
            
            deposit_id = self.db.create_deposit(
                user_id=user_id,
                wallet_id=wallet['id'],
                tx_hash=tx_hash,
                from_address=from_address,
                to_address=wallet['deposit_address'],
                amount=amount,
                block_number=tx_receipt['blockNumber'],
                block_timestamp=block['timestamp'],
                status='confirmed'
            )
            
            self.db.credit_user_balance(user_id, amount)
            
            return {
                "success": True,
                "deposit_id": deposit_id,
                "amount": amount,
                "message": "Deposit recorded successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to record deposit: {str(e)}"
            }
    
    def withdraw_usdc(self, user_id: int, destination_address: str, amount: float) -> Dict[str, Any]:
        """
        Withdraw USDC from user's deposit wallet to destination address
        SECURITY: Only allows withdrawals to the authorized wallet (first deposit sender)
        """
        try:
            wallet = self.db.get_user_wallet(user_id)
            if not wallet:
                return {"success": False, "error": "User wallet not found"}
            
            authorized_wallet = wallet.get('authorized_wallet')
            if not authorized_wallet:
                return {
                    "success": False, 
                    "error": "No authorized wallet set. Please make a deposit first to establish your withdrawal address."
                }
            
            if not self.w3.is_address(destination_address):
                return {"success": False, "error": "Invalid destination address"}
            
            destination_checksum = self.w3.to_checksum_address(destination_address)
            authorized_checksum = self.w3.to_checksum_address(authorized_wallet)
            
            if destination_checksum.lower() != authorized_checksum.lower():
                return {
                    "success": False,
                    "error": f"Withdrawals only allowed to your authorized wallet: {authorized_checksum}"
                }
            
            balance = self.db.get_user_balance(user_id)
            available = float(balance.get('available_balance', 0))
            
            if amount > available:
                return {"success": False, "error": f"Insufficient balance. Available: {available} USDC"}
            
            if amount < 1.0:
                return {"success": False, "error": "Minimum withdrawal is 1 USDC"}
            
            daily_limit = self._check_daily_withdrawal_limit(user_id, amount)
            if not daily_limit['allowed']:
                return {"success": False, "error": daily_limit['message']}
            
            encrypted_key = wallet['private_key_encrypted']
            private_key = self.encryption.decrypt(encrypted_key)
            
            from eth_account import Account
            account = Account.from_key(private_key)
            
            eth_balance = self.w3.eth.get_balance(account.address)
            if eth_balance == 0:
                return {
                    "success": False, 
                    "error": "No ETH in wallet for gas fees. Please deposit ETH to pay for transaction gas."
                }
            
            decimals = self.usdc_contract.functions.decimals().call()
            amount_wei = int(amount * (10 ** decimals))
            
            nonce = self.w3.eth.get_transaction_count(account.address)
            gas_price = self.w3.eth.gas_price
            
            try:
                gas_estimate = self.usdc_contract.functions.transfer(
                    destination_checksum, amount_wei
                ).estimate_gas({'from': account.address})
            except Exception as e:
                gas_estimate = 65000
            
            usdc_abi_transfer = [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_to", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }
            ]
            usdc_contract_full = self.w3.eth.contract(
                address=self.usdc_contract_address,
                abi=usdc_abi_transfer
            )
            
            transaction = usdc_contract_full.functions.transfer(
                destination_checksum, amount_wei
            ).build_transaction({
                'from': account.address,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': 8453
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    UPDATE balances 
                    SET available_balance = available_balance - %s,
                        total_withdrawn = total_withdrawn + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (amount, amount, user_id))
            else:
                cursor.execute('''
                    UPDATE balances 
                    SET available_balance = available_balance - ?,
                        total_withdrawn = total_withdrawn + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (amount, amount, user_id))
            
            conn.commit()
            conn.close()
            
            self._record_withdrawal(user_id, wallet['id'], tx_hash_hex, destination_checksum, amount)
            
            return {
                "success": True,
                "tx_hash": tx_hash_hex,
                "amount": amount,
                "destination": destination_checksum,
                "message": "Withdrawal transaction broadcast successfully"
            }
            
        except Exception as e:
            print(f"Withdrawal error: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_daily_withdrawal_limit(self, user_id: int, amount: float) -> Dict[str, Any]:
        """Check if withdrawal is within daily limit"""
        try:
            daily_limit = 10000.0
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            if self.db.is_postgresql:
                cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM deposits
                    WHERE user_id = %s 
                    AND status = 'confirmed'
                    AND tx_hash LIKE '0xwd%%'
                    AND DATE(created_at) = CURRENT_DATE
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM deposits
                    WHERE user_id = ? 
                    AND status = 'confirmed'
                    AND tx_hash LIKE '0xwd%'
                    AND DATE(created_at) = DATE('now')
                ''', (user_id,))
            
            row = cursor.fetchone()
            today_total = float(dict(row)['total'])
            conn.close()
            
            if today_total + amount > daily_limit:
                return {
                    "allowed": False,
                    "message": f"Daily withdrawal limit exceeded. Limit: {daily_limit} USDC, Used today: {today_total} USDC"
                }
            
            return {"allowed": True}
            
        except Exception as e:
            print(f"Error checking daily limit: {e}")
            return {"allowed": True}
    
    def _record_withdrawal(self, user_id: int, wallet_id: int, tx_hash: str, 
                          to_address: str, amount: float):
        """Record withdrawal as a deposit with negative amount marker"""
        try:
            import time
            withdrawal_hash = f"0xwd{tx_hash[4:]}"
            
            self.db.create_deposit(
                user_id=user_id,
                wallet_id=wallet_id,
                tx_hash=withdrawal_hash,
                from_address=self.db.get_user_wallet(user_id)['deposit_address'],
                to_address=to_address,
                amount=amount,
                block_number=self.w3.eth.block_number,
                block_timestamp=int(time.time()),
                status='confirmed'
            )
        except Exception as e:
            print(f"Error recording withdrawal: {e}")
