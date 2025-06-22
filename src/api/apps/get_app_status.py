"""
Get App Status API Endpoint

Retrieves status information for deployed applications.
"""

import json
import traceback
from typing import Dict, Any
from fastapi import HTTPException, Request as FastAPIRequest

from lib.VoxaCommunications_Router.apps.app_manager import get_global_app_manager
from util.logging import log

logger = log()

async def handler(request: FastAPIRequest) -> Dict[str, Any]:
    """Get status of a deployed application"""
    try:
        # Get app_id from query parameters
        app_id = request.query_params.get("app_id")
        
        if not app_id:
            raise HTTPException(status_code=400, detail="app_id parameter is required")
        
        # Get app manager
        app_manager = get_global_app_manager()
        
        try:
            # Get app status
            status = app_manager.get_app_status(app_id)
            
            return {
                "success": True,
                "app_status": status
            }
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get app status: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get app status")

# Disable automatic response model validation for custom response handling
ENABLE_RESPONSE_MODEL = False
