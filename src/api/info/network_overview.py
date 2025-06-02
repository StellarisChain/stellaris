"""
Network overview endpoint - Get comprehensive Voxa network information
"""

import asyncio
from typing import Dict, Any
from lib.VoxaCommunications_Router.discovery import DiscoveryManager
from util.logging import log

async def handler() -> Dict[str, Any]:
    """
    Get a comprehensive overview of the Voxa network including nodes, relays, and statistics.
    
    Returns:
        Dictionary with network overview and statistics
    """
    logger = log()
    logger.info("Network overview endpoint called")
    
    try:
        discovery_manager = DiscoveryManager()
        overview = await discovery_manager.get_network_overview()
        
        return {
            "success": True,
            "overview": overview
        }
        
    except Exception as e:
        logger.error(f"Error getting network overview: {e}")
        return {
            "success": False,
            "error": str(e),
            "overview": {}
        }