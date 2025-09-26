import os
import hashlib
import json
from ecdsa import NIST256p, SigningKey, VerifyingKey
from ecdsa.util import sigencode_string, sigdecode_string

# Constants
SELECTED_CURVE = NIST256p
KEY_FILE_PATH = "node_key.priv"

# Internal state
_private_key = None
_public_key = None
_node_id = None


def generate_new_key():
    """
    Generate a new P256 (secp256r1) key pair.
    Returns (private_key: int, public_key: VerifyingKey)
    """
    sk = SigningKey.generate(curve=SELECTED_CURVE)
    vk = sk.get_verifying_key()
    return sk.privkey.secret_multiplier, vk


def save_key(private_key):
    """
    Save the private key to disk in hexadecimal format
    """
    with open(KEY_FILE_PATH, "w") as f:
        f.write(f"{private_key:x}")


def load_key():
    """
    Load the private key from disk.
    Returns the private key as an integer or None if the file doesn't exist
    """
    if not os.path.exists(KEY_FILE_PATH):
        return None
    
    with open(KEY_FILE_PATH, "r") as f:
        key_hex = f.read().strip()
        return int(key_hex, 16)


def initialize_identity():
    """
    Initialize the node's cryptographic identity by loading or generating
    a private key, deriving the public key, and computing the node ID.
    """
    global _private_key, _public_key, _node_id
    
    # Load existing key or generate a new one
    _private_key = load_key()
    if _private_key is None:
        _private_key, _public_key = generate_new_key()
        save_key(_private_key)
    else:
        # Derive public key from private key
        sk = SigningKey.from_secret_exponent(_private_key, curve=SELECTED_CURVE)
        _public_key = sk.get_verifying_key()
    
    # Compute node ID (SHA256 hash of the uncompressed public key)
    pubkey_bytes = _public_key.to_string("uncompressed")
    _node_id = hashlib.sha256(pubkey_bytes).hexdigest()


def get_private_key():
    """
    Return the current private key.
    """
    global _private_key
    return _private_key


def get_public_key_hex():
    """
    Return the public key as a hex string (uncompressed format).
    """
    global _public_key
    if _public_key is None:
        return None
    return _public_key.to_string("uncompressed").hex()


def get_node_id():
    """
    Return the node ID (SHA256 hash of public key).
    """
    global _node_id
    return _node_id


def sign_message(message):
    """
    Sign a message using the node's private key.
    message: bytes to sign
    Returns: hex string of the signature (r,s)
    Raises ValueError if identity not initialized
    """
    global _private_key
    if _private_key is None:
        raise ValueError("Node identity not initialized. Call initialize_identity() first.")
    
    sk = SigningKey.from_secret_exponent(_private_key, curve=SELECTED_CURVE)
    signature = sk.sign(message, hashfunc=hashlib.sha256, sigencode=sigencode_string)
    return signature.hex()


def verify_signature(public_key_hex, message, signature_hex):
    """
    Verify a signature against a message and public key.
    public_key_hex: Hex string of the public key (uncompressed format)
    message: The message that was signed (bytes)
    signature_hex: Hex string of the signature
    Returns: bool indicating if the signature is valid
    """
    try:
        # Reconstruct the public key
        public_key_bytes = bytes.fromhex(public_key_hex)
        vk = VerifyingKey.from_string(public_key_bytes, curve=SELECTED_CURVE)
        
        # Decode the signature
        signature = bytes.fromhex(signature_hex)
        
        # Verify
        return vk.verify(signature, message, hashfunc=hashlib.sha256, sigdecode=sigdecode_string)
    except Exception:
        return False


def get_canonical_json_bytes(data):
    """
    Produce a canonical byte representation of a JSON object.
    This ensures consistent serialization for signing and verification.
    data: A JSON-serializable object
    Returns: bytes in UTF-8 encoding
    """
    # Sort keys and ensure consistent spacing
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return json_str.encode('utf-8')