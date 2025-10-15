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

# Decentralized bootstrap nodes list - multiple nodes for redundancy
DEFAULT_BOOTSTRAP_NODES = [
    'https://stellaris-node.connor33341.dev',
    # Add more bootstrap nodes here for production
]

# Get environment variables with defaults
MAIN_STELLARIS_NODE_URL = os.environ.get('MAIN_STELLARIS_NODE_URL', DEFAULT_BOOTSTRAP_NODES[0])
BOOTSTRAP_NODES = os.environ.get('STELLARIS_BOOTSTRAP_NODES', ','.join(DEFAULT_BOOTSTRAP_NODES)).split(',')
SELF_URL = os.environ.get('STELLARIS_SELF_URL', None)

# Peer discovery settings
PEER_EXCHANGE_INTERVAL = 60 * 10  # Exchange peers every 10 minutes
PEER_EXCHANGE_COUNT = 20  # Number of peers to exchange per request
MIN_PEERS_FOR_DISCOVERY = 5  # Minimum peers before triggering discovery

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
    
    def _sync_to_disk(self):
        """
        Internal method to persist the peer registry to disk
        """
        with open(path, 'wt') as f:
            json.dump({"peers": self.peers}, f)
            
    @classmethod
    def sync(cls):
        """Persist peer registry to disk (static compatibility method)"""
        instance = cls.get_instance()
        instance._sync_to_disk()
    
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
    
    async def discover_peers_from_bootstrap(self) -> int:
        """
        Discover peers from bootstrap nodes.
        Returns the number of new peers discovered.
        
        This method provides decentralized peer discovery by:
        1. Connecting to multiple bootstrap nodes (not just one)
        2. Requesting their peer lists
        3. Adding new peers to our registry
        """
        new_peers_count = 0
        
        for bootstrap_url in BOOTSTRAP_NODES:
            try:
                # Skip if this is our own URL
                if bootstrap_url == SELF_URL:
                    continue
                
                # Request peers from bootstrap node
                response = await self.client.get(
                    f"{bootstrap_url.rstrip('/')}/get_nodes",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok') and 'result' in data:
                        peers_list = data['result']
                        
                        # Add each peer to our registry
                        for peer_data in peers_list:
                            node_id = peer_data.get('node_id')
                            url = peer_data.get('url')
                            pubkey = peer_data.get('pubkey', '')
                            
                            if node_id and url and node_id != self.node_id:
                                # Add or update peer
                                is_new = self.add_or_update_peer(
                                    node_id, pubkey, url, is_public=True
                                )
                                if is_new:
                                    new_peers_count += 1
                        
                        print(f"Discovered {len(peers_list)} peers from {bootstrap_url}")
            
            except Exception as e:
                print(f"Failed to discover peers from {bootstrap_url}: {e}")
                continue
        
        return new_peers_count
    
    async def exchange_peers_with_peer(self, peer_url: str) -> int:
        """
        Exchange peer lists with a specific peer (gossip protocol).
        Returns the number of new peers discovered.
        
        This implements a gossip-based peer discovery where nodes share
        their peer lists with each other, creating a decentralized network.
        """
        new_peers_count = 0
        
        try:
            # Request peers from the peer
            response = await self.client.get(
                f"{peer_url.rstrip('/')}/get_nodes",
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and 'result' in data:
                    peers_list = data['result'][:PEER_EXCHANGE_COUNT]
                    
                    # Add each peer to our registry
                    for peer_data in peers_list:
                        node_id = peer_data.get('node_id')
                        url = peer_data.get('url')
                        pubkey = peer_data.get('pubkey', '')
                        
                        if node_id and url and node_id != self.node_id:
                            is_new = self.add_or_update_peer(
                                node_id, pubkey, url, is_public=True
                            )
                            if is_new:
                                new_peers_count += 1
        
        except Exception as e:
            print(f"Failed to exchange peers with {peer_url}: {e}")
        
        return new_peers_count
    
    async def run_peer_discovery(self) -> Dict[str, int]:
        """
        Run comprehensive peer discovery process.
        Returns statistics about the discovery process.
        
        This method implements a multi-strategy peer discovery:
        1. If we have few peers, connect to bootstrap nodes
        2. Exchange peers with existing active peers (gossip)
        3. Maintain a healthy peer count
        """
        stats = {
            'bootstrap_peers': 0,
            'exchanged_peers': 0,
            'total_peers': len(self.peers)
        }
        
        # Strategy 1: If we have few peers, use bootstrap nodes
        if len(self.peers) < MIN_PEERS_FOR_DISCOVERY:
            print(f"Low peer count ({len(self.peers)}), discovering from bootstrap nodes...")
            stats['bootstrap_peers'] = await self.discover_peers_from_bootstrap()
        
        # Strategy 2: Exchange peers with active peers (gossip protocol)
        recent_peers = self._get_recent_nodes_impl()
        
        # Select a random subset of peers to exchange with
        exchange_count = min(5, len(recent_peers))
        if exchange_count > 0:
            peers_to_exchange = random.sample(recent_peers, exchange_count)
            
            for peer in peers_to_exchange:
                peer_url = peer.get('url')
                if peer_url:
                    discovered = await self.exchange_peers_with_peer(peer_url)
                    stats['exchanged_peers'] += discovered
        
        stats['total_peers'] = len(self.peers)
        
        print(f"Peer discovery complete: {stats['bootstrap_peers']} from bootstrap, "
              f"{stats['exchanged_peers']} from exchange, {stats['total_peers']} total")
        
        return stats
    
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
    def __init__(self, url: str):
        """
        Initialize with a node URL.
        """
        self.url = url
        self.base_url = url.rstrip('/')
    
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
