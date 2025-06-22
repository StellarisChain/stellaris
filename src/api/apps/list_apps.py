"""
List Apps API Endpoint

Lists all deployed applications on the network.
"""

import traceback
from typing import Dict, Any, List
from fastapi import HTTPException, Request as FastAPIRequest

from lib.VoxaCommunications_Router.apps.app_manager import get_global_app_manager
from util.logging import log

logger = log()

async def handler(request: FastAPIRequest) -> Dict[str, Any]:
    """List all deployed applications"""
    try:
        # Get app manager
        app_manager = get_global_app_manager()
        
        # Get list of apps
        apps = app_manager.list_apps()
        
        return {
            "success": True,
            "apps": apps,
            "total": len(apps)
        }
        
    except Exception as e:
        logger.error(f"Failed to list apps: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to list applications")

# Disable automatic response model validation for custom response handling
ENABLE_RESPONSE_MODEL = False
