"""
Network Scanner Module

Provides low-level network scanning capabilities for discovering Voxa nodes and relays.
Includes port scanning, ping functionality, and network range detection.
"""

import asyncio
import socket
import ipaddress
import time
from typing import List, Dict, Set, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import httpx
from lib.VoxaCommunications_Router.util.logging import log


class NetworkScanner:
    """
    Core network scanner for discovering Voxa network components.
    
    Handles:
    - Port scanning for specific services
    - Network range scanning
    - Service identification
    - Concurrent scanning operations
    """
    
    def __init__(self, timeout: float = 3.0, max_workers: int = 50, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the network scanner.
        
        Args:
            timeout: Socket timeout for connections
            max_workers: Maximum concurrent scanning threads
            config: Configuration dictionary with discovery settings
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.config = config or {}
        self.logger = log()
        
        # Public IP discovery settings
        self.allow_public_ip_discovery = self.config.get("allow_public_ip_discovery", False)
        self.scan_local_only = self.config.get("scan_local_only", True)
        self.public_ip_ranges = self.config.get("public_ip_ranges", [])
        self.max_public_hosts_per_range = self.config.get("max_public_hosts_per_range", 1000)
        self.public_discovery_warning = self.config.get("public_discovery_warning", True)
        self.rate_limit_public_scans = self.config.get("rate_limit_public_scans", True)
        self.public_scan_delay_ms = self.config.get("public_scan_delay_ms", 100)
        
        if self.allow_public_ip_discovery and self.public_discovery_warning:
            self.logger.warning("⚠️  PUBLIC IP DISCOVERY ENABLED - This will scan beyond local networks!")
            self.logger.warning("⚠️  Ensure you have permission to scan the configured IP ranges!")
        
    def get_networks_to_scan(self) -> List[str]:
        """
        Get network ranges for scanning based on configuration.
        
        Returns:
            List of network CIDR strings to scan
        """
        networks = []
        
        # Always include local networks unless explicitly disabled
        if not self.scan_local_only or not self.allow_public_ip_discovery:
            networks.extend(self.get_local_networks())
        
        # Add public IP ranges if enabled
        if self.allow_public_ip_discovery and self.public_ip_ranges:
            self.logger.warning(f"Adding public IP ranges to scan: {self.public_ip_ranges}")
            networks.extend(self.public_ip_ranges)
            
        return networks
        
    def get_local_networks(self) -> List[str]:
        """
        Get local network ranges for scanning.
        
        Returns:
            List of network CIDR strings to scan
        """
        networks = []
        
        try:
            # Get all network interfaces
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Add common private network ranges
            private_ranges = [
                "192.168.0.0/24",
                "192.168.1.0/24", 
                "10.0.0.0/24",
                "172.16.0.0/24"
            ]
            
            # Try to detect actual local network
            try:
                # Create a socket to detect local network
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                
                # Convert to network range
                network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
                networks.append(str(network))
                
            except Exception as e:
                self.logger.warning(f"Could not detect local network: {e}")
                
            # Add private ranges as fallback
            networks.extend(private_ranges)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_networks = []
            for network in networks:
                if network not in seen:
                    seen.add(network)
                    unique_networks.append(network)
                    
            self.logger.info(f"Detected local networks: {unique_networks}")
            return unique_networks
            
        except Exception as e:
            self.logger.error(f"Error getting local networks: {e}")
            return ["192.168.1.0/24"]  # Fallback
    
    def scan_port(self, host: str, port: int) -> bool:
        """
        Scan a single port on a host.
        
        Args:
            host: Target host IP or hostname
            port: Port number to scan
            
        Returns:
            True if port is open, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception:
            return False
    
    def scan_host_ports(self, host: str, ports: List[int]) -> Dict[int, bool]:
        """
        Scan multiple ports on a single host.
        
        Args:
            host: Target host IP or hostname
            ports: List of ports to scan
            
        Returns:
            Dictionary mapping port numbers to open status
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(len(ports), 10)) as executor:
            future_to_port = {
                executor.submit(self.scan_port, host, port): port 
                for port in ports
            }
            
            for future in as_completed(future_to_port):
                port = future_to_port[future]
                try:
                    results[port] = future.result()
                except Exception as e:
                    self.logger.debug(f"Error scanning {host}:{port} - {e}")
                    results[port] = False
                    
        return results
    
    def scan_network_range(self, network: str, ports: List[int]) -> Dict[str, Dict[int, bool]]:
        """
        Scan a network range for open ports.
        
        Args:
            network: Network in CIDR format (e.g., "192.168.1.0/24")
            ports: List of ports to scan
            
        Returns:
            Dictionary mapping host IPs to port scan results
        """
        results = {}
        
        try:
            network_obj = ipaddress.IPv4Network(network, strict=False)
            hosts = list(network_obj.hosts())
            
            # Check if this is a private network
            is_private = network_obj.is_private
            
            if not is_private:
                # This is a public IP range
                if not self.allow_public_ip_discovery:
                    self.logger.warning(f"Skipping public network {network} - public IP discovery disabled")
                    return results
                
                self.logger.warning(f"⚠️  SCANNING PUBLIC NETWORK: {network}")
                self.logger.warning(f"⚠️  This will scan {len(hosts)} public IP addresses!")
                
                # Apply stricter limits for public ranges
                max_hosts = min(len(hosts), self.max_public_hosts_per_range)
                if len(hosts) > max_hosts:
                    self.logger.warning(f"Limiting scan to {max_hosts} hosts (from {len(hosts)} total)")
                    
            else:
                # Private network - use standard limits
                max_hosts = min(len(hosts), 254)
            
            hosts = hosts[:max_hosts]
            
            self.logger.info(f"Scanning {len(hosts)} hosts in {network} for ports {ports}")
            
            # Use reduced concurrency for public IP scans
            if not is_private and self.rate_limit_public_scans:
                max_workers = min(self.max_workers, 10)  # Limit public scan concurrency
                self.logger.info(f"Using reduced concurrency ({max_workers}) for public IP scan")
            else:
                max_workers = self.max_workers
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_host = {}
                
                for i, host in enumerate(hosts):
                    # Add delay between public IP scans if rate limiting is enabled
                    if not is_private and self.rate_limit_public_scans and i > 0:
                        time.sleep(self.public_scan_delay_ms / 1000.0)
                    
                    future = executor.submit(self.scan_host_ports, str(host), ports)
                    future_to_host[future] = str(host)
                
                for future in as_completed(future_to_host):
                    host = future_to_host[future]
                    try:
                        port_results = future.result()
                        # Only include hosts with at least one open port
                        if any(port_results.values()):
                            results[host] = port_results
                    except Exception as e:
                        self.logger.debug(f"Error scanning host {host}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error scanning network {network}: {e}")
            
        return results
    
    async def probe_voxa_service(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Probe a host to determine if it's running a Voxa service.
        
        Args:
            host: Target host IP
            port: Port to probe
            
        Returns:
            Service information if it's a Voxa service, None otherwise
        """
        try:
            # Try to connect to common Voxa endpoints
            endpoints_to_try = [
                "/status/health",
                "/info/program_stats", 
                "/status/",
                "/info/"
            ]
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for endpoint in endpoints_to_try:
                    try:
                        url = f"http://{host}:{port}{endpoint}"
                        response = await client.get(url)
                        
                        if response.status_code == 200:
                            try:
                                data = response.json()
                                # Check if response looks like a Voxa service
                                if self._is_voxa_response(data, endpoint):
                                    return {
                                        "host": host,
                                        "port": port,
                                        "endpoint": endpoint,
                                        "response": data,
                                        "service_type": self._determine_service_type(data, port)
                                    }
                            except json.JSONDecodeError:
                                # Not JSON, probably not a Voxa service
                                continue
                                
                    except Exception:
                        # Connection failed or other error, try next endpoint
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Error probing {host}:{port} - {e}")
            
        return None
    
    def _is_voxa_response(self, data: Dict[str, Any], endpoint: str) -> bool:
        """
        Determine if a response looks like it's from a Voxa service.
        
        Args:
            data: Response data
            endpoint: Endpoint that returned the data
            
        Returns:
            True if it looks like a Voxa service response
        """
        # Check for common Voxa response patterns
        voxa_indicators = [
            "VoxaCommunications",
            "voxa",
            "relay",
            "node",
            "program_stats",
            "healthy"
        ]
        
        # Convert data to string for searching
        data_str = json.dumps(data).lower()
        
        # Look for Voxa-specific indicators
        for indicator in voxa_indicators:
            if indicator.lower() in data_str:
                return True
                
        # Check for health endpoint patterns
        if endpoint == "/status/health" and "status" in data:
            return True
            
        # Check for program stats patterns
        if endpoint == "/info/program_stats" and "system" in data:
            return True
            
        return False
    
    def _determine_service_type(self, data: Dict[str, Any], port: int) -> str:
        """
        Determine the type of Voxa service based on response data and port.
        
        Args:
            data: Service response data
            port: Port number
            
        Returns:
            Service type string ("node", "relay", or "unknown")
        """
        data_str = json.dumps(data).lower()
        
        # Check for explicit type indicators
        if "relay" in data_str:
            return "relay"
        elif "node" in data_str:
            return "node"
        
        # Infer from port number
        if port == 9000:
            return "node"  # Nodes use port 9000
        
        # Default to unknown
        return "unknown"
    
    async def discover_voxa_services(self, networks: Optional[List[str]] = None, 
                                   ports: Optional[List[int]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover Voxa services across specified networks.
        
        Args:
            networks: List of networks to scan (CIDR format), uses config-based networks if None
            ports: List of ports to scan
            
        Returns:
            Dictionary categorizing discovered services by type
        """
        if networks is None:
            networks = self.get_networks_to_scan()  # Use config-based network selection
            
        if ports is None:
            ports = [9000, 8080, 8000, 3000, 5000]  # Common ports
            
        discovered = {
            "nodes": [],
            "relays": [], 
            "unknown": []
        }
        
        self.logger.info(f"Starting Voxa service discovery on networks: {networks}")
        
        # First, scan for open ports
        all_open_hosts = {}
        
        for network in networks:
            self.logger.info(f"Scanning network: {network}")
            open_hosts = self.scan_network_range(network, ports)
            all_open_hosts.update(open_hosts)
            
        self.logger.info(f"Found {len(all_open_hosts)} hosts with open ports")
        
        # Then, probe each host with open ports to identify Voxa services
        probe_tasks = []
        
        for host, port_results in all_open_hosts.items():
            for port, is_open in port_results.items():
                if is_open:
                    probe_tasks.append(self.probe_voxa_service(host, port))
                    
        if probe_tasks:
            self.logger.info(f"Probing {len(probe_tasks)} potential Voxa services")
            
            # Execute probes concurrently
            probe_results = await asyncio.gather(*probe_tasks, return_exceptions=True)
            
            for result in probe_results:
                if isinstance(result, dict) and result is not None:
                    service_type = result.get("service_type", "unknown")
                    
                    if service_type == "node":
                        discovered["nodes"].append(result)
                    elif service_type == "relay":
                        discovered["relays"].append(result)
                    else:
                        discovered["unknown"].append(result)
                        
        self.logger.info(f"Discovery complete: {len(discovered['nodes'])} nodes, "
                        f"{len(discovered['relays'])} relays, "
                        f"{len(discovered['unknown'])} unknown services")
        
        return discovered