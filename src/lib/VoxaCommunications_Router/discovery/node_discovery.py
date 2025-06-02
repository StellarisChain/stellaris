"""
Node Discovery Module

Specialized discovery functionality for finding Voxa nodes on the network.
Nodes typically run on port 9000 and provide specific endpoints for identification.
"""

import asyncio
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
import json
from VoxaCommunications_Router.discovery.network_scanner import NetworkScanner
from VoxaCommunications_Router.util.logging import log

class NodeDiscovery:
    """
    Specialized discovery for Voxa nodes.
    
    Handles:
    - Node-specific port scanning (default: 9000)
    - Node service identification
    - Node capability detection
    - Node health verification
    """
    
    # Default port for Voxa nodes
    DEFAULT_NODE_PORT = 9000
    
    # Node-specific endpoints to probe
    NODE_ENDPOINTS = [
        "/status/health",
        "/info/program_stats",
        "/data/fetch_nri",
        "/info/settings"
    ]
    
    def __init__(self, scanner: Optional[NetworkScanner] = None, cache_duration: int = 300):
        """
        Initialize node discovery.
        
        Args:
            scanner: Network scanner instance (creates new if None)
            cache_duration: Cache duration in seconds for discovered nodes
        """
        self.scanner = scanner or NetworkScanner()
        self.cache_duration = cache_duration
        self.logger = log()
        self._node_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    async def discover_nodes(self, networks: Optional[List[str]] = None, 
                           ports: Optional[List[int]] = None,
                           use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Discover Voxa nodes on the network.
        
        Args:
            networks: Networks to scan (auto-detect if None)
            ports: Ports to scan (default: [9000])
            use_cache: Whether to use cached results
            
        Returns:
            List of discovered node information
        """
        if ports is None:
            ports = [self.DEFAULT_NODE_PORT]
            
        # Check cache first
        if use_cache:
            cached_nodes = self._get_cached_nodes()
            if cached_nodes:
                self.logger.info(f"Returning {len(cached_nodes)} cached nodes")
                return cached_nodes
        
        self.logger.info(f"Starting node discovery on ports: {ports}")
        
        # Use the network scanner to find potential services
        discovered_services = await self.scanner.discover_voxa_services(networks, ports)
        
        # Extract and verify nodes
        potential_nodes = discovered_services.get("nodes", [])
        verified_nodes = []
        
        for node_info in potential_nodes:
            verified_node = await self._verify_node(node_info)
            if verified_node:
                verified_nodes.append(verified_node)
                
        # Also check "unknown" services that might be nodes
        for unknown_service in discovered_services.get("unknown", []):
            if unknown_service.get("port") in ports:
                verified_node = await self._verify_node(unknown_service)
                if verified_node:
                    verified_nodes.append(verified_node)
        
        # Update cache
        self._update_cache(verified_nodes)
        
        self.logger.info(f"Discovered {len(verified_nodes)} verified nodes")
        return verified_nodes
    
    async def _verify_node(self, node_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Verify that a discovered service is actually a Voxa node.
        
        Args:
            node_info: Basic service information
            
        Returns:
            Enhanced node information if verified, None otherwise
        """
        host = node_info.get("host")
        port = node_info.get("port")
        
        if not host or not port:
            return None
            
        try:
            # Probe node-specific endpoints
            node_data = await self._probe_node_endpoints(host, port)
            
            if node_data:
                # Enhance with additional information
                enhanced_info = {
                    "host": host,
                    "port": port,
                    "node_type": "node",
                    "discovered_at": datetime.utcnow().isoformat(),
                    "endpoints": node_data.get("available_endpoints", []),
                    "capabilities": node_data.get("capabilities", []),
                    "status": node_data.get("status", "unknown"),
                    "version": node_data.get("version"),
                    "node_id": node_data.get("node_id"),
                    "health": node_data.get("health", {}),
                    "stats": node_data.get("stats", {}),
                    "settings": node_data.get("settings", {})
                }
                
                self.logger.info(f"Verified node at {host}:{port}")
                return enhanced_info
                
        except Exception as e:
            self.logger.debug(f"Failed to verify node at {host}:{port}: {e}")
            
        return None
    
    async def _probe_node_endpoints(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Probe node-specific endpoints to gather information.
        
        Args:
            host: Node host
            port: Node port
            
        Returns:
            Collected node information or None if not a valid node
        """
        import httpx
        
        node_data = {
            "available_endpoints": [],
            "capabilities": [],
            "status": "unknown"
        }
        
        async with httpx.AsyncClient(timeout=self.scanner.timeout) as client:
            # Try each node endpoint
            for endpoint in self.NODE_ENDPOINTS:
                try:
                    url = f"http://{host}:{port}{endpoint}"
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        node_data["available_endpoints"].append(endpoint)
                        
                        try:
                            data = response.json()
                            await self._process_endpoint_data(endpoint, data, node_data)
                        except json.JSONDecodeError:
                            continue
                            
                except Exception as e:
                    self.logger.debug(f"Error probing {url}: {e}")
                    continue
            
            # Verify this looks like a node
            if self._is_valid_node(node_data):
                return node_data
                
        return None
    
    async def _process_endpoint_data(self, endpoint: str, data: Dict[str, Any], 
                                   node_data: Dict[str, Any]) -> None:
        """
        Process data from a specific endpoint.
        
        Args:
            endpoint: The endpoint that returned the data
            data: Response data
            node_data: Node data dictionary to update
        """
        if endpoint == "/status/health":
            node_data["health"] = data
            node_data["status"] = data.get("status", "unknown")
            if data.get("healthy"):
                node_data["capabilities"].append("health_monitoring")
                
        elif endpoint == "/info/program_stats":
            node_data["stats"] = data
            node_data["version"] = data.get("program", {}).get("version")
            node_data["capabilities"].append("statistics")
            
        elif endpoint == "/data/fetch_nri":
            node_data["capabilities"].append("nri_storage")
            # Try to get node count
            if isinstance(data, dict) and data.get("count", 0) > 0:
                node_data["capabilities"].append("node_registry")
                
        elif endpoint == "/info/settings":
            node_data["settings"] = data
            node_data["capabilities"].append("configuration")
            
            # Extract node ID if available
            if isinstance(data, dict):
                node_data["node_id"] = data.get("node_id") or data.get("id")
    
    def _is_valid_node(self, node_data: Dict[str, Any]) -> bool:
        """
        Determine if the collected data indicates a valid Voxa node.
        
        Args:
            node_data: Collected node data
            
        Returns:
            True if this appears to be a valid Voxa node
        """
        # Must have at least one endpoint
        if not node_data.get("available_endpoints"):
            return False
            
        # Must have some capabilities
        if not node_data.get("capabilities"):
            return False
            
        # Health endpoint is a strong indicator
        if "/status/health" in node_data.get("available_endpoints", []):
            return True
            
        # Statistics endpoint is also a good indicator
        if "/info/program_stats" in node_data.get("available_endpoints", []):
            return True
            
        # Must have at least 2 endpoints to be considered valid
        return len(node_data.get("available_endpoints", [])) >= 2
    
    async def get_node_details(self, host: str, port: int = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific node.
        
        Args:
            host: Node host
            port: Node port (default: 9000)
            
        Returns:
            Detailed node information or None if not accessible
        """
        if port is None:
            port = self.DEFAULT_NODE_PORT
            
        return await self._verify_node({"host": host, "port": port})
    
    async def ping_node(self, host: str, port: int = None) -> bool:
        """
        Quick ping to check if a node is responsive.
        
        Args:
            host: Node host
            port: Node port (default: 9000)
            
        Returns:
            True if node responds, False otherwise
        """
        if port is None:
            port = self.DEFAULT_NODE_PORT
            
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"http://{host}:{port}/status/health"
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
    
    def _get_cached_nodes(self) -> List[Dict[str, Any]]:
        """
        Get nodes from cache if still valid.
        
        Returns:
            List of cached nodes or empty list if cache is stale
        """
        current_time = datetime.utcnow()
        valid_nodes = []
        
        for node_key, timestamp in list(self._cache_timestamps.items()):
            if current_time - timestamp < timedelta(seconds=self.cache_duration):
                if node_key in self._node_cache:
                    valid_nodes.append(self._node_cache[node_key])
            else:
                # Remove stale entries
                self._cache_timestamps.pop(node_key, None)
                self._node_cache.pop(node_key, None)
                
        return valid_nodes
    
    def _update_cache(self, nodes: List[Dict[str, Any]]) -> None:
        """
        Update the node cache with discovered nodes.
        
        Args:
            nodes: List of discovered nodes
        """
        current_time = datetime.utcnow()
        
        for node in nodes:
            node_key = f"{node['host']}:{node['port']}"
            self._node_cache[node_key] = node
            self._cache_timestamps[node_key] = current_time
    
    def clear_cache(self) -> None:
        """Clear the node discovery cache."""
        self._node_cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("Node discovery cache cleared")
    
    def get_cached_node_count(self) -> int:
        """
        Get the number of nodes in cache.
        
        Returns:
            Number of cached nodes
        """
        return len(self._get_cached_nodes())