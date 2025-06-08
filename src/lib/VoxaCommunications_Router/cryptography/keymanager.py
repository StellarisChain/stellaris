import secrets
import rsa
import hashlib
import base64
import json
import uuid
import os
from typing import Optional
from cryptography.fernet import Fernet
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.VoxaCommunications_Router.util.ri_utils import fetch_ri
from lib.compression import JSONCompressor
from util.jsonreader import read_json_from_namespace
from util.filereader import file_to_str
from util.logging import log

class KeyManager:
    def __init__(self, mode: Optional[str] = "node"):
        self.mode = mode
        self.logger = log()
        self.rsa_keys: dict = {}
        self.cryptography_config = read_json_from_namespace("config.cryptography") or {}

    def load_rsa_keys(self) -> dict:
        storage_config = read_json_from_namespace("config.storage") or {}
        if not storage_config:
            self.logger.error("Storage configuration not found.")
            return {}
        data_dir = storage_config.get("data-dir", "data/")
        file_name = "nri" if self.mode == "node" else "rri"  # if node then nri if relay then rri
        ri_data: dict = fetch_ri(file_name, path="local").get("data")
        if not ri_data:
            self.logger.error(f"No RI data found for mode: {self.mode}")
            return {}
        self.rsa_keys["public_key"] = ri_data.get("public_key")
        self.rsa_keys["private_key"] = file_to_str(os.path.join(data_dir, "local", self.cryptography_config.get("private-key-file")))
        