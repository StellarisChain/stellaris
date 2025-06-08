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
from fastapi import FastAPI
from routes import InternalRouter
from colorama import init, Fore, Style
from kvprocessor import KVProcessor, KVStructLoader, LoadEnv
from kytan import create_client, create_server, KytanError, KytanContextManager
from util.logging import log, set_log_config
from util.filereader import file_to_str
from util.setuputils import setup_directories
from util.initnode import init_node
from stores.globalconfig import set_global_config
from stores.registrycontroller import set_global_registry_manager
from stores.kytancontroller import KytanController, set_kytan_controller
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from src import __version__

# Load environment variables and initialize colorama
dotenv.load_dotenv()
init(autoreset=True)


class Main:
    def __init__(self, logger: log):
        self.logger = logger
        self.first_run = True
        self.logger.info("Main class initialized.")

        # Load and validate configuration
        struct_loader_url = os.getenv(
            "STRUCT_LOADER_URL",
            "https://raw.githubusercontent.com/Voxa-Communications/VoxaCommunications-Structures/refs/heads/main/struct/config.json"
        )
        self.struct_loader = KVStructLoader(struct_loader_url)
        self.env_kv_processor: KVProcessor = self.struct_loader.from_namespace(
            "voxa.config.node_config"
        )
        self.env_config = LoadEnv(self.env_kv_processor.return_names())
        self.logger.info(
            f"Loading environment variables: {list(self.env_config.keys())}"
        )
        self.validated_config = self.env_kv_processor.process_config(
            self.env_config
        )
        setup_directories()
        self.logger.info(f"Validated configuration: {self.validated_config}")
        set_global_config(self.validated_config)
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
        self.logger.info("Setting up Kytan")
        self.kytan_controller: KytanController = KytanController()
        self.kytan_controller.set_server(create_server())
        set_kytan_controller(self.kytan_controller)
        self.logger.info("Kytan server created")
        if os.getenv("env") == "production":
            self.logger.info(f"Logging in to registry, with email: {self.validated_config.get('email')}")
            self.registry_manager: RegistryManager = RegistryManager(client_type="node")
            self.registry_manager.set_credentials(
                email=self.validated_config.get("email"),
                password=self.validated_config.get("password"),
                code=self.validated_config.get("code")
            )
            login_success = self.registry_manager.login()
            if not login_success:
                self.logger.error(
                    "Failed to log in to the registry. Please check your credentials."
                )
                raise Exception("Registry login failed")
            else:
                self.logger.info("Successfully logged in to the registry.")
            set_global_registry_manager(self.registry_manager)
            init_node()


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
        pass

    except Exception as error:
        logger_instance.error(
            f"{Fore.RED}Error in Main: {error}{Style.RESET_ALL}")
        raise error

    print(Fore.RED + "Application terminated.")
