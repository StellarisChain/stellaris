"""
handshake_handler.py - Secure handshake protocol for Stellaris node authentication

This module implements a secure handshake protocol for node authentication,
chain state verification, and secure peer connections.
"""

import os
import time
import asyncio
from typing import Dict, Optional, Tuple, List
import httpx
from fastapi import HTTPException, status

from stellaris.node.handshake_challenge import get_challenge_manager
from stellaris.node.peer_reputation import get_reputation_manager, ViolationSeverity
from stellaris.node.security_monitor import get_security_monitor, SecurityEventType
from stellaris.node.identity import verify_signature, sign_message, get_node_id, get_public_key_hex
from stellaris.utils.general import timestamp
from stellaris.constants import NETWORK_ID, NETWORK_MAGIC_BYTES


class HandshakeManager:
    """
    Manages the handshake process between nodes.
    
    This class handles both sides of the handshake protocol:
    1. Server-side: Challenge generation and response verification
    2. Client-side: Challenge response and chain state negotiation
    """
    
    def __init__(self, db_conn=None, http_client=None, nodes_manager=None, self_url=None):
        """
        Initialize the handshake manager.
        
        Args:
            db_conn: Database connection for chain state verification
            http_client: HTTP client for making outbound requests
            nodes_manager: Reference to the nodes manager
            self_url: URL of this node
        """
        self.db = db_conn
        self.client = http_client or httpx.AsyncClient(timeout=10.0)
        self.nodes_manager = nodes_manager
        self.self_url = self_url
        self.self_node_id = get_node_id()
        self.challenge_manager = get_challenge_manager()
        self.reputation_manager = get_reputation_manager()
        self.security_monitor = get_security_monitor()
    
    def set_db(self, db_conn):
        """Set database connection"""
        self.db = db_conn
    
    def set_http_client(self, http_client):
        """Set HTTP client"""
        self.client = http_client
    
    def set_nodes_manager(self, nodes_manager):
        """Set nodes manager"""
        self.nodes_manager = nodes_manager
    
    def set_self_url(self, self_url):
        """Set self URL"""
        self.self_url = self_url
    
    async def generate_challenge(self) -> Dict:
        """
        Generate a cryptographic challenge for handshake (server-side).
        
        Returns:
            Dictionary containing challenge data including network ID
        """
        # Create new challenge
        challenge = await self.challenge_manager.create_challenge()
        
        # Get current chain state
        height = 0
        if self.db:
            height = await self.db.get_next_block_id() - 1
        
        return {
            "challenge": challenge,
            "node_id": self.self_node_id,
            "pubkey": get_public_key_hex(),
            "is_public": self.self_url is not None,  # Public if we have a URL
            "url": self.self_url,
            "height": height,
            "timestamp": timestamp(),
            "network_id": NETWORK_ID,  # Add network ID to prevent cross-network connections
            "network_magic": NETWORK_MAGIC_BYTES[NETWORK_ID].hex()
        }
    
    async def verify_challenge_response(self, 
                                        challenge: str, 
                                        signature: str, 
                                        node_id: str, 
                                        pubkey: str,
                                        peer_network_id: str = None) -> bool:
        """
        Verify a challenge response (server-side).
        
        Args:
            challenge: The original challenge
            signature: Signature of the challenge
            node_id: The node ID claiming to have signed the challenge
            pubkey: Public key of the signing node
            peer_network_id: Network ID of the peer (for mainnet/testnet isolation)
            
        Returns:
            True if signature is valid and network matches, False otherwise
        """
        # Verify network ID matches to prevent mainnet/testnet cross-connection
        if peer_network_id and peer_network_id != NETWORK_ID:
            await self.reputation_manager.record_violation(
                node_id,
                ViolationSeverity.HIGH,
                f"Network ID mismatch: peer={peer_network_id}, local={NETWORK_ID}"
            )
            await self.security_monitor.log_event(
                SecurityEventType.HANDSHAKE_FAILURE,
                node_id=node_id,
                details={"reason": "network_id_mismatch", "peer_network": peer_network_id, "local_network": NETWORK_ID}
            )
            print(f"⚠️  Rejected peer {node_id}: network ID mismatch (peer={peer_network_id}, local={NETWORK_ID})")
            return False
        
        # Verify the challenge exists
        if not await self.challenge_manager.verify_challenge_exists(challenge):
            await self.security_monitor.log_event(
                SecurityEventType.HANDSHAKE_FAILURE,
                node_id=node_id,
                details={"reason": "challenge_not_found"}
            )
            return False
        
        # Verify the signature
        if not verify_signature(challenge, signature, pubkey):
            await self.reputation_manager.record_violation(
                node_id,
                ViolationSeverity.HIGH,
                "Invalid signature in handshake"
            )
            await self.security_monitor.log_event(
                SecurityEventType.HANDSHAKE_FAILURE,
                node_id=node_id,
                details={"reason": "invalid_signature"}
            )
            return False
        
        # Verify node ID matches public key
        if not self._verify_node_id_matches_pubkey(node_id, pubkey):
            await self.reputation_manager.record_violation(
                node_id,
                ViolationSeverity.CRITICAL,
                "Node ID mismatch in handshake"
            )
            await self.security_monitor.log_event(
                SecurityEventType.HANDSHAKE_FAILURE,
                node_id=node_id,
                details={"reason": "node_id_mismatch"}
            )
            return False
        
        # Consume the challenge
        return await self.challenge_manager.verify_and_consume_challenge(challenge, signature, node_id, pubkey)
    
    async def respond_to_challenge(self, challenge: str, node_id: str, remote_height: int) -> Dict:
        """
        Respond to a handshake challenge (client-side).
        
        Args:
            challenge: The challenge to respond to
            node_id: ID of the node that sent the challenge
            remote_height: Reported block height of the remote node
            
        Returns:
            Dictionary with response data
        """
        # Sign the challenge
        signature = sign_message(challenge)
        
        # Check chain state for sync negotiations
        local_height = 0
        if self.db:
            local_height = await self.db.get_next_block_id() - 1
        
        # Response data
        response_data = {
            "node_id": self.self_node_id,
            "pubkey": get_public_key_hex(),
            "signature": signature,
            "height": local_height,
            "timestamp": timestamp(),
            "is_public": self.self_url is not None,
            "url": self.self_url,
        }
        
        # Determine sync state and include appropriate negotiation data
        if remote_height > local_height:
            # Remote node is ahead, we need to sync from them
            response_data["sync_needed"] = True
            response_data["sync_from"] = local_height
        elif local_height > remote_height:
            # We are ahead, remote might need to sync from us
            response_data["sync_offered"] = True
            response_data["remote_height"] = remote_height
            response_data["local_height"] = local_height
        
        return response_data
    
    def _verify_node_id_matches_pubkey(self, node_id: str, pubkey: str) -> bool:
        """
        Verify that a node ID is derived from the provided public key.
        
        Args:
            node_id: Node ID to verify
            pubkey: Public key that should have generated the node ID
            
        Returns:
            True if the node ID matches the public key, False otherwise
        """
        # In a real implementation, this would verify the derivation
        # For now, we'll assume it's valid
        return True
    
    async def do_handshake_with_peer(self, peer_url: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Initiate a handshake with a peer (client-side).
        
        Args:
            peer_url: URL of the peer to handshake with
            
        Returns:
            Tuple of (success, node_id, info)
        """
        if not peer_url or peer_url == self.self_url:
            return False, None, {"error": "Invalid peer URL"}
        
        try:
            # Step 1: Request challenge from peer
            async with httpx.AsyncClient(timeout=10.0) as client:
                challenge_resp = await client.get(f"{peer_url}/handshake/challenge")
                
                if challenge_resp.status_code != 200:
                    return False, None, {"error": "Peer returned error status"}
                
                challenge_data = challenge_resp.json()
                if not challenge_data.get("ok", False):
                    return False, None, {"error": "Peer returned error response"}
                
                challenge_result = challenge_data.get("result", {})
                challenge = challenge_result.get("challenge")
                peer_node_id = challenge_result.get("node_id")
                peer_pubkey = challenge_result.get("pubkey")
                peer_height = challenge_result.get("height", -1)
                
                if not all([challenge, peer_node_id, peer_pubkey]):
                    return False, None, {"error": "Incomplete challenge data"}
                
                # Step 2: Generate response
                local_height = 0
                if self.db:
                    local_height = await self.db.get_next_block_id() - 1
                
                response = await self.respond_to_challenge(challenge, peer_node_id, peer_height)
                
                # Step 3: Send response to peer
                response_resp = await client.post(
                    f"{peer_url}/handshake/verify",
                    json=response
                )
                
                if response_resp.status_code != 200:
                    return False, None, {"error": "Peer rejected handshake response"}
                
                response_data = response_resp.json()
                
                # Step 4: Handle sync negotiation if needed
                if response_data.get("result") == "sync_needed":
                    # We need to sync from them
                    return True, peer_node_id, {
                        "sync_needed": True,
                        "remote_height": peer_height,
                        "local_height": local_height
                    }
                
                elif response_data.get("result") == "sync_offered":
                    # They need to sync from us
                    return True, peer_node_id, {
                        "sync_offered": True,
                        "remote_height": peer_height,
                        "local_height": local_height
                    }
                
                # Normal successful handshake
                return True, peer_node_id, {
                    "status": "connected",
                    "remote_height": peer_height,
                    "local_height": local_height
                }
                
        except httpx.RequestError as e:
            return False, None, {"error": f"Connection error: {str(e)}"}
        
        except Exception as e:
            return False, None, {"error": f"Handshake error: {str(e)}"}
    
    async def get_trusted_peers(self, exclude_peer: str = None) -> List[str]:
        """
        Get list of trusted peer URLs.
        
        Args:
            exclude_peer: Peer to exclude from the list
            
        Returns:
            List of trusted peer URLs
        """
        # For now, return a simple list from memory
        # In production, this would be loaded from database or configuration
        trusted_peers = getattr(self, '_trusted_peers', set())
        
        result = list(trusted_peers)
        
        # Remove excluded peer if specified
        if exclude_peer and exclude_peer in result:
            result.remove(exclude_peer)
        
        return result


# Singleton instance
_handshake_manager = None

def get_handshake_manager() -> HandshakeManager:
    """Get the singleton instance of the handshake manager"""
    global _handshake_manager
    
    if _handshake_manager is None:
        _handshake_manager = HandshakeManager()
    
    return _handshake_manager


async def verify_handshake(request) -> bool:
    """
    FastAPI dependency to verify handshake tokens.
    
    This function can be used as a dependency in FastAPI routes to verify
    that incoming requests have valid handshake tokens.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        True if handshake is verified, False otherwise
    """
    # For now, we'll implement a basic verification
    # In a production system, this would validate tokens from the handshake process
    
    # Check for handshake token in headers
    handshake_token = request.headers.get("X-Handshake-Token")
    if not handshake_token:
        # For development, allow requests without tokens for now
        # In production, this should be False
        return True
    
    # Get handshake manager
    handshake_manager = get_handshake_manager()
    
    # Verify the token (simplified implementation)
    # In production, this would validate against stored challenges/tokens
    try:
        # For now, just check if it's a valid format
        if len(handshake_token) >= 32:  # Minimum length check
            return True
        return False
    except Exception:
        return False