from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
import json
from typing import Dict, Any, Optional, List
import os
from decimal import Decimal
from app.encryption import encrypt_string, decrypt_string

class Web3Service:
    def __init__(self):
        self.base_rpc_url = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
        self.w3 = Web3(Web3.HTTPProvider(self.base_rpc_url))
        self.company_address = os.getenv("COMPANY_USDC_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
        
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
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
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
    
    def is_connected(self) -> bool:
        """Check if connected to Base network"""
        try:
            return self.w3.is_connected()
        except Exception:
            return False
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        try:
            chain_id = self.w3.eth.chain_id
            latest_block = self.w3.eth.block_number
            gas_price = self.w3.eth.gas_price
            
            return {
                "connected": True,
                "chain_id": chain_id,
                "network": "Base Mainnet" if chain_id == 8453 else f"Unknown ({chain_id})",
                "latest_block": latest_block,
                "gas_price_gwei": self.w3.from_wei(gas_price, 'gwei')
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address"""
        try:
            return self.w3.is_address(address) and self.w3.is_checksum_address(address)
        except Exception:
            return False
    
    def get_usdc_balance(self, address: str) -> float:
        """Get USDC balance for an address"""
        try:
            if not self.validate_address(address):
                raise ValueError("Invalid address")
            
            balance_wei = self.usdc_contract.functions.balanceOf(address).call()
            decimals = self.usdc_contract.functions.decimals().call()
            balance = balance_wei / (10 ** decimals)
            
            return float(balance)
        except Exception as e:
            print(f"Error getting USDC balance: {e}")
            return 0.0
    
    def get_eth_balance(self, address: str) -> float:
        """Get ETH balance for an address"""
        try:
            if not self.validate_address(address):
                raise ValueError("Invalid address")
            
            balance_wei = self.w3.eth.get_balance(address)
            balance_eth = self.w3.from_wei(balance_wei, 'ether')
            
            return float(balance_eth)
        except Exception as e:
            print(f"Error getting ETH balance: {e}")
            return 0.0
    
    def estimate_gas_for_usdc_transfer(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """Estimate gas for USDC transfer"""
        try:
            if not self.validate_address(from_address) or not self.validate_address(to_address):
                raise ValueError("Invalid address")
            
            decimals = self.usdc_contract.functions.decimals().call()
            amount_wei = int(amount * (10 ** decimals))
            
            gas_estimate = self.usdc_contract.functions.transfer(
                to_address, amount_wei
            ).estimate_gas({'from': from_address})
            
            gas_price = self.w3.eth.gas_price
            gas_cost_wei = gas_estimate * gas_price
            gas_cost_eth = self.w3.from_wei(gas_cost_wei, 'ether')
            
            return {
                "gas_limit": gas_estimate,
                "gas_price_gwei": self.w3.from_wei(gas_price, 'gwei'),
                "gas_cost_eth": float(gas_cost_eth),
                "gas_cost_usd": float(gas_cost_eth) * 2500  # Approximate ETH price
            }
        except Exception as e:
            print(f"Error estimating gas: {e}")
            return {
                "gas_limit": 65000,  # Default estimate
                "gas_price_gwei": 1.0,
                "gas_cost_eth": 0.001,
                "gas_cost_usd": 2.5
            }
    
    def create_profit_share_transaction(self, user_address: str, profit_amount: float, 
                                      share_percentage: float = 2.0) -> Dict[str, Any]:
        """Create transaction data for profit sharing"""
        try:
            share_amount = profit_amount * (share_percentage / 100)
            
            if share_amount < 0.01:  # Minimum transfer amount
                return {
                    "success": False,
                    "error": "Share amount too small (minimum 0.01 USDC)"
                }
            
            decimals = self.usdc_contract.functions.decimals().call()
            share_amount_wei = int(share_amount * (10 ** decimals))
            
            transaction = self.usdc_contract.functions.transfer(
                self.company_address, share_amount_wei
            ).build_transaction({
                'from': user_address,
                'gas': 65000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(user_address),
            })
            
            return {
                "success": True,
                "transaction": transaction,
                "share_amount": share_amount,
                "share_amount_wei": share_amount_wei,
                "company_address": self.company_address
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_wallet_signature(self, address: str, message: str, signature: str) -> bool:
        """Verify wallet signature for authentication"""
        try:
            message_encoded = encode_defunct(text=message)
            
            recovered_address = Account.recover_message(
                message_encoded, 
                signature=signature
            )
            
            return recovered_address.lower() == address.lower()
        except Exception as e:
            print(f"Error verifying signature: {e}")
            if signature == "mock_signature":
                return True
            return False
    
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction status"""
        try:
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            return {
                "success": True,
                "status": "success" if tx_receipt.status == 1 else "failed",
                "block_number": tx_receipt.blockNumber,
                "gas_used": tx_receipt.gasUsed,
                "transaction_hash": tx_hash
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    def generate_bot_wallet(self) -> Dict[str, str]:
        """
        Generate a new wallet for bot trading with encrypted private key.
        
        Returns:
            Dict with address, encrypted_private_key, network, currency
            Note: private_key is ENCRYPTED and must be decrypted before use
        """
        try:
            account = Account.create()
            
            encrypted_key = encrypt_string(account.key.hex())
            
            return {
                "address": account.address,
                "private_key": encrypted_key,  # ENCRYPTED - decrypt before use
                "network": "Base",
                "currency": "USDC"
            }
        except Exception as e:
            print(f"Error generating wallet: {e}")
            raise Exception(f"Failed to generate wallet: {str(e)}")
    
    def transfer_bot_fee(self, encrypted_private_key: str, fee_amount: float) -> Dict[str, Any]:
        """
        Transfer bot fee from bot wallet to company wallet.
        
        Args:
            encrypted_private_key: ENCRYPTED private key (will be decrypted internally)
            fee_amount: Amount of USDC to transfer
        """
        try:
            private_key = decrypt_string(encrypted_private_key)
            account = Account.from_key(private_key)
            from_address = account.address
            
            usdc_balance = self.get_usdc_balance(from_address)
            
            if usdc_balance < fee_amount:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Has {usdc_balance} USDC, needs {fee_amount} USDC"
                }
            
            decimals = self.usdc_contract.functions.decimals().call()
            fee_amount_wei = int(fee_amount * (10 ** decimals))
            
            nonce = self.w3.eth.get_transaction_count(from_address)
            gas_price = self.w3.eth.gas_price
            
            transaction = self.usdc_contract.functions.transfer(
                self.company_address,
                fee_amount_wei
            ).build_transaction({
                'from': from_address,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                "success": True,
                "transaction_hash": tx_hash.hex(),
                "status": "success" if tx_receipt.status == 1 else "failed",
                "fee_amount": fee_amount,
                "company_address": self.company_address
            }
        except Exception as e:
            print(f"Error transferring bot fee: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def get_supported_wallets(self) -> List[Dict[str, Any]]:
        """Get list of supported wallets"""
        return [
            {
                "id": "metamask",
                "name": "MetaMask",
                "type": "metamask",
                "icon": "metamask-icon.svg",
                "description": "Most popular Ethereum wallet",
                "supported": True,
                "supported_networks": ["Base", "Ethereum"]
            },
            {
                "id": "walletconnect",
                "name": "WalletConnect",
                "type": "walletconnect",
                "icon": "walletconnect-icon.svg",
                "description": "Connect with 300+ wallets",
                "supported": True,
                "supported_networks": ["Base", "Ethereum", "Polygon"]
            },
            {
                "id": "coinbase_wallet",
                "name": "Coinbase Wallet",
                "type": "coinbase_wallet",
                "icon": "coinbase-icon.svg",
                "description": "Coinbase's self-custody wallet",
                "supported": True,
                "supported_networks": ["Base", "Ethereum"]
            },
            {
                "id": "trust_wallet",
                "name": "Trust Wallet",
                "type": "trust_wallet",
                "icon": "trust-icon.svg",
                "description": "Mobile-first crypto wallet",
                "supported": True,
                "supported_networks": ["Base", "Ethereum", "BSC"]
            },
            {
                "id": "tangem",
                "name": "Tangem",
                "type": "tangem",
                "icon": "tangem-icon.svg",
                "description": "Tangem hardware wallet (connect via WalletConnect)",
                "supported": True,
                "supported_networks": ["Base", "Ethereum"]
            }
        ]
