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
        
        self.public_key: str = rsa_public.save_pkcs1(format='PEM').decode('utf-8')
        self.private_key: str = rsa_private.save_pkcs1(format='PEM').decode('utf-8')
        
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
    
class FernetKeyGenerator:
    def __init__(self):
        self.fernet_key: str = None
        self.fernet_key_hash: str = None
        self.key_id: str = None

    def generate_key(self) -> dict:
        """
        Generate a new Fernet key and compute its SHA-256 hash.

        Returns:
            dict: A dictionary containing the Fernet key, its hash, and a unique ID.
        """
        fernet_key = Fernet.generate_key()
        fernet = Fernet(fernet_key)
        
        # Store the key as a base64 string (Fernet.generate_key() already returns base64-encoded bytes)
        self.fernet_key = fernet_key.decode('utf-8')
        self.fernet_key_hash = hashlib.sha256(fernet_key).hexdigest()
        
        self.key_id = str(uuid.uuid4())
        return {
            "id": self.key_id,
            "fernet_key": self.fernet_key,
            "fernet_instance": fernet,
            "fernet_key_hash": self.fernet_key_hash
        }

    def get_key(self) -> dict:
        """
        Retrieve the generated Fernet key and its hash.

        Returns:
            dict: A dictionary containing the Fernet key, its hash, and a unique ID.
        """
        if not all([self.fernet_key, self.fernet_key_hash, self.key_id]):
            raise ValueError("Fernet key has not been generated yet. Call generate_key() first.")
        
        return {
            "id": self.key_id,
            "fernet_key": self.fernet_key,
            "fernet_instance": Fernet(self.fernet_key.encode('utf-8')),
            "fernet_key_hash": self.fernet_key_hash
        }
    
class HybridKeyGenerator:
    def __init__(self):
        self.rsa_generator = RSAKeyGenerator()
        self.fernet_generator = FernetKeyGenerator()
        self.fernet_key: str = None
        self.rsa_public_key: str = None
        self.rsa_private_key: str = None

    def generate_hybrid_keys(self) -> dict:
        """
        Generate a hybrid key pair combining RSA and Fernet keys.

        Returns:
            dict: A dictionary containing both RSA and Fernet keys and their hashes.
        """
        rsa_keys = self.rsa_generator.generate_keys()
        fernet_keys = self.fernet_generator.generate_key()
        self.fernet_key = self.fernet_generator.fernet_key
        self.rsa_public_key = rsa_keys["public_key"]
        self.rsa_private_key = rsa_keys["private_key"]
        if not all([self.fernet_key, self.rsa_public_key, self.rsa_private_key]):
            raise ValueError("Hybrid keys have not been generated properly.")
        
        return {
            "rsa": rsa_keys,
            "fernet": fernet_keys
        }
    
    def get_keys(self) -> dict:
        """
        Retrieve the generated hybrid keys.

        Returns:
            dict: A dictionary containing both RSA and Fernet keys and their hashes.
        """
        
        return {
            "rsa": {
                "public_key": self.rsa_public_key,
                "private_key": self.rsa_private_key,
            },
            "fernet": self.fernet_key
        }