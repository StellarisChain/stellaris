"""
input_validator.py - Comprehensive input validation for Stellaris

This module provides a collection of validation utilities to ensure that
inputs to the system are properly validated before processing. This helps 
prevent injection attacks, malformed data, and other security issues.
"""

import re
import ipaddress
from typing import Optional, Union, Any
from urllib.parse import urlparse

from fastapi import HTTPException, status


class InputValidator:
    """
    Comprehensive input validation utilities.
    
    This class provides static methods for validating various types of inputs
    used in the Stellaris system, including hex strings, block heights, URLs,
    node IDs, transaction hashes, and more.
    """
    
    @staticmethod
    def validate_hex(hex_string: str, min_length: int = 1, max_length: Optional[int] = None) -> bool:
        """
        Validate a hexadecimal string.
        
        Args:
            hex_string: The string to validate
            min_length: Minimum length in characters
            max_length: Maximum length in characters (None for no limit)
        
        Returns:
            True if valid, False otherwise
        """
        if not hex_string:
            return False
        
        if max_length and len(hex_string) > max_length:
            return False
        
        if len(hex_string) < min_length:
            return False
        
        try:
            # Ensure even length for valid hex bytes
            if len(hex_string) % 2 != 0:
                return False
            
            # Try to decode
            bytes.fromhex(hex_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    async def validate_block_height(height: int, db, max_ahead: int = 10) -> bool:
        """
        Validate a block height is reasonable.
        
        Args:
            height: Block height to validate
            db: Database instance
            max_ahead: Maximum blocks ahead of current height allowed
        
        Returns:
            True if valid, False otherwise
        """
        if height < 0:
            return False
        
        current_height = await db.get_next_block_id() - 1
        
        # Don't accept blocks too far in the future
        if height > current_height + max_ahead:
            return False
        
        return True
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: list = None) -> bool:
        """
        Validate a URL.
        
        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes (None for any)
        
        Returns:
            True if valid, False otherwise
        """
        if not url:
            return False
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in allowed_schemes:
                return False
            
            # Check netloc (domain or IP)
            if not parsed.netloc:
                return False
            
            # Additional checks could be added here
            # (e.g., domain format, IP validation, etc.)
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """
        Validate an IP address.
        
        Args:
            ip: IP address to validate
        
        Returns:
            True if valid, False otherwise
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_transaction_hash(tx_hash: str) -> bool:
        """
        Validate a transaction hash.
        
        Args:
            tx_hash: Transaction hash to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Transaction hashes are SHA-256 digests (32 bytes, 64 hex chars)
        return InputValidator.validate_hex(tx_hash, min_length=64, max_length=64)
    
    @staticmethod
    def validate_block_hash(block_hash: str) -> bool:
        """
        Validate a block hash.
        
        Args:
            block_hash: Block hash to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Block hashes are SHA-256 digests (32 bytes, 64 hex chars)
        return InputValidator.validate_hex(block_hash, min_length=64, max_length=64)
    
    @staticmethod
    def validate_signature(signature: str) -> bool:
        """
        Validate a signature format.
        
        Args:
            signature: Signature to validate
        
        Returns:
            True if valid format, False otherwise
        """
        # Signatures are typically 64-byte (128 hex chars) for Ed25519
        return InputValidator.validate_hex(signature, min_length=128, max_length=128)
    
    @staticmethod
    def validate_public_key(pubkey: str) -> bool:
        """
        Validate a public key format.
        
        Args:
            pubkey: Public key to validate
        
        Returns:
            True if valid format, False otherwise
        """
        # Public keys are typically 32-byte (64 hex chars) for Ed25519
        return InputValidator.validate_hex(pubkey, min_length=64, max_length=64)
    
    @staticmethod
    def validate_node_id(node_id: str) -> bool:
        """
        Validate a node ID format.
        
        Args:
            node_id: Node ID to validate
        
        Returns:
            True if valid format, False otherwise
        """
        # Node IDs are typically SHA-256 digests of public keys (64 hex chars)
        return InputValidator.validate_hex(node_id, min_length=64, max_length=64)
    
    @staticmethod
    def validate_integer_range(value: int, min_val: int, max_val: int) -> bool:
        """
        Validate an integer is within range.
        
        Args:
            value: Integer to validate
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
        
        Returns:
            True if valid, False otherwise
        """
        return min_val <= value <= max_val
    
    @staticmethod
    def validate_limit_offset(limit: int, offset: int, max_limit: int = 1000) -> bool:
        """
        Validate pagination parameters.
        
        Args:
            limit: Number of items to return
            offset: Starting position
            max_limit: Maximum allowed limit
        
        Returns:
            True if valid, False otherwise
        """
        return (
            limit > 0 and 
            limit <= max_limit and
            offset >= 0
        )
    
    @staticmethod
    def safe_validate(validation_fn, *args, **kwargs) -> tuple:
        """
        Safely run a validation function, catching exceptions.
        
        Args:
            validation_fn: Validation function to run
            *args, **kwargs: Arguments to pass to validation function
        
        Returns:
            (is_valid, error_message) tuple
        """
        try:
            result = validation_fn(*args, **kwargs)
            return result, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def validate_or_error(validation_fn, value, error_message: str, status_code=400, *args, **kwargs):
        """
        Validate input or raise an HTTP exception.
        
        Args:
            validation_fn: Validation function to use
            value: Value to validate
            error_message: Error message if validation fails
            status_code: HTTP status code if validation fails
            *args, **kwargs: Additional arguments to pass to validation function
        
        Raises:
            HTTPException if validation fails
        """
        if not validation_fn(value, *args, **kwargs):
            raise HTTPException(
                status_code=status_code,
                detail=error_message
            )