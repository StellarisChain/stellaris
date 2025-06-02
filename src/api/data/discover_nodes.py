"""
Discover nodes endpoint - Find all Voxa nodes on the network
"""

import asyncio
from typing import Dict, Any, List, Optional
from lib.VoxaCommunications_Router.discovery import DiscoveryManager
from util.logging import log

async def handler(networks: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Discover Voxa nodes on the network.
    
    Args:
        networks: Optional list of networks to scan (CIDR format)
        force_refresh: Force new discovery ignoring cache
        
    Returns:
        Dictionary with discovered nodes and metadata
    """
    logger = log()
    logger.info("Node discovery endpoint called")
    
    try:
        discovery_manager = DiscoveryManager()
        nodes = await discovery_manager.discover_nodes_only(
            networks=networks,
            force_refresh=force_refresh
        )
        
        return {
            "success": True,
            "count": len(nodes),
            "nodes": nodes,
            "discovery_time": discovery_manager._discovery_results.get("last_updated"),
            "cache_info": discovery_manager.get_cache_status()
        }
        
    except Exception as e:
        logger.error(f"Error discovering nodes: {e}")
        return {
            "success": False,
            "error": str(e),
            "count": 0,
            "nodes": []
        }