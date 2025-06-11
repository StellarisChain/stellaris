import secrets
import rsa
import hashlib
import base64
import json
import uuid
import os
import traceback
from typing import Optional
from cryptography.fernet import Fernet
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator, FernetKeyGenerator, HybridKeyGenerator
from lib.VoxaCommunications_Router.util.ri_utils import fetch_ri, save_ri
from lib.compression import JSONCompressor
from util.jsonreader import read_json_from_namespace
from util.jsonutils import json_from_keys
from util.filereader import file_to_str, save_key_file
from util.logging import log
from util.wrappers import deprecated

#TODO: Move towards a hybrid key system
class KeyManager:
    def __init__(self, mode: Optional[str] = "node"):
        self.mode = mode
        self.logger = log()
        self.rsa_keys: dict = {}
        self.fernet_key: str = None
        self.cryptography_config = read_json_from_namespace("config.cryptography") or {}
        #self.rsa_key_generator: RSAKeyGenerator = None
        self.hybrid_key_generator: HybridKeyGenerator = None
        self._keys_exist: bool = False

    @property
    def keys_exist(self) -> bool:
        """Check if keys are loaded and valid."""
        return (self._keys_exist and 
                bool(self.rsa_keys.get("public_key")) and 
                bool(self.rsa_keys.get("private_key"))) and self.fernet_key is not None
    
    def set_rsa_keys(self, public_key: Optional[str] = None, private_key: Optional[str] = None) -> dict:
        """Set RSA keys directly, useful for testing or manual key management."""
        self.rsa_keys["public_key"] = public_key
        self.rsa_keys["private_key"] = private_key
        self._keys_exist = True
        self.logger.info("RSA keys set successfully.")
        return self.rsa_keys
    
    def set_fernet_key(self, fernet_key: Optional[str] = None) -> str:
        """Set the Fernet key directly, useful for testing or manual key management."""
        if fernet_key is None:
            self.logger.error("Fernet key cannot be None")
            return ""
        
        self.fernet_key = fernet_key
        return self.fernet_key

    def load_rsa_keys(self) -> dict:
        """Load RSA keys from storage with comprehensive error handling."""
        try:
            storage_config = read_json_from_namespace("config.storage") or {}
            if not storage_config:
                self.logger.error("Storage configuration not found.")
                self._keys_exist = False
                return {}
            
            data_dir = storage_config.get("data-dir", "data/")
            if not os.path.exists(data_dir):
                self.logger.error(f"Data directory does not exist: {data_dir}")
                self._keys_exist = False
                return {}
            
            file_name = "nri" if self.mode == "node" else "rri"  # if node then nri if relay then rri
            
            # Fetch RI data with error handling
            try:
                ri_result = fetch_ri(f"{file_name}.bin", path="local")
                if not ri_result or not ri_result.get("data"):
                    self.logger.error(f"No RI data found for mode: {self.mode}")
                    self._keys_exist = False
                    return {}
                ri_data: dict = ri_result.get("data")
            except Exception as e:
                self.logger.error(f"Failed to fetch RI data: {str(e)}")
                self._keys_exist = False
                return {}
            
            # Load public key
            public_key = ri_data.get("public_key")
            if not public_key:
                self.logger.error("Public key not found in RI data")
                self._keys_exist = False
                return {}
            
            # Load private key with error handling
            private_key_file = self.cryptography_config.get("private-key-file")
            if not private_key_file:
                self.logger.error("Private key file not specified in cryptography config")
                self._keys_exist = False
                return {}
            
            private_key_path = os.path.join(data_dir, "local", private_key_file)
            if not os.path.exists(private_key_path):
                self.logger.error(f"Private key file does not exist: {private_key_path}")
                self._keys_exist = False
                return {}
            
            try:
                private_key = file_to_str(private_key_path)
                if not private_key:
                    self.logger.error("Private key file is empty or could not be read")
                    self._keys_exist = False
                    return {}
            except Exception as e:
                self.logger.error(f"Failed to read private key file: {str(e)}")
                self._keys_exist = False
                return {}
            
            # Successfully loaded both keys
            self.rsa_keys["public_key"] = public_key
            self.rsa_keys["private_key"] = private_key
            self._keys_exist = True
            self.logger.info(f"RSA keys successfully loaded for mode: {self.mode}")
            return self.rsa_keys
            
        except Exception as e:
            self.logger.error(f"Unexpected error loading RSA keys: {str(e)}")
            self._keys_exist = False
            return {}
        
    def generate_hybrid_keys(self) -> dict:
        try:
            self.hybrid_key_generator = HybridKeyGenerator()
            self.hybrid_key_generator.generate_hybrid_keys()

            generated_keys = self.hybrid_key_generator.get_keys()
            if not generated_keys:
                self.logger.error("Failed to generate hybrid keys - no keys returned")
                self._keys_exist = False
                return {}
            
            self.rsa_keys = json_from_keys(
                ["public_key", "private_key"],
                generated_keys.get("rsa", {})
            )

            if not self.rsa_keys.get("public_key") or not self.rsa_keys.get("private_key"):
                self.logger.error("Generated RSA keys are incomplete")
                self._keys_exist = False
                return {}
            
            if not generated_keys.get("fernet"):
                self.logger.error("Generated Fernet key is missing")
                self._keys_exist = False
                return {}
            self.fernet_key = generated_keys.get("fernet")

            return {
                "rsa": self.rsa_keys,
                "fernet": self.fernet_key
            }

        except Exception as e:
            self.logger.error(f"Failed to generate hybrid keys: {str(e)}")
            self._keys_exist = False
            return {}   
    
    def generate_rsa_keys(self) -> dict:
        """Generate new RSA keys with error handling."""
        try:
            self.rsa_key_generator = RSAKeyGenerator()
            self.rsa_key_generator.generate_keys()
            
            generated_keys = self.rsa_key_generator.get_keys()
            if not generated_keys:
                self.logger.error("Failed to generate RSA keys - no keys returned")
                self._keys_exist = False
                return {}
            
            self.rsa_keys = json_from_keys([
                "public_key", "private_key"
            ], generated_keys)
            
            if not self.rsa_keys.get("public_key") or not self.rsa_keys.get("private_key"):
                self.logger.error("Generated RSA keys are incomplete")
                self._keys_exist = False
                return {}
            
            self._keys_exist = True
            self.logger.info("RSA keys successfully generated")
            return self.rsa_keys
            
        except Exception as e:
            self.logger.error(f"Failed to generate RSA keys: {str(e)}")
            self._keys_exist = False
            return {}
    
    def save_hybrid_keys(self) -> dict:
        """Save Hybrid keys to storage with comprehensive error handling."""
        try:
            if not self.keys_exist:
                self.logger.error("Cannot save Hybrid keys - no valid keys available")
                return {}
            
            storage_config = read_json_from_namespace("config.storage") or {}
            if not storage_config:
                self.logger.error("Storage configuration not found.")
                return {}
            
            data_dir = storage_config.get("data-dir", "data/")
            local_dir = os.path.join(data_dir, "local")
            
            # Ensure directories exist
            try:
                os.makedirs(local_dir, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Failed to create directory {local_dir}: {str(e)}")
                return {}
            
            file_name = "nri" if self.mode == "node" else "rri"  # if node then nri if relay then rri
            ri_data: dict = {}
            # Fetch and update RI data
            try:
                ri_result: dict = fetch_ri(f"{file_name}", path="local").get("file_info")
                if not ri_result:
                    self.logger.warning(f"No existing RI data found for {file_name}, creating new")
                    ri_data = {}
                else:
                    ri_data: dict = ri_result.get("data")
            except Exception as e:
                self.logger.warning(f"Failed to fetch existing RI data: {str(e)}, creating new")
                ri_data = {}
            
            if isinstance(ri_data, str):
                ri_data = json.loads(ri_data)  # Ensure ri_data is a dictionary

            #self.logger.warning(type(ri_data))
            #self.logger.warning(ri_data)

            # Update and save RI data
            try:
                ri_data["public_key"] = self.rsa_keys.get("public_key")
                save_ri(f"{file_name}", ri_data, path="local")
            except Exception as e:
                self.logger.error(f"Failed to save RI data: {str(e)}")
                traceback.print_exception(type(e), e, e.__traceback__)
                return {}
            
            # Save private key
            private_key_file = self.cryptography_config.get("private-key-file")
            if not private_key_file:
                self.logger.error("Private key file not specified in cryptography config")
                return {}
            
            # Save fernet key
            fernet_key_file = self.cryptography_config.get("fernet-key-file")
            if not fernet_key_file:
                self.logger.error("Fernet key file not specified in cryptography config")
                return {}
            
            private_key_path = os.path.join(local_dir, private_key_file)
            fernet_key_path = os.path.join(local_dir, fernet_key_file)
            try:
                save_key_file(private_key_file, self.rsa_keys.get("private_key"))
                save_key_file(fernet_key_file, self.fernet_key)
                #with open(private_key_path, 'w') as f:
                #    f.write(self.rsa_keys.get("private_key"))
                #with open(fernet_key_path, 'w') as f:
                #    f.write(self.fernet_key)
                #os.chmod(private_key_path, 0o600)  # Set secure permissions
            except Exception as e:
                self.logger.error(f"Failed to save private key file: {str(e)}")
                return {}
            
            self.logger.info(f"RSA keys saved successfully for mode: {self.mode}")
            return self.rsa_keys
            
        except Exception as e:
            self.logger.error(f"Unexpected error saving RSA keys: {str(e)}")
            traceback.print_exception(type(e), e, e.__traceback__)
            return {}

    # Depricated method, use save_hybrid_keys instead
    @deprecated("Use save_hybrid_keys instead")
    def save_rsa_keys(self) -> dict:
        """Save RSA keys to storage with comprehensive error handling."""
        try:
            if not self.keys_exist:
                self.logger.error("Cannot save RSA keys - no valid keys available")
                return {}
            
            storage_config = read_json_from_namespace("config.storage") or {}
            if not storage_config:
                self.logger.error("Storage configuration not found.")
                return {}
            
            data_dir = storage_config.get("data-dir", "data/")
            local_dir = os.path.join(data_dir, "local")
            
            # Ensure directories exist
            try:
                os.makedirs(local_dir, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Failed to create directory {local_dir}: {str(e)}")
                return {}
            
            file_name = "nri" if self.mode == "node" else "rri"  # if node then nri if relay then rri
            ri_data: dict = {}
            # Fetch and update RI data
            try:
                ri_result: dict = fetch_ri(f"{file_name}", path="local").get("file_info")
                if not ri_result:
                    self.logger.warning(f"No existing RI data found for {file_name}, creating new")
                    ri_data = {}
                else:
                    ri_data: dict = ri_result.get("data")
            except Exception as e:
                self.logger.warning(f"Failed to fetch existing RI data: {str(e)}, creating new")
                ri_data = {}
            
            if isinstance(ri_data, str):
                ri_data = json.loads(ri_data)  # Ensure ri_data is a dictionary

            #self.logger.warning(type(ri_data))
            #self.logger.warning(ri_data)

            # Update and save RI data
            try:
                ri_data["public_key"] = self.rsa_keys.get("public_key")
                save_ri(f"{file_name}", ri_data, path="local")
            except Exception as e:
                self.logger.error(f"Failed to save RI data: {str(e)}")
                traceback.print_exception(type(e), e, e.__traceback__)
                return {}
            
            # Save private key
            private_key_file = self.cryptography_config.get("private-key-file")
            if not private_key_file:
                self.logger.error("Private key file not specified in cryptography config")
                return {}
            
            private_key_path = os.path.join(local_dir, private_key_file)
            try:
                with open(private_key_path, 'w') as f:
                    f.write(self.rsa_keys.get("private_key"))
                #os.chmod(private_key_path, 0o600)  # Set secure permissions
            except Exception as e:
                self.logger.error(f"Failed to save private key file: {str(e)}")
                return {}
            
            self.logger.info(f"RSA keys saved successfully for mode: {self.mode}")
            return self.rsa_keys
            
        except Exception as e:
            self.logger.error(f"Unexpected error saving RSA keys: {str(e)}")
            traceback.print_exception(type(e), e, e.__traceback__)
            return {}