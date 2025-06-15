from util.jsonutils import json_from_keys, lists_to_dict

SSU_NODE_CONFIG_KEYS: list[str] = [
    "host",
    "port"
]
SSU_NODE_CONFIG_DEFAULT_VALUES: list[str] = [
    "0.0.0.0",
    9999
]

class SSUNode:
    def __init__(self, config: dict):
        self.config: dict = json_from_keys(SSU_NODE_CONFIG_KEYS, config) or lists_to_dict(SSU_NODE_CONFIG_KEYS, SSU_NODE_CONFIG_DEFAULT_VALUES)