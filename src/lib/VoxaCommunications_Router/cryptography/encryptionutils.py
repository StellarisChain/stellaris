import rsa
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def encrypt_message(message: str, public_key: str) -> bytes:
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
    max_rsa_size = (rsa_public.n.bit_length() + 7) // 8 - 11  # PKCS1 padding overhead
    
    if len(message_bytes) <= max_rsa_size:
        # Direct RSA encryption for small messages
        encrypted_message = rsa.encrypt(message_bytes, rsa_public)
        return encrypted_message
    else:
        # Hybrid encryption for large messages
        # Generate a random AES key
        aes_key = Fernet.generate_key()
        fernet = Fernet(aes_key)
        
        # Encrypt the message with AES
        encrypted_message = fernet.encrypt(message_bytes)
        
        # Encrypt the AES key with RSA
        encrypted_aes_key = rsa.encrypt(aes_key, rsa_public)
        
        # Create a hybrid payload
        hybrid_payload = {
            'type': 'hybrid',
            'encrypted_key': base64.b64encode(encrypted_aes_key).decode('utf-8'),
            'encrypted_message': base64.b64encode(encrypted_message).decode('utf-8')
        }
        
        return json.dumps(hybrid_payload).encode('utf-8')

def encrypt_message_return_hash(message: str, public_key: str) -> tuple[bytes, str]:
    """
    Encrypt a message using the provided RSA public key and return the encrypted message along with its hash.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        tuple: A tuple containing the encrypted message as bytes and the orginal message's SHA-256 hash as a hex string.
    """
    encrypted_message = encrypt_message(message, public_key)
    message_hash = rsa.compute_hash(message, 'SHA-256').hex() # Orginal messages hash, used to verify integrity
    return encrypted_message, message_hash

def decrypt_message(encrypted_message: bytes, private_key: str) -> str:
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
    
    try:
        # Try to parse as hybrid payload first
        payload_str = encrypted_message.decode('utf-8')
        payload = json.loads(payload_str)
        
        if payload.get('type') == 'hybrid':
            # Hybrid decryption
            encrypted_aes_key = base64.b64decode(payload['encrypted_key'])
            encrypted_message_data = base64.b64decode(payload['encrypted_message'])
            
            # Decrypt the AES key with RSA
            aes_key = rsa.decrypt(encrypted_aes_key, rsa_private)
            
            # Decrypt the message with AES
            fernet = Fernet(aes_key)
            decrypted_message = fernet.decrypt(encrypted_message_data)
            
            return decrypted_message.decode('utf-8')
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        # Fall back to direct RSA decryption
        pass
    
    # Direct RSA decryption
    decrypted_message = rsa.decrypt(encrypted_message, rsa_private).decode('utf-8')
    return decrypted_message