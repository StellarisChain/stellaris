# Todo: Remove this
import secrets
import rsa
import hashlib
import base64
import json
import uuid
from typing import Optional
from cryptography.fernet import Fernet
from util.jsonreader import read_json_from_namespace
from util.dirutils import create_dir_if_not_exists
from stores.globalconfig import get_global_config
    
class RelayIntegrityManager:
    def __init__(self, request_ip: Optional[str] = None,global_config: Optional[dict] = get_global_config()):
        self.global_config = global_config or {}
        self.cryptography_config = read_json_from_namespace("config.cryptography") or {}
        self.request_ip = request_ip
        self.directories: dict = {
            "key_dir": f"{self.global_config["files"]["data-dir"]}{self.cryptography_config.get("key-dir")}",
        }
        self.setup_directories()

    
    def setup_directories(self):
        """
        Create necessary directories for relay integrity management.
        """
        create_dir_if_not_exists("/data/")
        for dir_path in self.directories.values():
            create_dir_if_not_exists(dir_path)

    def save_json_keys(self, filename: str, data: dict):
        """
        Save a dictionary as a JSON file.

        Args:
            filename (str): The name of the file to save.
            data (dict): The data to save.
        """
        filename = f"{self.directories['key_dir']}/{filename}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)

    def generate_keys(self, request_ip: Optional[str] = None) -> dict:
        """
        Generate a new set of keys for the given request IP.
        
        Args:
            request_ip (str): The IP address of the requestor.
        
        Returns:
            dict: A dictionary containing the generated keys.
        """
        if request_ip is None:
            request_ip = self.request_ip

        fernet_key = Fernet.generate_key()
        fernet = Fernet(fernet_key)
        fernet_key_hash = hashlib.sha256(fernet_key).hexdigest()
        fernet_key_b64 = base64.urlsafe_b64encode(fernet_key).decode('utf-8')

        rsa_public, rsa_private = rsa.newkeys(2048)
        
        id = str(uuid.uuid4())

        data = {
            "request_ip": request_ip,
            "id": id,
            "fernet": {
                "key": fernet_key_b64,
                "key_hash": fernet_key_hash,
                "fernet_instance": fernet
            },
            "rsa": {
                "public_key": rsa_public.save_pkcs1().decode('utf-8'),
                "private_key": rsa_private.save_pkcs1().decode('utf-8')
            }
        }

        self.save_json_keys(id, data)
        return data