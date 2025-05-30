from typing import Optional
from VoxaCommunications_Router.stores.globalsettings import get_global_config
from VoxaCommunications_Router.cryptography.relayintegrity import RelayIntegrityManager

class NodeHandler:
    def __init__(self, node_ip: str, global_config_override: Optional[dict] = get_global_config()):
        self.node_ip = node_ip
        self.global_config = global_config_override or get_global_config()
        self.mode = self.global_config.get("type", "relay") # default to "relay" if not set
        self.relay_integrity_manager = RelayIntegrityManager(request_ip=self.node_ip)
  