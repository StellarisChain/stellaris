import dotenv
import os
import logging
import uuid
import io
import time
from colorama import init, Fore, Style
from kvprocessor import KVProcessor, KVStructLoader, LoadEnv
from util.logging import log, set_log_config

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
        self.env_kv_processor: KVProcessor = self.struct_loader.from_namespace("voxa.registry.config")
        self.env_config = LoadEnv(self.env_kv_processor.return_names())
        self.logger.info(f"Loading environment variables: {list(self.env_config.keys())}")
        self.validated_config = self.env_kv_processor.process_config(self.env_config)
        self.logger.info(f"Validated configuration: {self.validated_config}")


if __name__ == "__main__":
    print(Fore.GREEN + "Initializing application...")

    # Configure logging
    log_id = str(uuid.uuid4())
    set_log_config(log_id)
    logger_instance = log()

    try:
        # Initialize main application class
        main_app = Main(logger_instance)

    except Exception as error:
        logger_instance.error(f"{Fore.RED}Error in Main: {error}{Style.RESET_ALL}")
        raise error

    print(Fore.RED + "Application terminated.")