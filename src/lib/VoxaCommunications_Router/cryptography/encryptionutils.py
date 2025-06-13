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
    rsa_public = rsa.PublicKey.load_pkcs1(public_key.encode('utf-8'), format='PEM')
    fernet_encrypted = rsa.encrypt(fernet_key_str.encode('utf-8'), rsa_public)
    return fernet_encrypted

def encrypt_message(message: str | dict, public_key: str, fernet_key_str: str) -> bytes:
    """
    Encrypt a message using hybrid encryption (AES + RSA).
    For large messages, uses AES for the message and RSA for the AES key.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        bytes: The encrypted message as bytes (JSON containing encrypted data and key).
    """
    if isinstance(message, dict):
        # For dictionary, make a copy and add encrypted_fernet directly
        message_dict = message.copy()  # Make a copy to avoid modifying the original
        message: str = json.dumps(message_dict, indent=2)
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

def encrypt_message_return_hash(message: str | dict, public_key: str) -> tuple[bytes, str, bytes]:
    """
    Encrypt a message using the provided RSA public key and return the encrypted message along with its hash.

    Args:
        message (str): The message to encrypt.
        public_key (str): The RSA public key in PEM format.

    Returns:
        tuple: A tuple containing the encrypted message as bytes and the orginal message's SHA-256 hash as a hex string.
    """
    if isinstance(message, dict):
        # For dictionary, make a copy and add encrypted_fernet directly
        message_dict = message.copy()  # Make a copy to avoid modifying the original
        message: str = json.dumps(message_dict, indent=2)
    fernet_key = generate_fernet_key()
    encrypted_message = encrypt_message(message, public_key, fernet_key)
    encrypted_fernet = encrypt_fernet(public_key, fernet_key)
    message_hash = hashlib.sha256(message.encode('utf-8')).hexdigest() # Original messages hash, used to verify integrity
    return encrypted_message, message_hash, encrypted_fernet

def extract_public_key_from_private(private_key: str) -> str:
    """
    Extract the public key from a private key.
    
    Args:
        private_key (str): The RSA private key in PEM format.
    
    Returns:
        str: The corresponding public key in PEM format.
    """
    try:
        # Ensure the private key is properly formatted
        if not private_key.strip():
            logger.error("Private key is empty")
            return None
            
        # Clean up the private key string
        private_key_clean = private_key.strip()
        
        # Try to load the private key - handle both PKCS1 and PKCS8 formats
        try:
            # First try PKCS1 format (default RSA format)
            rsa_private = rsa.PrivateKey.load_pkcs1(private_key_clean.encode('utf-8'))
        except Exception as pkcs1_error:
            logger.debug(f"PKCS1 format failed: {pkcs1_error}")
            try:
                # Try PKCS8 format
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.backends import default_backend
                
                # Load PKCS8 private key
                crypto_private_key = serialization.load_pem_private_key(
                    private_key_clean.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
                
                # Convert to RSA format
                private_numbers = crypto_private_key.private_numbers()
                rsa_private = rsa.PrivateKey(
                    private_numbers.private_value,
                    private_numbers.public_numbers.e,
                    private_numbers.p,
                    private_numbers.q
                )
                
            except Exception as pkcs8_error:
                logger.error(f"Both PKCS1 and PKCS8 parsing failed. PKCS1: {pkcs1_error}, PKCS8: {pkcs8_error}")
                return None
        
        # Extract the public key
        rsa_public = rsa.PublicKey(rsa_private.n, rsa_private.e)
        
        # Convert to PEM format
        public_key_pem = rsa_public.save_pkcs1().decode('utf-8')
        
        return public_key_pem
        
    except Exception as e:
        logger.error(f"Failed to extract public key from private key: {str(e)}")
        logger.error(f"Private key preview: {private_key[:100] if private_key else 'None'}...")
        return None

def decrypt_message(encrypted_message: bytes, private_key: str, encrypted_fernet: bytes) -> str:
    """
    Decrypt a message using the provided RSA private key.
    Handles both direct RSA and hybrid encryption.

    Args:
        encrypted_message (bytes): The encrypted message as bytes.
        private_key (str): The RSA private key in PEM format.
        encrypted_fernet (bytes): The encrypted Fernet key.

    Returns:
        str: The decrypted message.
    """
    try:
        # Load the RSA private key
        rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
        logger.debug(f"Successfully loaded RSA private key")
        
        # Extract public key from private key for comparison
        extracted_public_key = extract_public_key_from_private(private_key)
        rsa_public = rsa.PublicKey.load_pkcs1(extracted_public_key.encode('utf-8')) if extracted_public_key else None
        if extracted_public_key:
            logger.debug(f"Extracted public key from private key: {extracted_public_key[:50]}...")
        
        # Decrypt the Fernet key using RSA
        try:
            fernet_key = rsa.decrypt(encrypted_fernet, rsa_private)
            logger.debug(f"Successfully decrypted Fernet key, length: {len(fernet_key)}")
        except Exception as e:
            logger.error(f"Failed to decrypt Fernet key with RSA: {str(e)}")
            logger.error(f"Private key hash: {hashlib.sha256(private_key.encode()).hexdigest()[:16]}...")
            logger.error(f"Private key (first 50 chars): {private_key[:50]}")
            logger.error(f"Public key hash: {hashlib.sha256(extracted_public_key.encode()).hexdigest()[:16]}...")
            logger.error(f"Encrypted fernet length: {len(encrypted_fernet)}")
            logger.error(f"Encrypted fernet (first 50 chars): {encrypted_fernet[:50]}")
            
            # Additional debugging information
            if extracted_public_key:
                logger.error(f"Expected public key (from private): {extracted_public_key[:100]}...")
                logger.warning("Attempting to encrypt test message with extracted public key to verify key pair...")
                try:
                    test_message = b"test_key_validation"
                    test_encrypted = rsa.encrypt(test_message, rsa_public)
                    test_decrypted = rsa.decrypt(test_encrypted, rsa_private)
                    if test_decrypted == test_message:
                        logger.info("Key pair is valid - encryption/decryption test succeeded")
                    else:
                        logger.error("Key pair is invalid - encryption/decryption test failed")
                except Exception as test_error:
                    logger.error(f"Key pair test failed: {str(test_error)}")
            
            raise Exception(f"RSA decryption failed - key mismatch or corrupted data: {str(e)}")
        
        # Use the decrypted Fernet key to decrypt the message
        try:
            fernet = Fernet(fernet_key)
            decrypted_message = fernet.decrypt(encrypted_message)
            decrypted_message = decrypted_message.decode('utf-8')
            logger.debug(f"Successfully decrypted message, length: {len(decrypted_message)}")
            return decrypted_message
        except Exception as e:
            logger.error(f"Failed to decrypt message with Fernet: {str(e)}")
            raise Exception(f"Fernet decryption failed: {str(e)}")
            
    except Exception as e:
        if "RSA decryption failed" in str(e) or "Fernet decryption failed" in str(e):
            raise  # Re-raise our custom exceptions
        logger.error(f"Unexpected error in decrypt_message: {str(e)}")
        raise Exception(f"Decryption failed: {str(e)}")

def validate_rsa_key_pair(public_key: str, private_key: str) -> bool:
    """
    Validate that a public and private key pair match by testing encryption/decryption.
    
    Args:
        public_key (str): The RSA public key in PEM format.
        private_key (str): The RSA private key in PEM format.
    
    Returns:
        bool: True if the keys match, False otherwise.
    """
    try:
        # Load the keys
        rsa_public = rsa.PublicKey.load_pkcs1(public_key.encode('utf-8'))
        rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
        
        # Test message
        test_message = b"test_key_validation"
        
        # Encrypt with public key
        encrypted = rsa.encrypt(test_message, rsa_public)
        
        # Try to decrypt with private key
        decrypted = rsa.decrypt(encrypted, rsa_private)
        
        # Check if the decrypted message matches the original
        return decrypted == test_message
        
    except Exception as e:
        logger.debug(f"Key validation failed: {str(e)}")
        return False

def find_correct_private_key_for_block(current_block: dict, encrypted_fernet: bytes) -> str:
    """
    Find the correct private key for decrypting a block by testing all available keys.
    
    Args:
        current_block (dict): The current routing block
        encrypted_fernet (bytes): The encrypted Fernet key to test against
    
    Returns:
        str: The correct private key if found, None otherwise
    """
    import os
    from util.filereader import read_key_file
    
    logger.info("Searching for correct private key...")
    
    # Get all available key files
    key_directories = ["data/rri", "data/local", "data/nri"]
    
    for key_dir in key_directories:
        if not os.path.exists(key_dir):
            continue
            
        key_files = [f for f in os.listdir(key_dir) if f.endswith('.key')]
        logger.info(f"Testing {len(key_files)} keys from {key_dir}")
        
        for key_file in key_files:
            try:
                # Extract relay ID from filename
                relay_id = key_file.replace('.key', '')
                
                # Load the private key
                private_key = read_key_file(relay_id, key_dir.split('/')[-1])
                
                # Test if this key can decrypt the encrypted_fernet
                try:
                    rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
                    test_decrypt = rsa.decrypt(encrypted_fernet, rsa_private)
                    
                    logger.info(f"SUCCESS: Found matching private key for relay {relay_id}")
                    
                    # Additional verification: extract public key and compare with block's public key
                    extracted_public = extract_public_key_from_private(private_key)
                    if extracted_public:
                        block_public = current_block.get("public_key")
                        if block_public and extracted_public.strip() == block_public.strip():
                            logger.info("Confirmed: Public keys match!")
                        else:
                            logger.warning("Note: This key decrypts the data but doesn't match the block's public key - this is expected in the routing chain encryption design")
                    
                    return private_key
                    
                except Exception:
                    # This key doesn't work, continue to next
                    pass
                    
            except Exception as e:
                logger.debug(f"Failed to test key {key_file}: {str(e)}")
                continue
    
    logger.error("No matching private key found in any directory")
    return None

def find_correct_key_using_routing_logic(current_block: dict, encrypted_fernet: bytes) -> str:
    """
    Find the correct private key based on routing chain encryption logic.
    In the routing chain, each block is encrypted with the NEXT block's public key,
    so we need to find the private key that corresponds to the public key used for encryption.
    
    Args:
        current_block (dict): The current routing block
        encrypted_fernet (bytes): The encrypted Fernet key to test against
    
    Returns:
        str: The correct private key if found, None otherwise
    """
    import os
    from util.filereader import read_key_file
    
    logger.info("Finding correct key using routing chain encryption logic...")
    
    # In routing chain encryption, the current block was encrypted with the next block's public key
    # The public key in the current block is NOT the one used for encryption - it's just metadata
    # We need to find which relay's private key can actually decrypt this encrypted_fernet
    
    logger.info("Testing all available private keys to find the one that can decrypt this block...")
    
    # Get all available key files from all directories
    key_directories = ["data/rri", "data/local", "data/nri"]
    tested_keys = []
    
    for key_dir in key_directories:
        if not os.path.exists(key_dir):
            logger.debug(f"Directory {key_dir} does not exist, skipping...")
            continue
            
        key_files = [f for f in os.listdir(key_dir) if f.endswith('.key')]
        logger.info(f"Testing {len(key_files)} keys from {key_dir}")
        
        for key_file in key_files:
            try:
                relay_id = key_file.replace('.key', '')
                private_key = read_key_file(relay_id, key_dir.split('/')[-1])
                
                if not private_key:
                    logger.debug(f"Could not read key file for relay {relay_id}")
                    continue
                
                # Test if this key can decrypt the encrypted_fernet
                try:
                    rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
                    test_decrypt = rsa.decrypt(encrypted_fernet, rsa_private)
                    
                    logger.info(f"SUCCESS: Found working private key for relay {relay_id} in {key_dir}")
                    
                    # Additional verification: extract public key for debugging
                    extracted_public = extract_public_key_from_private(private_key)
                    if extracted_public:
                        extracted_hash = hashlib.sha256(extracted_public.encode()).hexdigest()[:16]
                        logger.info(f"Working key's public key hash: {extracted_hash}")
                        
                        # Compare with the block's public key
                        block_public = current_block.get("public_key")
                        if block_public:
                            block_hash = hashlib.sha256(block_public.encode()).hexdigest()[:16]
                            logger.info(f"Block's public key hash: {block_hash}")
                            
                            if extracted_hash == block_hash:
                                logger.info("✓ Working key matches block's public key")
                            else:
                                logger.info("ℹ Working key differs from block's public key (expected in routing chain)")
                    
                    tested_keys.append(f"{relay_id}({key_dir.split('/')[-1]}):✓")
                    return private_key
                    
                except Exception as decrypt_error:
                    # This key doesn't work, continue to next
                    tested_keys.append(f"{relay_id}({key_dir.split('/')[-1]}):✗")
                    logger.debug(f"Key {relay_id} cannot decrypt: {str(decrypt_error)[:50]}")
                    continue
                    
            except Exception as e:
                logger.debug(f"Failed to test key {key_file}: {str(e)}")
                tested_keys.append(f"{key_file}:ERROR")
                continue
    
    logger.error(f"No working private key found. Tested {len(tested_keys)} keys:")
    for i, test_result in enumerate(tested_keys):
        logger.error(f"  {i+1:2d}. {test_result}")
    
    return None

def diagnose_and_fix_key_mismatch(current_block: dict, private_key: str, encrypted_fernet: bytes) -> str:
    """
    Diagnose key mismatch issues and attempt to find the correct key.
    
    Args:
        current_block (dict): The current routing block
        private_key (str): The originally attempted private key
        encrypted_fernet (bytes): The encrypted Fernet key
    
    Returns:
        str: The correct private key if found, original key otherwise
    """
    logger.info("Diagnosing key mismatch issue...")
    
    # First, verify the current key doesn't work
    try:
        rsa_private = rsa.PrivateKey.load_pkcs1(private_key.encode('utf-8'))
        rsa.decrypt(encrypted_fernet, rsa_private)
        logger.info("Current key actually works - no issue detected")
        return private_key
    except Exception:
        logger.info("Confirmed: Current key cannot decrypt the encrypted_fernet")
    
    # Extract public key from current private key for comparison
    extracted_public = extract_public_key_from_private(private_key)
    block_public = current_block.get("public_key")
    
    if extracted_public and block_public:
        if extracted_public.strip() == block_public.strip():
            logger.error("Keys match but decryption fails - possible data corruption")
        else:
            logger.info("Public keys don't match - this confirms key mismatch")
            logger.info(f"Block public key hash: {hashlib.sha256(block_public.encode()).hexdigest()[:16]}...")
            logger.info(f"Private key's public hash: {hashlib.sha256(extracted_public.encode()).hexdigest()[:16]}...")
    
    # Try to find the correct key using routing chain logic first
    logger.info("Step 1: Trying routing chain logic-based key search...")
    correct_key = find_correct_key_using_routing_logic(current_block, encrypted_fernet)
    
    if correct_key:
        logger.info("Found correct private key using routing logic - using it for decryption")
        return correct_key
    else:
        logger.warning("Routing logic search failed, trying brute force...")
        # Fallback to brute force search
        correct_key = find_correct_private_key_for_block(current_block, encrypted_fernet)
        if correct_key:
            logger.info("Found correct private key using brute force - using it for decryption")
            return correct_key
        else:
            logger.error("Could not find correct private key - decryption will fail")
            return private_key