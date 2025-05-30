import secrets
import hashlib
import base64
from typing import Optional
from cryptography.fernet import Fernet
from util.jsonreader import read_json_from_namespace
from util.dirutils import create_dir_if_not_exists
from stores.globalconfig import get_global_config
    
class RelayIntegrityManager:
    def __init__(self, global_config: Optional[dict] = get_global_config()):
        self.global_config = global_config or {}
        self.cryptography_config = read_json_from_namespace("config.cryptography") or {}
        self.directories: dict = {
            "key_dir": f"{self.global_config["files"]["data-dir"]}{self.cryptography_config.get("key-dir")}",
            "fernet_dir": f"{self.global_config["files"]["data-dir"]}{self.cryptography_config.get("key-dir")}/fernet/",
            "asymmetric_dir": f"{self.global_config["files"]["data-dir"]}{self.cryptography_config.get("key-dir")}/asymmetric/",
        }
        self.setup_directories()

    
    def setup_directories(self):
        """
        Create necessary directories for relay integrity management.
        """
        create_dir_if_not_exists("/data/")
        for dir_path in self.directories.values():
            create_dir_if_not_exists(dir_path)