"""
Scale App API Endpoint

Scales a deployed application to a new replica count.
"""

import json
import traceback
from typing import Dict, Any
from fastapi import HTTPException, Request as FastAPIRequest

from lib.VoxaCommunications_Router.apps.app_manager import get_global_app_manager
from util.logging import log

logger = log()

async def handler(request: FastAPIRequest) -> Dict[str, Any]:
    """Scale a deployed application"""
    try:
        # Parse request body
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Request body is required")
        
        try:
            request_data = json.loads(body.decode())
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        app_id = request_data.get("app_id")
        replicas = request_data.get("replicas")
        
        if not app_id:
            raise HTTPException(status_code=400, detail="app_id is required")
        if replicas is None:
            raise HTTPException(status_code=400, detail="replicas count is required")
        if not isinstance(replicas, int) or replicas < 0:
            raise HTTPException(status_code=400, detail="replicas must be a non-negative integer")
        
        # Get app manager
        app_manager = get_global_app_manager()
        
        try:
            # Scale the application
            result = await app_manager.scale_app(app_id, replicas)
            
            return {
                "success": True,
                "message": f"Scaled app {app_id} to {replicas} replicas",
                "result": result
            }
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to scale app: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to scale application")

# Disable automatic response model validation for custom response handling
ENABLE_RESPONSE_MODEL = False
