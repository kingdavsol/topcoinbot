from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
import secrets

class EncryptionService:
    """Service for encrypting/decrypting sensitive data like private keys"""
    
    def __init__(self):
        master_key = os.getenv("WALLET_ENCRYPTION_KEY")
        
        if not master_key:
            master_key = Fernet.generate_key().decode()
            print(f"WARNING: Generated temporary encryption key. Set WALLET_ENCRYPTION_KEY in production!")
            print(f"WALLET_ENCRYPTION_KEY={master_key}")
        
        try:
            self.cipher = Fernet(master_key.encode() if isinstance(master_key, str) else master_key)
        except Exception:
            salt = os.getenv("ENCRYPTION_SALT", "coinpicker-salt-change-in-prod").encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
            self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string"""
        return self.cipher.decrypt(ciphertext.encode()).decode()
