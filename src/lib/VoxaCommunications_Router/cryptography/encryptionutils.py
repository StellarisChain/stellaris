import rsa
import os
import json
import base64
import hashlib
from lib.VoxaCommunications_Router.cryptography.keyutils import FernetKeyGenerator
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from util.jsonutils import serialize_for_json
#from util.filereader import read_key_file
from util.logging import log

# TODO: Fernet should be generated each time, not read from file

logger = log()

def generate_fernet_key() -> str:
    """
    Generate a Fernet key.
    Returns:
        str: The generated Fernet key as a base64-encoded string.
    """
    fernet_key_generator = FernetKeyGenerator()
    fernet_key = dict(fernet_key_generator.generate_key()).get("fernet_key")
    
    return fernet_key # should be base64-encoded string

def encrypt_fernet(public_key: str, fernet_key_str: str) -> bytes:
    """
    Encrypt the Fernet key using RSA public key.
    Args:
        public_key (str): The RSA public key in PEM format.
    Returns:
        bytes: The encrypted Fernet key as bytes."""
    rsa_public = rsa.PublicKey.load_pkcs1(public_key.encode('utf-8'))
    fernet_encrypted = rsa.encrypt(fernet_key_str.encode('utf-8'), rsa_public)
    return fernet_encrypted

def encrypt_message(message: str, public_key: str, fernet_key_str: str) -> bytes:
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
    
    # The key from file should be a base64-encoded string that we can use directly
    fernet = Fernet(fernet_key_str.encode('utf-8'))

    message_encrypted = fernet.encrypt(message_bytes)
    
    return message_encrypted

def encrypt_route_message(message: dict | str, public_key: str) -> tuple[bytes, str, bytes]:
    """
    Encrypt a message using the provided RSA public key and return the encrypted message along with its hash.

    Args:
        message (dict|str): The message to encrypt. Can be either a dictionary or a string.
        public_key (str): The RSA public key in PEM format.

    Returns:
        tuple: A tuple containing the encrypted message as bytes and the original message's SHA-256 hash as a hex string.
    """

    fernet_key = generate_fernet_key()
    encrypted_fernet: bytes = encrypt_fernet(public_key, fernet_key)
    
    # Process the message to ensure encrypted_fernet is added in all cases
    if isinstance(message, dict):
        # For dictionary, make a copy and add encrypted_fernet directly
        message_dict = message.copy()  # Make a copy to avoid modifying the original
        message_dict["encrypted_fernet"] = serialize_for_json(encrypted_fernet)
        json_str_message: str = json.dumps(message_dict, indent=2)
    else:
        # For string, convert to dict first, add encrypted_fernet, then back to string
        message_dict = json.loads(message)
        message_dict["encrypted_fernet"] = serialize_for_json(encrypted_fernet)
        json_str_message: str = json.dumps(message_dict, indent=2)

    encrypted_message: bytes = encrypt_message(json_str_message, public_key, fernet_key)
    message_hash = hashlib.sha256(json_str_message.encode('utf-8')).hexdigest()  # Original message's hash, used to verify integrity
    return encrypted_message, message_hash, encrypted_fernet    

def encrypt_message_return_hash(message: str, public_key: str) -> tuple[bytes, str, bytes]:
    """
    Encrypt a message using the provided RSA public key and return the encrypted message along with its hash.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        tuple: A tuple containing the encrypted message as bytes and the orginal message's SHA-256 hash as a hex string.
    """
    fernet_key = generate_fernet_key()
    encrypted_message = encrypt_message(message, public_key, fernet_key)
    encrypted_fernet = encrypt_fernet(public_key, fernet_key)
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