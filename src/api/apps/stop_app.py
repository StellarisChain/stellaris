"""
Stop App API Endpoint

Stops a deployed application and all its instances.
"""

import json
import traceback
from typing import Dict, Any
from fastapi import HTTPException, Request as FastAPIRequest

from lib.VoxaCommunications_Router.apps.app_manager import get_global_app_manager
from util.logging import log

logger = log()

async def handler(request: FastAPIRequest) -> Dict[str, Any]:
    """Stop a deployed application"""
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
        if not app_id:
            raise HTTPException(status_code=400, detail="app_id is required")
        
        # Get app manager
        app_manager = get_global_app_manager()
        
        try:
            # Stop the application
            result = await app_manager.stop_app(app_id)
            
            message = f"Stopped {result['stopped']}/{result['total']} instances"
            if result['failed'] > 0:
                message += f" ({result['failed']} failed to stop)"
            
            return {
                "success": True,
                "message": message,
                "result": result
            }
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop app: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to stop application")

# Disable automatic response model validation for custom response handling
ENABLE_RESPONSE_MODEL = False
