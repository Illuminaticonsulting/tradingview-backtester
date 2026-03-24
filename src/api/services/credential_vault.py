"""
Credential vault - Encrypted storage for API keys and cookies.
Uses Fernet symmetric encryption (AES-128).
"""
from cryptography.fernet import Fernet
from typing import Optional
import base64
import os

from ..config import get_settings

settings = get_settings()


class CredentialVault:
    """Secure credential storage with encryption at rest."""
    
    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize Fernet cipher with key from settings or generate one."""
        key = settings.encryption_key
        
        if not key:
            # Generate a key if not provided (for development)
            # In production, this should be set via BACKTESTER_ENCRYPTION_KEY env var
            key = Fernet.generate_key().decode()
            print(f"WARNING: Generated encryption key. Set BACKTESTER_ENCRYPTION_KEY={key}")
        
        # Ensure key is proper Fernet format
        try:
            if len(key) == 32:
                # Raw 32-byte key, encode to base64
                key = base64.urlsafe_b64encode(key.encode()[:32]).decode()
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            # Generate fresh key on error
            self._fernet = Fernet(Fernet.generate_key())
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted value."""
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ""
    
    def rotate_key(self, old_key: str, new_key: str, ciphertext: str) -> str:
        """Re-encrypt data with a new key."""
        old_fernet = Fernet(old_key.encode())
        new_fernet = Fernet(new_key.encode())
        
        plaintext = old_fernet.decrypt(ciphertext.encode())
        return new_fernet.encrypt(plaintext).decode()


# Singleton instance
vault = CredentialVault()


def encrypt_credential(value: str) -> str:
    """Encrypt a credential value."""
    return vault.encrypt(value)


def decrypt_credential(value: str) -> str:
    """Decrypt a credential value."""
    return vault.decrypt(value)


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()
