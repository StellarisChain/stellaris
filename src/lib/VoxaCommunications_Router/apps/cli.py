"""
App CLI Commands

Command-line interface for managing decentralized app deployments.
"""

import json
import asyncio
import uuid
from typing import Dict, Any, Optional

from lib.VoxaCommunications_Router.apps.app_manager import AppSpec, get_global_app_manager
from util.logging import log

logger = log()

def create_example_app_spec() -> AppSpec:
    """Create an example application specification"""
    return AppSpec(
        app_id=str(uuid.uuid4()),
        name="hello-world",
        version="1.0.0",
        image="nginx:alpine",  # Simple web server
        runtime_config={
            "environment": {
                "ENV": "production"
            }
        },
        resource_requirements={
            "memory": "256m",
            "cpu": "0.5",
            "storage": "1G"
        },
        network_config={
            "ports": {
                "80/tcp": {"HostPort": "8080"}
            }
        },
        replicas=2
    )

async def deploy_example_app():
    """Deploy an example application"""
    try:
        logger.info("Deploying example application...")
        
        app_manager = get_global_app_manager()
        if not app_manager:
            logger.error("App manager not initialized")
            return
        
        # Create example app spec
        app_spec = create_example_app_spec()
        
        # Deploy the app
        result = await app_manager.deploy_app(app_spec)
        
        logger.info(f"Deployment result: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to deploy example app: {e}")
        raise

async def list_deployed_apps():
    """List all deployed applications"""
    try:
        app_manager = get_global_app_manager()
        if not app_manager:
            logger.error("App manager not initialized")
            return
        
        apps = app_manager.list_apps()
        
        logger.info("Deployed applications:")
        for app in apps:
            logger.info(f"  - {app['name']} ({app['app_id'][:8]}...): {app['instances']} instances")
        
        return apps
        
    except Exception as e:
        logger.error(f"Failed to list apps: {e}")
        raise

async def get_app_status_cli(app_id: str):
    """Get status of a specific application"""
    try:
        app_manager = get_global_app_manager()
        if not app_manager:
            logger.error("App manager not initialized")
            return
        
        status = app_manager.get_app_status(app_id)
        
        logger.info(f"App status: {json.dumps(status, indent=2)}")
        return status
        
    except Exception as e:
        logger.error(f"Failed to get app status: {e}")
        raise

async def stop_app_cli(app_id: str):
    """Stop an application"""
    try:
        app_manager = get_global_app_manager()
        if not app_manager:
            logger.error("App manager not initialized")
            return
        
        result = await app_manager.stop_app(app_id)
        
        logger.info(f"Stop result: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to stop app: {e}")
        raise

def run_app_command(command: str, app_id: Optional[str] = None):
    """Run an app management command"""
    try:
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if command == "deploy":
            return loop.run_until_complete(deploy_example_app())
        elif command == "list":
            return loop.run_until_complete(list_deployed_apps())
        elif command == "status":
            if not app_id:
                logger.error("app_id required for status command")
                return
            return loop.run_until_complete(get_app_status_cli(app_id))
        elif command == "stop":
            if not app_id:
                logger.error("app_id required for stop command")
                return
            return loop.run_until_complete(stop_app_cli(app_id))
        else:
            logger.error(f"Unknown command: {command}")
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        raise
