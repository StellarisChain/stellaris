import secrets
import rsa
import hashlib
import base64
import uuid
from typing import Optional
from cryptography.fernet import Fernet

class RSAKeyGenerator:
    def __init__(self):
        self.public_key: str = None
        self.private_key: str = None
        self.public_key_hash: str = None
        self.private_key_hash: str = None
        self.key_id: str = None

    def generate_keys(self) -> dict:
        """
        Generate a new RSA key pair and compute their SHA-256 hashes.

        Returns:
            dict: A dictionary containing the public key, private key, their hashes, and a unique ID.
        """
        rsa_public, rsa_private = rsa.newkeys(2048)
        
        self.public_key = rsa_public.save_pkcs1().decode('utf-8')
        self.private_key = rsa_private.save_pkcs1().decode('utf-8')
        
        self.public_key_hash = hashlib.sha256(self.public_key.encode('utf-8')).hexdigest()
        self.private_key_hash = hashlib.sha256(self.private_key.encode('utf-8')).hexdigest()
        
        self.key_id = str(uuid.uuid4())
        return {
            "id": self.key_id,
            "public_key": self.public_key,
            "private_key": self.private_key,
            "public_key_hash": self.public_key_hash,
            "private_key_hash": self.private_key_hash
        }
    
    def get_keys(self) -> dict:
        """
        Retrieve the generated RSA keys and their hashes.

        Returns:
            dict: A dictionary containing the public key, private key, their hashes, and a unique ID.
        """
        if not all([self.public_key, self.private_key, self.public_key_hash, self.private_key_hash, self.key_id]):
            raise ValueError("Keys have not been generated yet. Call generate_keys() first.")
        
        return {
            "id": self.key_id,
            "public_key": self.public_key,
            "private_key": self.private_key,
            "public_key_hash": self.public_key_hash,
            "private_key_hash": self.private_key_hash
        }
    
    def compare_hash(self, public_key_hash: Optional[str] = None, private_key_hash: Optional[str] = None) -> bool:
        """
        Compare the provided hashes with the stored key hashes.

        Args:
            public_key_hash (str): The SHA-256 hash of the public key to compare.
            private_key_hash (str): The SHA-256 hash of the private key to compare.

        Returns:
            bool: True if both hashes match, False otherwise.
        """
        if public_key_hash and public_key_hash != self.public_key_hash:
            return False
        if private_key_hash and private_key_hash != self.private_key_hash:
            return False
        return True