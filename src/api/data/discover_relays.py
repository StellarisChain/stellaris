"""
Discover relays endpoint - Find all Voxa relays on the network
"""

import asyncio
from typing import Dict, Any, List, Optional
from lib.VoxaCommunications_Router.discovery import DiscoveryManager
from util.logging import log

async def handler(networks: Optional[List[str]] = None, force_refresh: bool = False, 
                 relay_ports: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Discover Voxa relays on the network.
    
    Args:
        networks: Optional list of networks to scan (CIDR format)
        force_refresh: Force new discovery ignoring cache
        relay_ports: Optional list of ports to scan for relays
        
    Returns:
        Dictionary with discovered relays and metadata
    """
    logger = log()
    logger.info("Relay discovery endpoint called")
    
    try:
        discovery_manager = DiscoveryManager()
        
        # Configure relay ports if provided
        if relay_ports:
            discovery_manager.configure_relay_ports(relay_ports)
        
        relays = await discovery_manager.discover_relays_only(
            networks=networks,
            force_refresh=force_refresh
        )
        
        return {
            "success": True,
            "count": len(relays),
            "relays": relays,
            "discovery_time": discovery_manager._discovery_results.get("last_updated"),
            "cache_info": discovery_manager.get_cache_status(),
            "relay_ports": discovery_manager.relay_discovery.get_relay_ports()
        }
        
    except Exception as e:
        logger.error(f"Error discovering relays: {e}")
        return {
            "success": False,
            "error": str(e),
            "count": 0,
            "relays": []
        }