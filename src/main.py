import sys
import os
# Add the project root to Python path to enable absolute imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import dotenv
import logging
import uuid
import io
import time
from typing import Optional
from fastapi import FastAPI
from routes import InternalRouter
from colorama import init, Fore, Style
from kvprocessor import KVProcessor, KVStructLoader, load_env
from kytan import create_client, create_server, KytanError, KytanContextManager
from util.logging import log, set_log_config
from util.filereader import file_to_str
from util.setuputils import setup_directories
#from util.initnode import init_node
from stores.globalconfig import set_global_config
from stores.registrycontroller import set_global_registry_manager
from stores.kytancontroller import KytanController, set_kytan_controller, initialize_kytan_controller
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.ri.ri_manager import RIManager
from src import __version__

# Load environment variables and initialize colorama
dotenv.load_dotenv()
init(autoreset=True)


class Main:
    """Main application class for VoxaCommunications-NetNode.
    
    This class handles the initialization and configuration of all
    application components including FastAPI, Kytan networking,
    and registry management.
    """
    
    def __init__(self, logger: log) -> None:
        """Initialize the main application.
        
        Args:
            logger: Logger instance for application logging.
        """
        self.logger = logger
        self.first_run = True
        self.kytan_controller: Optional[KytanController] = None
        self.registry_manager: Optional[RegistryManager] = None
        self.logger.info("Main class initialized.")

        try:
            self._load_configuration()
            self._setup_fastapi()
            self._setup_kytan()
            self._setup_registry()
        except Exception as e:
            self.logger.error(f"Failed to initialize Main application: {e}")
            raise

    def _load_configuration(self) -> None:
        """Load and validate application configuration."""
        self.logger.info("Loading application configuration...")
        
        # Load and validate configuration
        struct_loader_url = os.getenv(
            "STRUCT_LOADER_URL",
            "https://raw.githubusercontent.com/Voxa-Communications/VoxaCommunications-Structures/refs/heads/main/struct/config.json"
        )
        
        self.struct_loader = KVStructLoader(struct_loader_url)
        self.env_kv_processor: KVProcessor = self.struct_loader.from_namespace(
            "voxa.config.node_config"
        )
        self.env_config = load_env(self.env_kv_processor.return_names())
        self.logger.info(
            f"Loading environment variables: {list(self.env_config.keys())}"
        )
        
        self.validated_config = self.env_kv_processor.process_config(
            self.env_config
        )
        
        # Setup directories and global configuration
        setup_directories()
        self.logger.info(f"Validated configuration: {self.validated_config}")
        set_global_config(self.validated_config)

    def _setup_fastapi(self) -> None:
        """Initialize FastAPI application and routes."""
        self.logger.info("Setting up FastAPI application...")
        
        self.app = FastAPI(
            title="VoxaCommunications-NetNode", 
            summary=file_to_str("summary.txt"),
            description=file_to_str("README.md"), 
            version=__version__,
            license_info={
                "name": "Attribution-NonCommercial-ShareAlike 4.0 International"
            }
        )
        
        self.internal_router = InternalRouter()
        self.internal_router.add_to_app(self.app)
        self.logger.info("FastAPI application configured successfully")

    def _setup_kytan(self) -> None:
        """Initialize Kytan networking components."""
        self.logger.info("Setting up Kytan networking...")
        
        try:
            # Initialize the global Kytan controller
            self.kytan_controller = initialize_kytan_controller()
            
            # Create and configure the server
            kytan_server = create_server()
            self.kytan_controller.server = kytan_server
            
            self.logger.info("Kytan server created and configured successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to setup Kytan: {e}")
            raise RuntimeError(f"Kytan initialization failed: {e}")

    def _setup_registry(self) -> None:
        """Initialize registry manager for production environment."""
        if os.getenv("env") != "production":
            self.logger.info("Skipping registry setup (not in production environment)")
            return
            
        self.logger.info("Setting up registry manager for production...")
        
        try:
            email = self.validated_config.get('email')
            password = self.validated_config.get('password')
            code = self.validated_config.get('code')
            
            if not all([email, password]):
                raise ValueError("Email and password are required for registry authentication")
            
            self.logger.info(f"Logging in to registry with email: {email}")
            
            self.registry_manager = RegistryManager(client_type="node")
            self.registry_manager.set_credentials(
                email=email,
                password=password,
                code=code
            )
            
            login_success = self.registry_manager.login()
            if not login_success:
                raise RuntimeError("Registry login failed - invalid credentials or connection error")
            
            self.logger.info("Successfully logged in to the registry")
            set_global_registry_manager(self.registry_manager)
            
            self.ri_manager: RIManager = RIManager(type="node")
            self.ri_manager.login()

            if not self.ri_manager.initialized:
                self.logger.info("RI not initialized, initializing now...")
                self.ri_manager.initialize()
                self.logger.info("RI initialization completed")
            
        except Exception as e:
            self.logger.error(f"Failed to setup registry: {e}")
            raise

    def start_kytan_server(self) -> None:
        """Start the Kytan server if configured."""
        if not self.kytan_controller:
            raise RuntimeError("Kytan controller not initialized")
            
        try:
            self.logger.info("Starting Kytan server...")
            self.kytan_controller.serve()
        except Exception as e:
            self.logger.error(f"Failed to start Kytan server: {e}")
            raise

    def shutdown(self) -> None:
        """Shutdown the application and cleanup resources."""
        self.logger.info("Shutting down application...")
        
        if self.kytan_controller:
            try:
                self.kytan_controller.shutdown()
                self.logger.info("Kytan controller shutdown completed")
            except Exception as e:
                self.logger.error(f"Error during Kytan shutdown: {e}")
        
        self.logger.info("Application shutdown completed")


# Configure logging for module-level initialization
log_id = str(uuid.uuid4())
set_log_config(log_id)
logger_instance = log()

# Initialize main application class and expose the app
main_app = Main(logger_instance)
app = main_app.app  # Expose the FastAPI app for uvicorn


if __name__ == "__main__":
    print(Fore.GREEN + "Initializing application...")

    try:
        # App is already initialized above
        logger_instance.info("Application initialized successfully")

    except Exception as error:
        logger_instance.error(
            f"{Fore.RED}Error in Main: {error}{Style.RESET_ALL}")
        raise error

    print(Fore.RED + "Application terminated.")
