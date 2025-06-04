from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.registry.client import RegistryClient

global_registry_manager: RegistryManager = None

def get_global_registry_manager() -> RegistryManager:
    return global_registry_manager

def set_global_registry_manager(manager: RegistryManager):
    global global_registry_manager
    if not isinstance(manager, RegistryManager):
        raise TypeError("Expected an instance of RegistryManager")
    global_registry_manager = manager