import rsa

def encrypt_message(message: str, public_key: str) -> bytes:
    """
    Encrypt a message using the provided RSA public key.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        bytes: The encrypted message as bytes.
    """
    rsa_public = rsa.PublicKey.load_pkcs1(public_key.encode('utf-8'))
    encrypted_message = rsa.encrypt(message.encode('utf-8'), rsa_public)
    return encrypted_message

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

    Args:
        encrypted_message (bytes): The encrypted message as bytes.
        private_key (str): The RSA private key in PEM format.

    Returns:
        str: The decrypted message.
    """
    rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
    decrypted_message = rsa.decrypt(encrypted_message, rsa_private).decode('utf-8')
    return decrypted_message