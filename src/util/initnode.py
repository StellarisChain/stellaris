import json
import os
import uuid
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.registry.client import RegistryClient
from lib.compression import JSONCompressor
from stores.registrycontroller import get_global_registry_manager, set_global_registry_manager
from util.logging import log
from util.jsonreader import read_json_from_namespace
from typing import Optional

def init_node():
    logger = log()
    logger.info("Initializing Voxa Node...")

    try:
        storage_config: dict = read_json_from_namespace("config.storage")
        if not storage_config:
            logger.error("Storage configuration not found. Please ensure 'config.storage' is set up correctly.")
            return
        data_dir = storage_config.get("data-dir", "data/")
        nri_subdir = dict(storage_config.get("sub-dirs", {})).get("local", "local/")
        nri_dir = os.path.join(data_dir, nri_subdir)

        if not os.path.exists(nri_dir):
            logger.error(f"NRI directory does not exist: {nri_dir}. Please check your storage configuration.")
            return
        
        # check if nri.bin exists
        nri_file_path = os.path.join(nri_dir, "nri.bin")
        if os.path.exists(nri_file_path):
            logger.info(f"NRI file found at {nri_file_path}. Initializing registry...")
            return
        
        # session would only exist if we have logged in, if not, login
        registry_manager: RegistryManager = get_global_registry_manager()
        if registry_manager.session_token == "":
            registry_manager.login()

        # register the node to the network
        node_settings: dict = read_json_from_namespace("config.settings")
        registry_manager.client.register_node(
            callsign = f"{node_settings.get("node-network-level", "mainnet")}-{str(uuid.uuid4())}",
            node_type = "node" # idk why this even exists as we know this is a node
        )

    except Exception as e:
        logger.error(f"Failed to read storage configuration: {e}")
        return