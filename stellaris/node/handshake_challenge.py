"""
handshake_challenge.py - Secure handshake challenge system for Stellaris

This module implements a secure handshake challenge system to verify node identities
before establishing trust. It uses cryptographic challenges to prevent impersonation
and ensures nodes can prove their identity by signing challenges.
"""

import os
import time
import asyncio
import hashlib
from typing import Dict, Optional
from asyncio import Lock

from stellaris.node.identity import verify_signature, get_node_id


class HandshakeChallengeManager:
    """
    Secure challenge management system with automatic cleanup
    
    This class manages cryptographic challenges used during node handshakes
    to verify the authenticity of peer nodes. Challenges have a time-to-live
    and are automatically cleaned up.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the handshake challenge manager.
        
        Args:
            ttl_seconds: Time-to-live for challenges in seconds
        """
        self._challenges: Dict[str, float] = {}  # challenge -> timestamp
        self._challenge_owners: Dict[str, str] = {}  # challenge -> node_id
        self._lock = Lock()
        self.ttl_seconds = ttl_seconds
        self._cleanup_task = None
    
    async def start(self):
        """Start periodic cleanup task"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self):
        """Stop cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
    
    async def _periodic_cleanup(self):
        """Remove expired challenges every 60 seconds"""
        while True:
            try:
                await asyncio.sleep(60)
                await self.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Retry after a minute on error
    
    async def cleanup(self):
        """Remove expired challenges"""
        async with self._lock:
            current_time = time.time()
            expired = [
                challenge for challenge, timestamp in self._challenges.items()
                if current_time - timestamp > self.ttl_seconds
            ]
            for challenge in expired:
                del self._challenges[challenge]
                if challenge in self._challenge_owners:
                    del self._challenge_owners[challenge]
    
    async def create_challenge(self, for_node_id: Optional[str] = None) -> str:
        """
        Create a new challenge.
        
        Args:
            for_node_id: Optional node ID this challenge is intended for
        
        Returns:
            Hexadecimal challenge string
        """
        # Generate random challenge
        challenge = os.urandom(32).hex()
        
        async with self._lock:
            # Prevent unlimited growth
            if len(self._challenges) > 10000:
                # Remove oldest half
                sorted_challenges = sorted(
                    self._challenges.items(), 
                    key=lambda x: x[1]
                )
                for challenge_to_remove, _ in sorted_challenges[:5000]:
                    del self._challenges[challenge_to_remove]
                    if challenge_to_remove in self._challenge_owners:
                        del self._challenge_owners[challenge_to_remove]
            
            # Store the challenge with timestamp
            self._challenges[challenge] = time.time()
            
            # If specified, store the node ID this challenge is for
            if for_node_id:
                self._challenge_owners[challenge] = for_node_id
        
        return challenge
    
    async def verify_and_consume_challenge(self, 
                                           challenge: str, 
                                           signature: str,
                                           node_id: str,
                                           pubkey_hex: str) -> bool:
        """
        Verify a challenge signature and consume the challenge.
        
        Args:
            challenge: The challenge string
            signature: Signature of the challenge
            node_id: The node ID claiming to have signed the challenge
            pubkey_hex: Public key of the signing node (hex string)
        
        Returns:
            True if challenge is valid and signature verifies, False otherwise
        """
        async with self._lock:
            # Check if challenge exists
            if challenge not in self._challenges:
                return False
            
            # Check if challenge expired
            timestamp = self._challenges[challenge]
            current_time = time.time()
            if current_time - timestamp > self.ttl_seconds:
                del self._challenges[challenge]
                if challenge in self._challenge_owners:
                    del self._challenge_owners[challenge]
                return False
            
            # If challenge has a specific owner, verify it's being used by that node
            if challenge in self._challenge_owners and self._challenge_owners[challenge] != node_id:
                return False
            
            # Verify the signature
            if not verify_signature(challenge, signature, pubkey_hex):
                return False
            
            # Valid challenge - consume it immediately
            del self._challenges[challenge]
            if challenge in self._challenge_owners:
                del self._challenge_owners[challenge]
            
            return True
    
    async def verify_challenge_exists(self, challenge: str) -> bool:
        """
        Check if a challenge exists and hasn't expired.
        
        Args:
            challenge: The challenge string
        
        Returns:
            True if challenge exists and is valid, False otherwise
        """
        async with self._lock:
            if challenge in self._challenges:
                timestamp = self._challenges[challenge]
                current_time = time.time()
                
                # Check if expired
                if current_time - timestamp > self.ttl_seconds:
                    del self._challenges[challenge]
                    if challenge in self._challenge_owners:
                        del self._challenge_owners[challenge]
                    return False
                
                return True
            
            return False


# Singleton instance
_challenge_manager: Optional[HandshakeChallengeManager] = None

def get_challenge_manager() -> HandshakeChallengeManager:
    """Get the singleton instance of HandshakeChallengeManager"""
    global _challenge_manager
    
    if _challenge_manager is None:
        _challenge_manager = HandshakeChallengeManager()
    
    return _challenge_manager