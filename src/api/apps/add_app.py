"""
App Deployment API Endpoint

Handles deployment requests for decentralized applications.
"""

import json
import traceback
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request as FastAPIRequest
from pydantic import BaseModel, Field
from schema.apps.deploy_app_request import DeployAppRequest
from schema.apps.app_deployment_response import AppDeploymentResponse

from lib.VoxaCommunications_Router.apps.app_manager import (
    get_global_app_manager, AppSpec, AppManager
)
from util.logging import log

logger = log()

async def handler(request: FastAPIRequest) -> AppDeploymentResponse:
    """Deploy an application to the decentralized network"""
    try:
        # Parse request body
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Request body is required")
        
        try:
            request_data = json.loads(body.decode())
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        # Validate request
        try:
            deploy_request = DeployAppRequest(**request_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request format: {e}")
        
        # Validate deployment type
        if not deploy_request.image and not deploy_request.source_code_hash:
            raise HTTPException(
                status_code=400, 
                detail="Either 'image' or 'source_code_hash' must be provided"
            )
        
        # Get app manager
        app_manager: AppManager = get_global_app_manager()
        
        # Generate app ID
        import uuid
        app_id = str(uuid.uuid4())
        
        # Create app specification
        app_spec = AppSpec(
            app_id=app_id,
            name=deploy_request.name,
            version=deploy_request.version,
            image=deploy_request.image,
            source_code_hash=deploy_request.source_code_hash,
            build_config=deploy_request.build_config,
            runtime_config=deploy_request.runtime_config,
            resource_requirements=deploy_request.resource_requirements,
            network_config=deploy_request.network_config,
            replicas=deploy_request.replicas
        )
        
        logger.info(f"Deploying app {deploy_request.name} with {deploy_request.replicas} replicas")
        
        # Deploy the application
        deployment_result = await app_manager.deploy_app(
            app_spec, 
            target_nodes=deploy_request.target_nodes
        )
        
        # Prepare response
        success = deployment_result["successful"] > 0
        message = f"Deployed {deployment_result['successful']}/{deployment_result['total']} instances successfully"
        
        if deployment_result["failed"] > 0:
            message += f" ({deployment_result['failed']} failed)"
        
        return AppDeploymentResponse(
            success=success,
            app_id=deployment_result["app_id"],
            deployment_id=deployment_result["deployment_id"],
            message=message,
            instances=deployment_result["instances"],
            successful=deployment_result["successful"],
            failed=deployment_result["failed"],
            total=deployment_result["total"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"App deployment failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")

# Disable automatic response model validation for custom response handling
ENABLE_RESPONSE_MODEL = False
