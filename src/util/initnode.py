# Todo, this should be moved into a class and in the VoxaCommunications_Router package
# Your service will not be forgotten.
import json
import os
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator, ValidationError
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.registry.client import RegistryClient
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.compression import JSONCompressor
from stores.registrycontroller import get_global_registry_manager, set_global_registry_manager
from util.logging import log
from util.jsonreader import read_json_from_namespace
from schema.NRISchema import NRISchema
from src import __version__

def init_node():
    logger = log()
    logger.info("Initializing Voxa Node...")

    raise DeprecationWarning("Use RIManager from lib.VoxaCommunications_Router.ri.ri_manager instead of this function.")

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
        p2p_settings: dict = read_json_from_namespace("config.p2p")
        registry_manager.client.register_node(
            callsign = f"{node_settings.get("node-network-level", "mainnet")}-{str(uuid.uuid4())}",
            node_type = "node" # idk why this even exists as we know this is a node
        )
        node_id = registry_manager.client.ids.get("node_id")

        # Generate RSA keys for the node
        rsa_generator = RSAKeyGenerator()
        rsa_generator.generate_keys()
        rsa_keys = rsa_generator.get_keys()

        # Create local NRI data
        nri_data: dict = NRISchema(
            node_id=node_id,
            node_ip=registry_manager.client.node_ip,
            node_port=p2p_settings.get("port", 9000), # 9000 should be standard for nodes
            node_type="node",
            capabilities=["routing", "forwarding"],
            metadata={"location": "datacenter-1"},
            public_key=rsa_keys["public_key"],
            public_key_hash=rsa_keys["public_key_hash"]
        ).dict()
        nri_data["created_at"] = datetime.utcnow().isoformat()
        nri_data["last_updated"] = datetime.utcnow().isoformat()
        nri_data["version"] = str(__version__)
        json_data = json.dumps(nri_data, indent=2, ensure_ascii=False)

        # Initialize the compressor
        compressor = JSONCompressor()
        compressed_data = compressor.compress(json_data)

        # Save the NRI data to a file
        file_path = os.path.join(nri_dir, "nri.bin")
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        logger.info(f"Successfully initialized node with NRI data at {file_path}")

    except Exception as e:
        logger.error(f"Failed to read storage configuration: {e}")
        return