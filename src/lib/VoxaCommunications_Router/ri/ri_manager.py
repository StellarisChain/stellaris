import json
import os
import uuid
from typing import Optional
from datetime import datetime
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.registry.client import RegistryClient
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.VoxaCommunications_Router.cryptography.keymanager import KeyManager
from lib.VoxaCommunications_Router.util.ri_utils import fetch_ri, save_ri
from lib.compression import JSONCompressor
from stores.registrycontroller import get_global_registry_manager, set_global_registry_manager
from schema.RRISchema import RRISchema
from schema.NRISchema import NRISchema
from util.jsonreader import read_json_from_namespace
from util.logging import log
from src import __version__

class RIManager:
    def __init__(self, type: Optional[str] = "node"):
        self.type = type
        self.logger = log()
        self._initialized: bool = False
        self.storage_config: dict = read_json_from_namespace("config.storage") or {}
        self.settings = read_json_from_namespace("config.settings") or {}
        self.features: dict = self.settings.get("features", {})
        self.p2p_settings = read_json_from_namespace("config.p2p") or {}
        self.data_dir: str = self.storage_config.get("data-dir", "data/")
        self.sub_dirs: dict = dict(self.storage_config.get("sub-dirs", {}))
        self.local_dir: str = os.path.join(self.data_dir, self.sub_dirs.get("local", "local/"))
        self.registry_manager: RegistryManager = get_global_registry_manager()
        self.session_token: str = self.registry_manager.session_token
        self.check_initialization()

    def update_registry_manager(self, registry_manager: Optional[RegistryManager] = None) -> None:
        """Update the registry manager instance."""
        if registry_manager:
            self.registry_manager = registry_manager
        else:
            self.registry_manager = get_global_registry_manager()
        self.session_token = self.registry_manager.session_token

    def login(self) -> None:
        """Login to the registry if not already logged in."""
        if self.session_token == "":
            self.registry_manager.login()
            self.session_token = self.registry_manager.session_token

    def check_initialization(self) -> bool:
        """Check if RI is initialized by verifying the existence of the RI file."""
        file_name = "nri.bin" if self.type == "node" else "rri.bin"
        ri_file_path = os.path.join(self.local_dir, file_name)
        self._initialized = os.path.exists(ri_file_path)
        return self._initialized

    @property
    def initialized(self) -> bool:
        """Check if RI is initialized."""
        return self._initialized
    
    @initialized.setter
    def initialized(self, value: bool) -> None:
        self._initialized = value

    def setup(self) -> None:
        """Does the same thing as initialize, just a different name."""
        # Initialize is close to initialized which is confusing
        self.initialize()

    def initialize(self) -> None:
        """Initialize the RI based on its type (node or relay)."""
        if self.type == "node":
            self.initialize_node()
        elif self.type == "relay":
            self.initialize_relay()
        else:
            raise ValueError(f"Unknown RI type: {self.type}")
        self._initialized = True
    
    def _features_to_list(self) -> list[str]:
        features_list: list[str] = []
        for feature, enabled in self.features.items():
            if enabled:
                feature: str = feature.replace("enable-", "")
                features_list.append(feature)
        return features_list

    def initialize_node(self):
        self.registry_manager.client.register_node(
            callsign=f"{self.settings.get('node-network-level', 'mainnet')}-{str(uuid.uuid4())}",
            node_type=self.settings.get('node-network-level', 'mainnet')  # idk why this even exists as we know this is a node
        )
        node_id = self.registry_manager.client.ids.get("node_id")
        key_manager = KeyManager(mode="node")
        rsa_keys = key_manager.generate_hybrid_keys().get("rsa")
        rsa_key_generator: RSAKeyGenerator = key_manager.hybrid_key_generator.rsa_generator
        capabilities: list[str] = self._features_to_list()
        nri_data: dict = NRISchema(
            node_id=node_id,
            node_ip=self.registry_manager.client.node_ip,
            node_port=self.p2p_settings.get("port", 9000),  # 9000 should be standard for nodes
            node_type=self.settings.get('node-network-level', 'mainnet'),
            capabilities=capabilities,
            metadata={"location": "datacenter-1"},
            public_key=rsa_keys["public_key"],
            public_key_hash=str(rsa_key_generator.public_key_hash)
        ).dict()
        nri_data["created_at"] = datetime.utcnow().isoformat()
        nri_data["last_updated"] = datetime.utcnow().isoformat()
        nri_data["version"] = str(__version__)
        json_data = json.dumps(nri_data, indent=2, ensure_ascii=False)
        save_ri("nri", json_data, path="local")
        key_manager.save_hybrid_keys() # Have to do this after the file is written, since it uses the file to save the keys, eventhough they are alreadt saved
        self.logger.info(f"Successfully initialized node with NRI data")

    def initialize_relay(self):
        pass