from typing import Optional, Dict, List
import os
import importlib
import inspect
import traceback
from fastapi import WebSocket, APIRouter, FastAPI, Response
#from lib.dynamiclibrary.loader import DynamicLibraryLoader
#from lib.dynamiclibrary.structs import DynamicLibrary
from lib.dynamiclibrary import DynamicLibrary, DynamicLibraryLoader
from util.jsonreader import read_json_from_namespace
from util.logging import log

class InternalRouter:
    def __init__(self, app: Optional[FastAPI] = None):
        self.router = APIRouter()
        self.app = app
        self.sub_routers: Dict[str, APIRouter] = {}
        self.dev_config: dict = read_json_from_namespace("config.dev") or {}
        self.logger = log()
        
    def include_router(self, new_router: APIRouter):
        self.router.include_router(new_router)

    def add_to_app(self, app: Optional[FastAPI] = None):
        # Load all API modules dynamically
        self._load_api_modules()
        
        # Include all sub-routers in the main router
        for prefix, sub_router in self.sub_routers.items():
            self.router.include_router(sub_router, prefix=f"/{prefix}")
            
        # Add the main router to the app
        if self.app:
            self.app.include_router(self.router)
        elif app:
            app.include_router(self.router)
            
    def _load_api_modules(self):
        """Dynamically load all API modules from the api directory"""
        api_path = os.path.join(os.path.dirname(__file__), "api")
        self.logger.info(f"Loading API modules from {api_path}")
        
        # Check if api directory exists
        if not os.path.exists(api_path):
            self.logger.warning(f"API path {api_path} does not exist")
            return
            
        # Find all subdirectories in the api directory
        for dir_name in os.listdir(api_path):
            dir_path = os.path.join(api_path, dir_name)
            
            # Skip if not a directory or starts with __
            if not os.path.isdir(dir_path) or dir_name.startswith('__'):
                continue
                
            self.logger.info(f"Found API module directory: {dir_name}")
            
            # Create a new router for this API module
            sub_router = APIRouter()
            self.sub_routers[dir_name] = sub_router
            
            # Find all Python files in this directory
            for file_name in os.listdir(dir_path):
                if file_name.endswith('.py') and not file_name.startswith('__'):
                    module_name = file_name[:-3]  # Remove .py extension
                    full_module_path = f"api.{dir_name}.{module_name}"
                    
                    self.logger.info(f"Loading API handler from {full_module_path}")
                    
                    try:
                        # Import the module
                        module = importlib.import_module(full_module_path)
                        
                        # Check if the module has a handler function
                        if hasattr(module, 'handler'):
                            # Register the handler function with the router
                            handler_func = getattr(module, 'handler')
                            endpoint_path = f"/{module_name}/"
                            
                            # Check if response model should be disabled
                            response_model = True
                            if hasattr(module, 'ENABLE_RESPONSE_MODEL') and getattr(module, 'ENABLE_RESPONSE_MODEL') is False:
                                response_model = False
                                self.logger.info(f"Response model disabled for {full_module_path}")

                            # Disalow the test directory if we are not in debug mode
                            if dir_name == "test" and self.dev_config.get("debug", False):
                                self.logger.info(f"Skipping test directory {dir_name} in non-debug mode")
                                continue
                            
                            # Determine HTTP method based on module name
                            if module_name.startswith('add_'):
                                # POST method for add operations
                                sub_router.add_api_route(endpoint_path, handler_func, methods=["POST"])
                                self.logger.info(f"Registered POST endpoint {endpoint_path} for {full_module_path}")
                            elif module_name.startswith('fetch_') or module_name.startswith('get_'):
                                # GET method for fetch/get operations  
                                sub_router.add_api_route(endpoint_path, handler_func, methods=["GET"])
                                self.logger.info(f"Registered GET endpoint {endpoint_path} for {full_module_path}")
                            else:
                                # Default to GET for other endpoints
                                if response_model:
                                    sub_router.add_api_route(endpoint_path, handler_func, methods=["GET"])
                                else:
                                    sub_router.add_api_route(endpoint_path, handler_func, methods=["GET"], response_model=None)
                                self.logger.info(f"Registered GET endpoint {endpoint_path} for {full_module_path}")
                        else:
                            self.logger.warning(f"No handler function found in {full_module_path}")
                            
                    except Exception as e:
                        self.logger.error(f"Error loading module {full_module_path}: {str(e)}")
                        traceback.print_exc()