import requests
import json
from lib.VoxaCommunications_Router.registry.client import RegistryClient
from typing import Optional

class RegistryManager:

    registry_url: str = "https://voxa-registry.connor33341.dev/"
    api_version: str = "v1"

    def __init__(self, client_type: str = "relay" | "node" | "user" | "other"):
        self.client_type = client_type
        self.client = RegistryClient(client_type=client_type, registry_url=self.registry_url, api_version=self.api_version)
        self.session_token = ""

    def set_credentials(self, email: Optional[str] = None, password: Optional[str] = None, token: Optional[str] = None, code: Optional[str] = None):
        """
        Sets the credentials for the RegistryClient instance.

        Args:
            email (str): The email address of the user.
            password (str): The password of the user.
            token (str): The authentication token.
            code (str): The verification code.
        """
        self.client.set_credentials(email=email, password=password, token=token, code=code)

    def login(self) -> bool:
        """
        Logs in the user using the provided credentials.

        Returns:
            bool: True if login is successful, False otherwise.
        """
        success =  self.client.login()
        self.session_token = self.client.session_token
        return success
    
    def get_client(self) -> RegistryClient:
        """
        Returns the RegistryClient instance for interacting with the Voxa registry.

        Returns:
            RegistryClient: The client instance.
        """
        return self.client
    
    def get_registry_url(self) -> str:
        """
        Returns the base URL for the Voxa registry.
        """
        return self.registry_url
    
    def get_api_version(self) -> str:
        """
        Returns the API version for the Voxa registry.
        """
        return self.api_version
    
    def set_registry_url(self, url: str):
        """
        Sets the base URL for the Voxa registry.
        
        Args:
            url (str): The new base URL for the registry.
        """
        self.registry_url = url
    
    def set_api_version(self, version: str):
        """
        Sets the API version for the Voxa registry.

        Args:
            version (str): The new API version for the registry.
        """
        self.api_version = version