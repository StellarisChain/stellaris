import json
import os
import hashlib
import random
from os.path import dirname, exists
import httpx
import time
from typing import Dict, List, Optional, Any, Tuple
import ipaddress
import socket
import asyncio

from stellaris.node.identity import get_node_id, sign_message, get_canonical_json_bytes, get_public_key_hex
from stellaris.utils.general import timestamp
from stellaris.constants import MAX_BLOCK_SIZE_HEX
from stellaris.node.peer_reputation import get_reputation_manager, ViolationSeverity
from stellaris.node.handshake_challenge import get_challenge_manager
from stellaris.node.security_monitor import get_security_monitor, SecurityEventType

# Constants
ACTIVE_NODES_DELTA = 60 * 60 * 24 * 7  # 7 days
MAX_PEERS_COUNT = 200

# Get environment variables with defaults
MAIN_STELLARIS_NODE_URL = os.environ.get('MAIN_STELLARIS_NODE_URL', 'https://stellaris-node.connor33341.dev')
SELF_URL = os.environ.get('STELLARIS_SELF_URL', None)

# Path setup
path = dirname(os.path.realpath(__file__)) + '/nodes.json'


class NodesManager:
    """
    Manages peer registry with persistence and connection utilities.
    Implemented as a singleton for compatibility with previous static usage.
    """
    # Singleton instance
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance, creating it if necessary."""
        if cls._instance is None:
            # Use a default httpx.AsyncClient if none is provided
            default_client = httpx.AsyncClient(timeout=10.0)
            cls._instance = cls(default_client)
        return cls._instance
    
    def __init__(self, http_client: httpx.AsyncClient, db_handle=None):
        """
        Initialize the nodes manager with an HTTP client
        """
        # If there's already an instance, use that one (singleton pattern)
        if NodesManager._instance is not None:
            return
            
        self.client = http_client
        self.db = db_handle
        self.peers = {}
        self.is_public = False  # Whether this node is publicly reachable
        self.node_id = None  # Will be set on init()
        
        # Set the singleton instance
        NodesManager._instance = self
        
    def initialize(self, node_id: str):
        """
        Instance method to initialize the peer registry with a node_id
        """
        self.node_id = node_id
        
        if exists(path):
            try:
                with open(path, 'rt') as f:
                    data = json.load(f)
                    self.peers = data.get("peers", {})
            except (json.JSONDecodeError, IOError):
                # If file is corrupted or can't be read, start with empty peers
                self.peers = {}
        else:
            # Create an empty peers registry
            self.peers = {}
            self.sync()
            
    @classmethod
    def init(cls):
        """
        Static compatibility method for old-style init calls.
        This will initialize with default values if no instance exists yet.
        """
        instance = cls.get_instance()
        if instance.node_id is None:
            # Try to initialize with node ID from identity module
            from stellaris.node.identity import initialize_identity, get_node_id
            initialize_identity()
            instance.initialize(get_node_id())
    
    def sync(self):
        """
        Persist the peer registry to disk
        """
        with open(path, 'wt') as f:
            json.dump({"peers": self.peers}, f)
            
    @classmethod
    def sync_peers(cls):
        """Static compatibility method for sync"""
        instance = cls.get_instance()
        instance.sync()
    
    def purge_peers(self):
        """
        Clear the peer registry and persist the empty state
        """
        self.peers = {}
        self.sync()
    
    def add_or_update_peer(self, node_id: str, pubkey: str, url: Optional[str], is_public: bool = False) -> bool:
        """
        Add a new peer or update an existing one.
        Returns True if the peer was added (new), False if updated.
        """
        # Skip self
        if node_id == get_node_id():
            return False
        
        # Normalize URL if provided
        normalized_url = url
        if url:
            normalized_url = url.rstrip('/')
        
        current_time = timestamp()
        is_new = node_id not in self.peers
        
        # Create or update peer entry
        self.peers[node_id] = {
            "pubkey": pubkey,
            "url": normalized_url,
            "last_seen": current_time,
            "is_public": is_public
        }
        
        # Enforce capacity limit
        if len(self.peers) > MAX_PEERS_COUNT:
            # Remove oldest peer by last_seen
            oldest_peer_id = min(self.peers, key=lambda p: self.peers[p]["last_seen"])
            del self.peers[oldest_peer_id]
        
        self.sync()
        return is_new
    
    def update_peer_last_seen(self, node_id: str) -> bool:
        """
        Update the last_seen timestamp for a peer.
        Returns True if the peer exists and was updated.
        """
        if node_id in self.peers:
            self.peers[node_id]["last_seen"] = timestamp()
            self.sync()
            return True
        return False
    
    def get_peer(self, node_id: str) -> Optional[Dict]:
        """
        Get a single peer by node_id
        """
        peer = self.peers.get(node_id)
        if peer:
            return {"node_id": node_id, **peer}
        return None
    
    def get_all_peers(self) -> List[Dict]:
        """
        Get all peers with their node_id included
        """
        return [{"node_id": node_id, **peer} for node_id, peer in self.peers.items()]
    
    def _get_recent_nodes_impl(self) -> List[Dict]:
        """
        Get peers that have been seen recently, sorted by last_seen (newest first)
        Implementation method to avoid recursion with the class method
        """
        current_time = timestamp()
        recent_cutoff = current_time - ACTIVE_NODES_DELTA
        
        recent_peers = [
            {"node_id": node_id, **peer}
            for node_id, peer in self.peers.items()
            if peer["last_seen"] >= recent_cutoff
        ]
        
        # Sort by last_seen (descending)
        recent_peers.sort(key=lambda p: p["last_seen"], reverse=True)
        return recent_peers
        
    @classmethod
    def get_recent_nodes(cls) -> List[Dict]:
        """Static compatibility method"""
        instance = cls.get_instance()
        return instance._get_recent_nodes_impl()
    
    async def get_propagate_peers(self, limit: int = 10) -> List[Dict]:
        """
        Get peers for outbound propagation, filtered to recent peers with URLs and prioritized by reputation.
        
        This method selects peers for propagation considering:
        1. Recent activity (seen within ACTIVE_NODES_DELTA)
        2. Has a valid URL
        3. Not banned
        4. Higher reputation scores are prioritized
        
        Args:
            limit: Maximum number of peers to return
            
        Returns:
            List of peer dictionaries, prioritized by reputation
        """
        current_time = timestamp()
        recent_cutoff = current_time - ACTIVE_NODES_DELTA
        reputation_manager = get_reputation_manager()
        
        # Get all recent peers with URLs
        recent_peers = [
            {"node_id": node_id, **peer}
            for node_id, peer in self.peers.items()
            if peer["last_seen"] >= recent_cutoff and peer.get("url")
        ]
        
        # Filter out banned peers and get reputation scores
        valid_peers = []
        for peer in recent_peers:
            node_id = peer["node_id"]
            # Skip if banned
            if await reputation_manager.is_banned(node_id):
                continue
            
            # Get reputation score
            score = await reputation_manager.get_score(node_id)
            valid_peers.append((peer, score))
        
        # If we have more than 2x the limit, use weighted random selection favoring higher scores
        if len(valid_peers) > limit * 2:
            # Higher scores mean higher selection probability
            weighted_selection = self._weighted_peer_selection(valid_peers, limit * 2)
            # Sort the selected subset by score (highest first)
            weighted_selection.sort(key=lambda x: x[1], reverse=True)
            # Take the top 'limit' peers
            selected_peers = [peer for peer, _ in weighted_selection[:limit]]
            return selected_peers
        
        # Otherwise, just sort by score (highest first) and take top 'limit'
        valid_peers.sort(key=lambda x: x[1], reverse=True)
        return [peer for peer, _ in valid_peers[:limit]]
    
    def _weighted_peer_selection(self, peers_with_scores: List[Tuple[Dict, int]], limit: int) -> List[Tuple[Dict, int]]:
        """
        Select peers with probability weighted by their reputation score.
        
        Args:
            peers_with_scores: List of (peer, score) tuples
            limit: Number of peers to select
            
        Returns:
            List of selected (peer, score) tuples
        """
        # Normalize scores to be at least 1 for probability calculation
        normalized_peers = [(peer, max(1, score)) for peer, score in peers_with_scores]
        
        # Calculate total weight
        total_weight = sum(score for _, score in normalized_peers)
        
        # Select 'limit' peers with probability proportional to score
        selected = []
        remaining = list(normalized_peers)
        
        for _ in range(min(limit, len(normalized_peers))):
            if not remaining:
                break
                
            # Get random value between 0 and total_weight
            r = random.uniform(0, total_weight)
            cumulative = 0
            
            for i, (peer, score) in enumerate(remaining):
                cumulative += score
                if cumulative >= r:
                    selected.append((peer, score))
                    # Remove selected peer from remaining and adjust total weight
                    total_weight -= score
                    del remaining[i]
                    break
        
        return selected
        
    async def _get_propagate_nodes_impl(self, limit: int = 10) -> List[str]:
        """
        Get URLs of peers for propagation (implementation method).
        Returns a list of peer URLs.
        """
        peers = await self.get_propagate_peers(limit)
        return [peer["url"] for peer in peers if peer.get("url")]

    @classmethod
    async def get_propagate_nodes(cls, limit: int = 10) -> List[str]:
        """
        Get URLs of peers for propagation with reputation prioritization.
        
        This method returns a list of peer URLs, prioritizing peers with
        higher reputation scores.
        
        Args:
            limit: Maximum number of peers to return
            
        Returns:
            List of peer URLs
        """
        instance = cls.get_instance()
        try:
            return await instance._get_propagate_nodes_impl(limit)
        except Exception as e:
            # Fallback to old synchronous method for backward compatibility
            print(f"Warning: Error in async get_propagate_nodes: {e}, using fallback")
            # Simple fallback that doesn't use reputation
            current_time = timestamp()
            recent_cutoff = current_time - ACTIVE_NODES_DELTA
            
            propagate_peers = [
                peer for node_id, peer in instance.peers.items()
                if peer.get("last_seen", 0) >= recent_cutoff and peer.get("url")
            ]
            
            # Sort by last_seen (descending) and take up to limit
            propagate_peers.sort(key=lambda p: p.get("last_seen", 0), reverse=True)
            return [peer["url"] for peer in propagate_peers[:limit] if peer.get("url")]
    
    def set_public_status(self, is_public: bool):
        """
        Set whether this node is publicly reachable
        """
        self.is_public = is_public
    
    def remove_peer(self, node_id: str) -> bool:
        """
        Remove a peer from the registry.
        Returns True if the peer was removed.
        """
        if node_id in self.peers:
            del self.peers[node_id]
            self.sync()
            return True
        return False
    
    async def request(self, url: str, method: str = 'GET', **kwargs) -> Optional[Any]:
        """
        Make an HTTP request to a peer node.
        Returns the parsed JSON response or None on error.
        """
        try:
            response = await self.client.request(method, url, **kwargs)
            
            # Handle sync hints with 409
            if response.status_code == 409:
                return response.json()
            
            # Require success status for other responses
            if response.status_code < 200 or response.status_code >= 300:
                return None
            
            # Parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                return None
                
        except httpx.RequestError:
            # Re-raise network/transport errors to signal unreachability
            raise
            
    @classmethod
    async def request(cls, url: str, **kwargs):
        """Static compatibility method for HTTP requests"""
        instance = cls.get_instance()
        return await instance.request(url, **kwargs)
        
    # Compatibility methods for older code that used static methods
    
    def _update_last_message_impl(self, url: str):
        """
        Update the last_seen timestamp for a node by URL.
        Implementation method for update_last_message.
        """
        # Find the peer with this URL
        for node_id, peer in self.peers.items():
            if peer.get("url") == url:
                self.peers[node_id]["last_seen"] = timestamp()
                return
        
        # If not found, try to add it
        self._add_node_impl(url)

    @classmethod
    def update_last_message(cls, url: str):
        """Static compatibility method"""
        instance = cls.get_instance()
        instance._update_last_message_impl(url)

    # Add node compatibility
    def _add_node_impl(self, url: str) -> bool:
        """
        Add a node by URL. Will make a connection attempt.
        Implementation method for add_node.
        """
        if not url:
            return False
        
        # Normalize URL
        url = url.rstrip('/')
        
        # Check if we already have this URL
        for peer in self.peers.values():
            if peer.get("url") == url:
                # Already exists, update last_seen
                peer["last_seen"] = timestamp()
                self.sync()
                return True
        
        # This is a new URL - would normally connect to get node_id and pubkey
        # For compatibility, just add with placeholder values
        node_id = f"temp_{hashlib.sha256(url.encode()).hexdigest()[:16]}"
        self.peers[node_id] = {
            "url": url,
            "pubkey": "",  # Empty placeholder
            "last_seen": timestamp(),
            "is_public": True  # Assume public since it has a URL
        }
        self.sync()
        return True

    @classmethod
    def add_node(cls, url: str) -> bool:
        """Static compatibility method"""
        instance = cls.get_instance()
        return instance._add_node_impl(url)

    # Get_nodes compatibility
    def _get_nodes_impl(self) -> List[str]:
        """
        Get all node URLs.
        Implementation method for get_nodes.
        """
        return [peer["url"] for peer in self.peers.values() 
                if peer.get("url")]

    @classmethod
    def get_nodes(cls) -> List[str]:
        """Static compatibility method"""
        instance = cls.get_instance()
        return instance._get_nodes_impl()

    # Is_node_working compatibility
    async def _is_node_working_impl(self, url: str) -> bool:
        """
        Check if a node is responsive.
        Implementation method for is_node_working.
        """
        try:
            response = await self.client.get(f"{url}/get_status", timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("ok", False)
        except Exception:
            return False

    @classmethod
    async def is_node_working(cls, url: str) -> bool:
        """Static compatibility method"""
        instance = cls.get_instance()
        return await instance._is_node_working_impl(url)


class NodeInterface:
    """
    Interface for making authenticated requests to peer nodes.
    """
    def __init__(self, url: str, node_id: str = None):
        """
        Initialize with a node URL and optional node_id.
        """
        self.url = url
        self.base_url = url.rstrip('/')
        self.node_id = node_id
        self._handshake_completed = False
        
    async def ensure_handshake(self) -> bool:
        """
        Ensure handshake is completed and node_id is known.
        Returns True if handshake successful, False otherwise.
        """
        if self._handshake_completed and self.node_id:
            return True
            
        try:
            from stellaris.node.handshake_handler import get_handshake_manager
            handshake_manager = get_handshake_manager()
            
            success, node_id, info = await handshake_manager.do_handshake_with_peer(self.base_url)
            
            if success and node_id:
                self.node_id = node_id
                self._handshake_completed = True
                return True
                
        except Exception as e:
            print(f"Handshake failed with {self.base_url}: {e}")
        
        return False
    
    async def request(self, path: str, args: dict = None, sender_node: str = None):
        """
        Make a request to a node with optional sender information.
        """
        if not path.startswith('/'):
            path = '/' + path
            
        url = self.base_url + path
        headers = {}
        
        if sender_node:
            headers['Sender-Node'] = sender_node
            
        try:
            async with httpx.AsyncClient() as client:
                if args is None:
                    response = await client.get(url, headers=headers, timeout=30)
                else:
                    response = await client.post(url, json=args, headers=headers, timeout=30)
                    
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return {'ok': False, 'error': f"Error connecting to {url}"}
    
    async def get_nodes(self):
        """Get nodes from this peer with error handling"""
        try:
            response = await self.request('/get_nodes')
            if response and response.get('ok'):
                return response.get('result', [])
        except Exception as e:
            print(f"Error getting nodes from {self.base_url}: {e}")
        return []
    
    async def get_block(self, block_id: int):
        """Get block from this peer with error handling"""
        try:
            response = await self.request('/get_block', {'block': str(block_id)})
            if response and response.get('ok'):
                return response.get('result', {})
        except Exception as e:
            print(f"Error getting block {block_id} from {self.base_url}: {e}")
        return {}
    
    async def get_blocks(self, offset: int, limit: int):
        """Get blocks from this peer with error handling"""
        try:
            response = await self.request('/get_blocks', {'offset': offset, 'limit': limit})
            if response and response.get('ok'):
                return response.get('result', [])
        except Exception as e:
            print(f"Error getting blocks from {self.base_url}: {e}")
        return []
