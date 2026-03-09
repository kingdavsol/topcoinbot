"""
Encryption utilities for securing sensitive data.

This module provides AES-256-GCM encryption for:
- Private keys (Web3 wallets)
- Exchange API credentials
- Any other sensitive configuration data

Uses environment variable ENCRYPTION_KEY for the master key.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Tuple

class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256-GCM"""
    
    def __init__(self):
        """Initialize encryption service with master key from environment"""
        master_key = os.getenv("ENCRYPTION_KEY")
        
        if not master_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable must be set. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        
        salt = b"coinpicker_salt_v1"  # Fixed salt for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
        )
        self.key = kdf.derive(master_key.encode())
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded string containing: nonce (12 bytes) + ciphertext + tag (16 bytes)
        """
        if not plaintext:
            return ""
        
        nonce = os.urandom(12)
        
        ciphertext = self.aesgcm.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            None  # No additional authenticated data
        )
        
        encrypted_data = nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with encrypt().
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Original plaintext
            
        Raises:
            ValueError: If decryption fails (wrong key, corrupted data, or tampering)
        """
        if not encrypted_data:
            return ""
        
        try:
            data = base64.b64decode(encrypted_data)
            
            nonce = data[:12]
            
            ciphertext = data[12:]
            
            plaintext_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}. Data may be corrupted or wrong key used.")
    
    def encrypt_key_value_pairs(self, data: dict) -> dict:
        """
        Encrypt all string values in a dictionary.
        
        Args:
            data: Dictionary with string keys and values
            
        Returns:
            Dictionary with same keys but encrypted values
        """
        return {
            key: self.encrypt(str(value)) if value else ""
            for key, value in data.items()
        }
    
    def decrypt_key_value_pairs(self, data: dict) -> dict:
        """
        Decrypt all values in a dictionary.
        
        Args:
            data: Dictionary with encrypted string values
            
        Returns:
            Dictionary with decrypted values
        """
        return {
            key: self.decrypt(value) if value else ""
            for key, value in data.items()
        }


_encryption_service = None

def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_string(plaintext: str) -> str:
    """Encrypt a string using the global encryption service"""
    return get_encryption_service().encrypt(plaintext)

def decrypt_string(encrypted: str) -> str:
    """Decrypt a string using the global encryption service"""
    return get_encryption_service().decrypt(encrypted)
