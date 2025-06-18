"""
Discovery Manager

Main orchestrator for Voxa network discovery operations.
Provides a unified interface for discovering nodes, relays, and managing discovery operations.
"""

import asyncio
from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
import json
from lib.VoxaCommunications_Router.discovery.network_scanner import NetworkScanner
from lib.VoxaCommunications_Router.discovery.node_discovery import NodeDiscovery
from lib.VoxaCommunications_Router.discovery.relay_discovery import RelayDiscovery
from lib.VoxaCommunications_Router.util.logging import log
from lib.VoxaCommunications_Router.util.jsonreader import read_json_from_namespace

class DiscoveryManager:
    """
    Central manager for all Voxa discovery operations.
    
    Provides:
    - Unified discovery interface
    - Configuration management
    - Discovery scheduling
    - Result aggregation and filtering
    - Integration with existing NRI/RRI systems
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the discovery manager.
        
        Args:
            config: Optional configuration override
        """
        self.logger = log()
        self.config = config or self._load_config()
        
        # Initialize discovery components
        self.scanner = NetworkScanner(
            timeout=self.config.get("timeout", 3.0),
            max_workers=self.config.get("max_workers", 50),
            config=self.config  # Pass full config to scanner
        )
        
        self.node_discovery = NodeDiscovery(
            scanner=self.scanner,
            cache_duration=self.config.get("cache_duration", 300)
        )
        
        relay_ports = self.config.get("relay_ports")
        self.relay_discovery = RelayDiscovery(
            scanner=self.scanner,
            cache_duration=self.config.get("cache_duration", 300),
            relay_ports=relay_ports
        )
        
        # Discovery state
        self._last_full_discovery: Optional[datetime] = None
        self._discovery_in_progress = False
        self._discovery_results: Dict[str, Any] = {
            "nodes": [],
            "relays": [],
            "last_updated": None
        }
        
        self.logger.info("Discovery Manager initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load discovery configuration from various sources.
        
        Returns:
            Discovery configuration dictionary
        """
        config = {
            "timeout": 3.0,
            "max_workers": 50,
            "cache_duration": 300,
            "auto_discovery_interval": 600,  # 10 minutes
            "networks": None,  # Auto-detect
            "node_ports": [9999, 10000, 10001, 10002, 10003, 10004, 10005],
            "relay_ports": [8080, 8081, 8082, 3000, 5000, 7000, 8000, 9001, 9002]
        }
        
        try:
            # Try to load from p2p config
            p2p_config = read_json_from_namespace("config.p2p")
            if p2p_config:
                config["max_workers"] = p2p_config.get("maxPeers", 50)
                
            # Try to load discovery-specific config if it exists
            discovery_config = read_json_from_namespace("config.discovery")
            if discovery_config:
                config.update(discovery_config)
                
        except Exception as e:
            self.logger.warning(f"Could not load discovery config: {e}")
            
        return config
    
    async def discover_all(self, networks: Optional[List[str]] = None,
                          force_refresh: bool = False) -> Dict[str, Any]:
        """
        Discover all Voxa services (nodes and relays).
        
        Args:
            networks: Networks to scan (auto-detect if None)
            force_refresh: Force new discovery even if cache is valid
            
        Returns:
            Dictionary with discovered nodes and relays
        """
        if self._discovery_in_progress:
            self.logger.info("Discovery already in progress, waiting...")
            while self._discovery_in_progress:
                await asyncio.sleep(1)
            return self._discovery_results.copy()
        
        self._discovery_in_progress = True
        
        try:
            self.logger.info("Starting comprehensive Voxa service discovery")
            
            # Run node and relay discovery concurrently
            node_task = self.node_discovery.discover_nodes(
                networks=networks,
                use_cache=not force_refresh,
                ports=self.config.get("node_ports", [9999, 10000, 10001, 10002, 10003, 10004, 10005])
            )
            
            relay_task = self.relay_discovery.discover_relays(
                networks=networks,
                use_cache=not force_refresh
            )
            
            nodes, relays = await asyncio.gather(node_task, relay_task)
            
            # Update results
            self._discovery_results = {
                "nodes": nodes,
                "relays": relays,
                "last_updated": datetime.utcnow().isoformat(),
                "total_services": len(nodes) + len(relays)
            }
            
            self._last_full_discovery = datetime.utcnow()
            
            # Optionally save to NRI/RRI storage
            if self.config.get("auto_save_to_storage", True):
                await self._save_to_storage(nodes, relays)
            
            self.logger.info(f"Discovery complete: {len(nodes)} nodes, {len(relays)} relays")
            
            return self._discovery_results.copy()
            
        finally:
            self._discovery_in_progress = False
    
    async def discover_nodes_only(self, networks: Optional[List[str]] = None,
                                 force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover only Voxa nodes.
        
        Args:
            networks: Networks to scan
            force_refresh: Force new discovery
            
        Returns:
            List of discovered nodes
        """
        self.logger.info("Starting node-only discovery")
        
        nodes = await self.node_discovery.discover_nodes(
            networks=networks,
            use_cache=not force_refresh
        )
        
        # Update nodes in results
        self._discovery_results["nodes"] = nodes
        self._discovery_results["last_updated"] = datetime.utcnow().isoformat()
        
        return nodes
    
    async def discover_relays_only(self, networks: Optional[List[str]] = None,
                                  force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover only Voxa relays.
        
        Args:
            networks: Networks to scan
            force_refresh: Force new discovery
            
        Returns:
            List of discovered relays
        """
        self.logger.info("Starting relay-only discovery")
        
        relays = await self.relay_discovery.discover_relays(
            networks=networks,
            use_cache=not force_refresh
        )
        
        # Update relays in results
        self._discovery_results["relays"] = relays
        self._discovery_results["last_updated"] = datetime.utcnow().isoformat()
        
        return relays
    
    async def find_service(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Check if a specific host:port is running a Voxa service.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            Service information if found, None otherwise
        """
        self.logger.info(f"Checking for Voxa service at {host}:{port}")
        
        # Try as node first (if port matches)
        if port == 9000:
            node_info = await self.node_discovery.get_node_details(host, port)
            if node_info:
                return node_info
        
        # Try as relay
        relay_info = await self.relay_discovery.get_relay_details(host, port)
        if relay_info:
            return relay_info
        
        # Try generic probe
        result = await self.scanner.probe_voxa_service(host, port)
        return result
    
    async def ping_service(self, host: str, port: int) -> bool:
        """
        Quick ping to check if a service is responsive.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            True if service responds
        """
        if port == 9000:
            return await self.node_discovery.ping_node(host, port)
        else:
            return await self.relay_discovery.ping_relay(host, port)
    
    async def get_network_overview(self) -> Dict[str, Any]:
        """
        Get a comprehensive overview of the Voxa network.
        
        Returns:
            Network overview with statistics and service information
        """
        # Ensure we have recent discovery data
        if (not self._last_full_discovery or 
            datetime.utcnow() - self._last_full_discovery > timedelta(minutes=10)):
            await self.discover_all()
        
        nodes = self._discovery_results.get("nodes", [])
        relays = self._discovery_results.get("relays", [])
        
        # Calculate statistics
        total_services = len(nodes) + len(relays)
        healthy_nodes = sum(1 for node in nodes if node.get("status") == "online")
        healthy_relays = sum(1 for relay in relays if relay.get("status") == "online")
        
        # Group by network
        networks = {}
        for service in nodes + relays:
            host = service.get("host", "")
            network = ".".join(host.split(".")[:3]) + ".0/24"
            if network not in networks:
                networks[network] = {"nodes": 0, "relays": 0}
            
            if service in nodes:
                networks[network]["nodes"] += 1
            else:
                networks[network]["relays"] += 1
        
        return {
            "total_services": total_services,
            "nodes": {
                "total": len(nodes),
                "healthy": healthy_nodes,
                "capabilities": self._get_capabilities_summary(nodes)
            },
            "relays": {
                "total": len(relays),
                "healthy": healthy_relays,
                "types": self._get_relay_types(relays),
                "capabilities": self._get_capabilities_summary(relays)
            },
            "networks": networks,
            "last_discovery": self._discovery_results.get("last_updated"),
            "discovery_config": {
                "node_ports": self.config.get("node_ports", [9999, 10000, 10001, 10002, 10003, 10004, 10005]),
                "relay_ports": self.relay_discovery.get_relay_ports(),
                "cache_duration": self.config.get("cache_duration", 300)
            }
        }
    
    def _get_capabilities_summary(self, services: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get a summary of capabilities across services."""
        capabilities = {}
        for service in services:
            for capability in service.get("capabilities", []):
                capabilities[capability] = capabilities.get(capability, 0) + 1
        return capabilities
    
    def _get_relay_types(self, relays: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get a summary of relay types."""
        types = {}
        for relay in relays:
            relay_type = relay.get("relay_type", "unknown")
            types[relay_type] = types.get(relay_type, 0) + 1
        return types
    
    async def _save_to_storage(self, nodes: List[Dict[str, Any]], 
                              relays: List[Dict[str, Any]]) -> None:
        """
        Save discovered services to NRI/RRI storage.
        
        Args:
            nodes: Discovered nodes
            relays: Discovered relays
        """
        try:
            # This would integrate with the existing NRI/RRI storage system
            # For now, just log the intention
            self.logger.info(f"Would save {len(nodes)} nodes and {len(relays)} relays to storage")
            
            # TODO: Integrate with existing NRI/RRI API endpoints
            # - POST to /data/add_nri for each node
            # - POST to /data/add_rri for each relay
            
        except Exception as e:
            self.logger.error(f"Error saving to storage: {e}")
    
    def configure_relay_ports(self, ports: List[int]) -> None:
        """
        Configure the ports to scan for relays.
        
        Args:
            ports: List of port numbers
        """
        self.relay_discovery.set_relay_ports(ports)
        self.config["relay_ports"] = ports
        self.logger.info(f"Updated relay ports to: {ports}")
    
    def add_relay_port(self, port: int) -> None:
        """
        Add a port to scan for relays.
        
        Args:
            port: Port number to add
        """
        self.relay_discovery.add_relay_port(port)
        if "relay_ports" not in self.config:
            self.config["relay_ports"] = self.relay_discovery.get_relay_ports()
        elif port not in self.config["relay_ports"]:
            self.config["relay_ports"].append(port)
    
    def clear_all_caches(self) -> None:
        """Clear all discovery caches."""
        self.node_discovery.clear_cache()
        self.relay_discovery.clear_cache()
        self._discovery_results = {"nodes": [], "relays": [], "last_updated": None}
        self._last_full_discovery = None
        self.logger.info("All discovery caches cleared")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get the status of discovery caches.
        
        Returns:
            Cache status information
        """
        return {
            "nodes_cached": self.node_discovery.get_cached_node_count(),
            "relays_cached": self.relay_discovery.get_cached_relay_count(),
            "last_full_discovery": self._last_full_discovery.isoformat() if self._last_full_discovery else None,
            "cache_duration": self.config.get("cache_duration", 300),
            "discovery_in_progress": self._discovery_in_progress
        }
    
    async def start_auto_discovery(self, interval: Optional[int] = None) -> None:
        """
        Start automatic periodic discovery.
        
        Args:
            interval: Discovery interval in seconds (uses config default if None)
        """
        if interval is None:
            interval = self.config.get("auto_discovery_interval", 600)
        
        self.logger.info(f"Starting auto-discovery with {interval}s interval")
        
        while True:
            try:
                await self.discover_all()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                self.logger.info("Auto-discovery cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in auto-discovery: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    def enable_public_ip_discovery(self, public_ip_ranges: List[str], 
                                   max_hosts_per_range: int = 1000) -> None:
        """
        Enable public IP discovery with specified ranges.
        
        Args:
            public_ip_ranges: List of public IP CIDR ranges to scan
            max_hosts_per_range: Maximum hosts to scan per range
        """
        self.config["allow_public_ip_discovery"] = True
        self.config["public_ip_ranges"] = public_ip_ranges
        self.config["max_public_hosts_per_range"] = max_hosts_per_range
        
        # Update scanner configuration
        self.scanner.allow_public_ip_discovery = True
        self.scanner.public_ip_ranges = public_ip_ranges
        self.scanner.max_public_hosts_per_range = max_hosts_per_range
        
        self.logger.warning("⚠️  PUBLIC IP DISCOVERY ENABLED")
        self.logger.warning(f"⚠️  Will scan public ranges: {public_ip_ranges}")
        self.logger.warning("⚠️  Ensure you have permission to scan these ranges!")
    
    def disable_public_ip_discovery(self) -> None:
        """Disable public IP discovery and revert to local-only scanning."""
        self.config["allow_public_ip_discovery"] = False
        self.config["scan_local_only"] = True
        
        # Update scanner configuration
        self.scanner.allow_public_ip_discovery = False
        self.scanner.scan_local_only = True
        
        self.logger.info("Public IP discovery disabled - reverted to local-only scanning")
    
    def get_public_ip_config(self) -> Dict[str, Any]:
        """
        Get current public IP discovery configuration.
        
        Returns:
            Dictionary with public IP discovery settings
        """
        return {
            "allow_public_ip_discovery": self.config.get("allow_public_ip_discovery", False),
            "scan_local_only": self.config.get("scan_local_only", True),
            "public_ip_ranges": self.config.get("public_ip_ranges", []),
            "max_public_hosts_per_range": self.config.get("max_public_hosts_per_range", 1000),
            "rate_limit_public_scans": self.config.get("rate_limit_public_scans", True),
            "public_scan_delay_ms": self.config.get("public_scan_delay_ms", 100)
        }
    
    def configure_public_ip_scanning(self, rate_limit: bool = True, 
                                   delay_ms: int = 100) -> None:
        """
        Configure public IP scanning behavior.
        
        Args:
            rate_limit: Whether to rate limit public IP scans
            delay_ms: Delay between scans in milliseconds
        """
        self.config["rate_limit_public_scans"] = rate_limit
        self.config["public_scan_delay_ms"] = delay_ms
        
        # Update scanner configuration
        self.scanner.rate_limit_public_scans = rate_limit
        self.scanner.public_scan_delay_ms = delay_ms
        
        self.logger.info(f"Updated public IP scan rate limiting: {rate_limit}, delay: {delay_ms}ms")