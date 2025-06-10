"""
Relay Discovery Module

Specialized discovery functionality for finding Voxa relays on the network.
Relays can run on various ports and provide relay-specific endpoints for identification.
"""

import asyncio
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
import json
from .network_scanner import NetworkScanner
from util.logging import log


class RelayDiscovery:
    """
    Specialized discovery for Voxa relays.
    
    Handles:
    - Relay-specific port scanning (configurable ports)
    - Relay service identification
    - Relay capability detection
    - Relay health verification
    """
    
    # Common ports that relays might use (since port isn't decided yet)
    DEFAULT_RELAY_PORTS = [8080, 8081, 8082, 3000, 5000, 7000, 8000, 9001, 9002]
    
    # Relay-specific endpoints to probe
    RELAY_ENDPOINTS = [
        "/status/health",
        "/info/program_stats", 
        "/data/fetch_rri",
        "/info/settings",
        "/relay/status",
        "/relay/info"
    ]
    
    def __init__(self, scanner: Optional[NetworkScanner] = None, 
                 cache_duration: int = 300,
                 relay_ports: Optional[List[int]] = None):
        """
        Initialize relay discovery.
        
        Args:
            scanner: Network scanner instance (creates new if None)
            cache_duration: Cache duration in seconds for discovered relays
            relay_ports: Custom list of ports to scan for relays
        """
        self.scanner = scanner or NetworkScanner()
        self.cache_duration = cache_duration
        self.relay_ports = relay_ports or self.DEFAULT_RELAY_PORTS.copy()
        self.logger = log()
        self._relay_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def add_relay_port(self, port: int) -> None:
        """
        Add a port to scan for relays.
        
        Args:
            port: Port number to add
        """
        if port not in self.relay_ports:
            self.relay_ports.append(port)
            self.logger.info(f"Added port {port} to relay discovery")
    
    def remove_relay_port(self, port: int) -> None:
        """
        Remove a port from relay scanning.
        
        Args:
            port: Port number to remove
        """
        if port in self.relay_ports:
            self.relay_ports.remove(port)
            self.logger.info(f"Removed port {port} from relay discovery")
    
    def set_relay_ports(self, ports: List[int]) -> None:
        """
        Set the list of ports to scan for relays.
        
        Args:
            ports: List of port numbers
        """
        self.relay_ports = ports.copy()
        self.logger.info(f"Set relay ports to: {ports}")
    
    async def discover_relays(self, networks: Optional[List[str]] = None,
                            ports: Optional[List[int]] = None,
                            use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Discover Voxa relays on the network.
        
        Args:
            networks: Networks to scan (auto-detect if None)
            ports: Ports to scan (default: configured relay ports)
            use_cache: Whether to use cached results
            
        Returns:
            List of discovered relay information
        """
        if ports is None:
            ports = self.relay_ports
            
        # Check cache first
        if use_cache:
            cached_relays = self._get_cached_relays()
            if cached_relays:
                self.logger.info(f"Returning {len(cached_relays)} cached relays")
                return cached_relays
        
        self.logger.info(f"Starting relay discovery on ports: {ports}")
        
        # Use the network scanner to find potential services
        discovered_services = await self.scanner.discover_voxa_services(networks, ports)
        
        # Extract and verify relays
        potential_relays = discovered_services.get("relays", [])
        verified_relays = []
        
        for relay_info in potential_relays:
            verified_relay = await self._verify_relay(relay_info)
            if verified_relay:
                verified_relays.append(verified_relay)
                
        # Also check "unknown" services that might be relays
        for unknown_service in discovered_services.get("unknown", []):
            if unknown_service.get("port") in ports:
                verified_relay = await self._verify_relay(unknown_service)
                if verified_relay:
                    verified_relays.append(verified_relay)
        
        # Update cache
        self._update_cache(verified_relays)
        
        self.logger.info(f"Discovered {len(verified_relays)} verified relays")
        return verified_relays
    
    async def _verify_relay(self, relay_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Verify that a discovered service is actually a Voxa relay.
        
        Args:
            relay_info: Basic service information
            
        Returns:
            Enhanced relay information if verified, None otherwise
        """
        host = relay_info.get("host")
        port = relay_info.get("port")
        
        if not host or not port:
            return None
            
        try:
            # Probe relay-specific endpoints
            relay_data = await self._probe_relay_endpoints(host, port)
            
            if relay_data:
                # Enhance with additional information
                enhanced_info = {
                    "host": host,
                    "port": port,
                    "service_type": "relay",
                    "discovered_at": datetime.utcnow().isoformat(),
                    "endpoints": relay_data.get("available_endpoints", []),
                    "capabilities": relay_data.get("capabilities", []),
                    "status": relay_data.get("status", "unknown"),
                    "version": relay_data.get("version"),
                    "relay_id": relay_data.get("relay_id"),
                    "relay_type": relay_data.get("relay_type", "standard"),
                    "health": relay_data.get("health", {}),
                    "stats": relay_data.get("stats", {}),
                    "settings": relay_data.get("settings", {}),
                    "supported_protocols": relay_data.get("supported_protocols", []),
                    "load_info": relay_data.get("load_info", {})
                }
                
                self.logger.info(f"Verified relay at {host}:{port}")
                return enhanced_info
                
        except Exception as e:
            self.logger.debug(f"Failed to verify relay at {host}:{port}: {e}")
            
        return None
    
    async def _probe_relay_endpoints(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Probe relay-specific endpoints to gather information.
        
        Args:
            host: Relay host
            port: Relay port
            
        Returns:
            Collected relay information or None if not a valid relay
        """
        import httpx
        
        relay_data = {
            "available_endpoints": [],
            "capabilities": [],
            "status": "unknown",
            "supported_protocols": []
        }
        
        async with httpx.AsyncClient(timeout=self.scanner.timeout) as client:
            # Try each relay endpoint
            for endpoint in self.RELAY_ENDPOINTS:
                try:
                    url = f"http://{host}:{port}{endpoint}"
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        relay_data["available_endpoints"].append(endpoint)
                        
                        try:
                            data = response.json()
                            await self._process_endpoint_data(endpoint, data, relay_data)
                        except json.JSONDecodeError:
                            continue
                            
                except Exception as e:
                    self.logger.debug(f"Error probing {url}: {e}")
                    continue
            
            # Verify this looks like a relay
            if self._is_valid_relay(relay_data):
                return relay_data
                
        return None
    
    async def _process_endpoint_data(self, endpoint: str, data: Dict[str, Any],
                                   relay_data: Dict[str, Any]) -> None:
        """
        Process data from a specific endpoint.
        
        Args:
            endpoint: The endpoint that returned the data
            data: Response data
            relay_data: Relay data dictionary to update
        """
        if endpoint == "/status/health":
            relay_data["health"] = data
            relay_data["status"] = data.get("status", "unknown")
            if data.get("healthy"):
                relay_data["capabilities"].append("health_monitoring")
                
        elif endpoint == "/info/program_stats":
            relay_data["stats"] = data
            relay_data["version"] = data.get("program", {}).get("version")
            relay_data["capabilities"].append("statistics")
            
        elif endpoint == "/data/fetch_rri":
            relay_data["capabilities"].append("rri_storage")
            # Try to get relay count
            if isinstance(data, dict) and data.get("count", 0) > 0:
                relay_data["capabilities"].append("relay_registry")
                
        elif endpoint == "/info/settings":
            relay_data["settings"] = data
            relay_data["capabilities"].append("configuration")
            
            # Extract relay ID and type if available
            if isinstance(data, dict):
                relay_data["relay_id"] = data.get("relay_id") or data.get("id")
                relay_data["relay_type"] = data.get("relay_type", "standard")
                
        elif endpoint == "/relay/status":
            relay_data["capabilities"].append("relay_status")
            if isinstance(data, dict):
                relay_data["load_info"] = data.get("load", {})
                relay_data["supported_protocols"] = data.get("protocols", [])
                
        elif endpoint == "/relay/info":
            relay_data["capabilities"].append("relay_info")
            if isinstance(data, dict):
                relay_data["relay_type"] = data.get("type", "standard")
                relay_data["supported_protocols"].extend(data.get("protocols", []))
    
    def _is_valid_relay(self, relay_data: Dict[str, Any]) -> bool:
        """
        Determine if the collected data indicates a valid Voxa relay.
        
        Args:
            relay_data: Collected relay data
            
        Returns:
            True if this appears to be a valid Voxa relay
        """
        # Must have at least one endpoint
        if not relay_data.get("available_endpoints"):
            return False
            
        # Relay-specific endpoints are strong indicators
        relay_specific_endpoints = ["/relay/status", "/relay/info", "/data/fetch_rri"]
        for endpoint in relay_specific_endpoints:
            if endpoint in relay_data.get("available_endpoints", []):
                relay_data["capabilities"].append("relay_service")
                return True
                
        # Health endpoint with some capabilities
        if ("/status/health" in relay_data.get("available_endpoints", []) and 
            len(relay_data.get("capabilities", [])) > 0):
            return True
            
        # Must have at least 2 endpoints to be considered valid
        return len(relay_data.get("available_endpoints", [])) >= 2
    
    async def get_relay_details(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific relay.
        
        Args:
            host: Relay host
            port: Relay port
            
        Returns:
            Detailed relay information or None if not accessible
        """
        return await self._verify_relay({"host": host, "port": port})
    
    async def ping_relay(self, host: str, port: int) -> bool:
        """
        Quick ping to check if a relay is responsive.
        
        Args:
            host: Relay host
            port: Relay port
            
        Returns:
            True if relay responds, False otherwise
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                # Try multiple endpoints
                endpoints = ["/status/health", "/relay/status", "/info/program_stats"]
                
                for endpoint in endpoints:
                    try:
                        url = f"http://{host}:{port}{endpoint}"
                        response = await client.get(url)
                        if response.status_code == 200:
                            return True
                    except Exception:
                        continue
                        
        except Exception:
            pass
            
        return False
    
    async def discover_relay_by_type(self, relay_type: str, 
                                   networks: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Discover relays of a specific type.
        
        Args:
            relay_type: Type of relay to find (e.g., "standard", "high_capacity", "secure")
            networks: Networks to scan
            
        Returns:
            List of relays matching the specified type
        """
        all_relays = await self.discover_relays(networks, use_cache=True)
        
        matching_relays = [
            relay for relay in all_relays 
            if relay.get("relay_type") == relay_type
        ]
        
        self.logger.info(f"Found {len(matching_relays)} relays of type '{relay_type}'")
        return matching_relays
    
    def _get_cached_relays(self) -> List[Dict[str, Any]]:
        """
        Get relays from cache if still valid.
        
        Returns:
            List of cached relays or empty list if cache is stale
        """
        current_time = datetime.utcnow()
        valid_relays = []
        
        for relay_key, timestamp in list(self._cache_timestamps.items()):
            if current_time - timestamp < timedelta(seconds=self.cache_duration):
                if relay_key in self._relay_cache:
                    valid_relays.append(self._relay_cache[relay_key])
            else:
                # Remove stale entries
                self._cache_timestamps.pop(relay_key, None)
                self._relay_cache.pop(relay_key, None)
                
        return valid_relays
    
    def _update_cache(self, relays: List[Dict[str, Any]]) -> None:
        """
        Update the relay cache with discovered relays.
        
        Args:
            relays: List of discovered relays
        """
        current_time = datetime.utcnow()
        
        for relay in relays:
            relay_key = f"{relay['host']}:{relay['port']}"
            self._relay_cache[relay_key] = relay
            self._cache_timestamps[relay_key] = current_time
    
    def clear_cache(self) -> None:
        """Clear the relay discovery cache."""
        self._relay_cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("Relay discovery cache cleared")
    
    def get_cached_relay_count(self) -> int:
        """
        Get the number of relays in cache.
        
        Returns:
            Number of cached relays
        """
        return len(self._get_cached_relays())
    
    def get_relay_ports(self) -> List[int]:
        """
        Get the current list of ports being scanned for relays.
        
        Returns:
            List of relay ports
        """
        return self.relay_ports.copy()