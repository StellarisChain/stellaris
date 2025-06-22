"""
App Manager Integration

Integrates the decentralized app manager with the main VoxaCommunications node.
"""

from typing import Optional
from lib.VoxaCommunications_Router.apps.app_manager import AppManager, get_global_app_manager, set_global_app_manager
from lib.VoxaCommunications_Router.net.net_manager import get_global_net_manager
from util.logging import log
from util.jsonreader import read_json_from_namespace

logger = log()

def initialize_app_manager() -> AppManager:
    """Initialize the app manager and integrate it with the node"""
    try:
        logger.info("Initializing decentralized app manager...")
        
        # Check if apps feature is enabled
        settings = read_json_from_namespace("config.settings") or {}
        features = settings.get("features", {})
        
        if not features.get("enable-app-deployment", False):
            logger.info("App deployment feature is disabled")
            return None
        
        # Create app manager instance
        app_manager = AppManager()
        
        # Set as global instance
        set_global_app_manager(app_manager)
        
        logger.info("Decentralized app manager initialized successfully")
        return app_manager
        
    except Exception as e:
        logger.error(f"Failed to initialize app manager: {e}")
        raise

def get_app_manager() -> Optional[AppManager]:
    """Get the app manager instance if available"""
    try:
        return get_global_app_manager()
    except:
        return None

def is_app_deployment_enabled() -> bool:
    """Check if app deployment is enabled on this node"""
    settings = read_json_from_namespace("config.settings") or {}
    features = settings.get("features", {})
    return features.get("enable-app-deployment", False)

def get_node_app_capabilities() -> list[str]:
    """Get the app deployment capabilities of this node"""
    capabilities = []
    
    if is_app_deployment_enabled():
        capabilities.append("app-deployment")
        
        # Check for Docker availability
        try:
            import docker
            client = docker.from_env()
            client.ping()
            capabilities.append("docker-containers")
        except:
            pass
        
        # Check for other runtime capabilities
        app_config = read_json_from_namespace("config.apps") or {}
        if app_config.get("enable_source_builds", True):
            capabilities.append("source-builds")
        
        if app_config.get("enable_auto_scaling", True):
            capabilities.append("auto-scaling")
    
    return capabilities
