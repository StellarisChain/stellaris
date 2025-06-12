import rsa
import os
import json
import base64
import hashlib
from util.filereader import read_key_file
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def encrypt_message(message: str, public_key: str) -> tuple[bytes, bytes]:
    """
    Encrypt a message using hybrid encryption (AES + RSA).
    For large messages, uses AES for the message and RSA for the AES key.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        bytes: The encrypted message as bytes (JSON containing encrypted data and key).
    """
    message_bytes = message.encode('utf-8')
    
    # For small messages that fit in RSA, use direct RSA encryption
    rsa_public = rsa.PublicKey.load_pkcs1(public_key.encode('utf-8'))
    fernet_key_str = read_key_file("fernet")
    
    # The key from file should be a base64-encoded string that we can use directly
    fernet = Fernet(fernet_key_str.encode('utf-8'))

    fernet_encrypted = rsa.encrypt(fernet_key_str.encode('utf-8'), rsa_public)
    message_encrypted = fernet.encrypt(message_bytes)
    
    return message_encrypted, fernet_encrypted

def encrypt_message_return_hash(message: str, public_key: str) -> tuple[bytes, str, bytes]:
    """
    Encrypt a message using the provided RSA public key and return the encrypted message along with its hash.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        tuple: A tuple containing the encrypted message as bytes and the orginal message's SHA-256 hash as a hex string.
    """
    encrypted_message, encrypted_fernet = encrypt_message(message, public_key)
    message_hash = hashlib.sha256(message.encode('utf-8')).hexdigest() # Original messages hash, used to verify integrity
    return encrypted_message, message_hash, encrypted_fernet

def decrypt_message(encrypted_message: bytes, private_key: str, encrypted_fernet: bytes) -> str:
    """
    Decrypt a message using the provided RSA private key.
    Handles both direct RSA and hybrid encryption.

    Args:
        encrypted_message (bytes): The encrypted message as bytes.
        private_key (str): The RSA private key in PEM format.

    Returns:
        str: The decrypted message.
    """
    rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
    fernet_key = rsa.decrypt(encrypted_fernet, rsa_private)
    fernet = Fernet(fernet_key)

    decrypted_message = fernet.decrypt(encrypted_message)
    decrypted_message = decrypted_message.decode('utf-8')
    
    return decrypted_message