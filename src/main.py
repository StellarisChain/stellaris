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
from util.logging import log, set_log_config
from util.filereader import file_to_str
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
            "https://github.com/Voxa-Communications/VoxaCommunicaitons-Structures/raw/refs/heads/main/struct/config.json"
        )
        self.struct_loader = KVStructLoader(struct_loader_url)
        self.env_kv_processor: KVProcessor = self.struct_loader.from_namespace(
            "voxa.registry.config"
        )
        self.env_config = LoadEnv(self.env_kv_processor.return_names())
        self.logger.info(
            f"Loading environment variables: {list(self.env_config.keys())}"
        )
        self.validated_config = self.env_kv_processor.process_config(
            self.env_config
        )
        self.logger.info(f"Validated configuration: {self.validated_config}")
        self.app = FastAPI(
            title="VoxaCommunications-NetNode", 
            summary="https://github.com/Voxa-Communications/",
            description=file_to_str("README.md"), 
            version=__version__,
            license_info={
                "name": "Attribution-NonCommercial-ShareAlike 4.0 International"
            }
        )
        self.internal_router = InternalRouter()
        self.internal_router.add_to_app(self.app)


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
