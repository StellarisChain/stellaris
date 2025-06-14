"""Kytan Controller Module

This module provides a controller class for managing Kytan client and server instances,
along with their configuration and lifecycle management.
"""

import logging
import secrets
import base64
from typing import Optional, Dict, Any
from threading import Lock

from kytan import KytanClient, KytanServer
from kytan.kytan import KytanBase
from util.jsonreader import read_json_from_namespace
from util.filereader import file_to_str, read_key_file, save_key_file


logger = logging.getLogger(__name__)


class KytanController:
    """Controller class for managing Kytan client and server instances.
    
    This class handles the configuration, initialization, and lifecycle
    management of Kytan networking components.
    """
    
    def __init__(self) -> None:
        """Initialize the KytanController with default configuration."""
        self._client: Optional[KytanClient] = None
        self._server: Optional[KytanServer] = None
        self._config: Dict[str, Any] = self._load_config()
        self._lock = Lock()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from the kytan namespace.
        
        Returns:
            Dict containing the kytan configuration, or empty dict if not found.
        """
        try:
            config = read_json_from_namespace("config.kytan")
            return config if config is not None else {}
        except Exception as e:
            logger.error(f"Failed to load kytan configuration: {e}")
            return {}
        
    def _generate_key(self, length: Optional[int] = 32) -> str:
        """Generate a secure random key.
        
        Args:
            length: Length of the key in bytes. Default is 32.
            
        Returns:
            Base64 encoded string of the generated key.
        """
        key = secrets.token_bytes(length)
        return base64.urlsafe_b64encode(key).decode('utf-8')
        
    def serve(self) -> None:
        """Start the Kytan server with configured parameters.
        
        Raises:
            RuntimeError: If no server instance is configured.
            ValueError: If server configuration is invalid.
        """
        if not self._server:
            raise RuntimeError("No server instance configured. Set server before calling serve().")
            
        server_config: dict = self._config.get("server", {})
        
        try:
            port = server_config.get("port", 9527)
            host = server_config.get("host", "0.0.0.0")
            dns = server_config.get("dns")
            
            # Load key file if specified
            key = ""
            key_file = server_config.get("key_file")
            if key_file:
                key = read_key_file(key_file, raise_error=False) or ""
                if not key:
                    logger.warning(f"Key file '{key_file}' is empty or could not be read, generating new key.")
                    key = self._generate_key()
                    save_key_file(key_file, key)
            
            logger.info(f"Starting Kytan server on {host}:{port}")
            self._server.serve(port=port, bind=host, dns=dns, key=key)
            
        except Exception as e:
            logger.error(f"Failed to start Kytan server: {e}")
            raise

    @property
    def client(self) -> Optional[KytanClient]:
        """Get the current Kytan client instance.
        
        Returns:
            The KytanClient instance or None if not set.
        """
        return self._client
    
    @client.setter
    def client(self, client: Optional[KytanClient]) -> None:
        """Set the Kytan client instance.
        
        Args:
            client: KytanClient instance or None.
            
        Raises:
            TypeError: If client is not a KytanClient instance or None.
        """
        if client is not None and not isinstance(client, KytanClient):
            raise TypeError("Expected KytanClient instance or None")
        
        with self._lock:
            self._client = client
        
        logger.debug(f"Kytan client {'set' if client else 'cleared'}")

    @property
    def server(self) -> Optional[KytanServer]:
        """Get the current Kytan server instance.
        
        Returns:
            The KytanServer instance or None if not set.
        """
        return self._server
    
    @server.setter
    def server(self, server: Optional[KytanServer]) -> None:
        """Set the Kytan server instance.
        
        Args:
            server: KytanServer instance or None.
            
        Raises:
            TypeError: If server is not a KytanServer instance or None.
        """
        if server is not None and not isinstance(server, KytanServer):
            raise TypeError("Expected KytanServer instance or None")
        
        with self._lock:
            self._server = server
            
        logger.debug(f"Kytan server {'set' if server else 'cleared'}")

    @property
    def config(self) -> Dict[str, Any]:
        """Get the current configuration.
        
        Returns:
            A copy of the current configuration dictionary.
        """
        return self._config.copy()
    
    @config.setter
    def config(self, config: Dict[str, Any]) -> None:
        """Set the configuration.
        
        Args:
            config: Configuration dictionary.
            
        Raises:
            TypeError: If config is not a dictionary.
        """
        if not isinstance(config, dict):
            raise TypeError("Expected dictionary for configuration")
        
        with self._lock:
            self._config = config.copy()
            
        logger.debug("Kytan configuration updated")

    def reload_config(self) -> None:
        """Reload configuration from the kytan namespace."""
        with self._lock:
            self._config = self._load_config()
        logger.info("Kytan configuration reloaded")

    def is_server_running(self) -> bool:
        """Check if the server is currently running.
        
        Returns:
            True if server is running, False otherwise.
        """
        # This would depend on the KytanServer implementation
        # For now, we just check if a server instance exists
        return self._server is not None

    def shutdown(self) -> None:
        """Shutdown the controller and cleanup resources."""
        with self._lock:
            if self._server:
                try:
                    # Assuming KytanServer has a shutdown method
                    if hasattr(self._server, 'shutdown'):
                        self._server.shutdown()
                    logger.info("Kytan server shutdown completed")
                except Exception as e:
                    logger.error(f"Error during server shutdown: {e}")
                    
            self._client = None
            self._server = None


# Global controller instance with thread-safe access
kytan_controller: Optional[KytanController] = None
_controller_lock = Lock()


def get_kytan_controller() -> Optional[KytanController]:
    """Get the global KytanController instance.
    
    Returns:
        The global KytanController instance or None if not initialized.
    """
    return kytan_controller


def set_kytan_controller(controller: KytanController) -> None:
    """Set the global KytanController instance.
    
    Args:
        controller: KytanController instance to set as global.
        
    Raises:
        TypeError: If controller is not a KytanController instance.
    """
    if not isinstance(controller, KytanController):
        raise TypeError("Expected KytanController instance")
    
    global kytan_controller
    with _controller_lock:
        kytan_controller = controller
    
    logger.info("Global KytanController instance set")


def initialize_kytan_controller() -> KytanController:
    """Initialize and set the global KytanController instance.
    
    Returns:
        The newly created KytanController instance.
    """
    controller = KytanController()
    set_kytan_controller(controller)
    return controller