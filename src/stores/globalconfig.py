from typing import Optional
from util.jsonreader import read_json_from_namespace

global_config: dict = None

def set_global_config(config: dict):
    global global_config
    if not isinstance(config, dict):
        raise ValueError("Global config must be a dictionary")
    global_config = config

def get_global_config() -> dict:
    global global_config
    if global_config is None:
        load_global_config()
    return global_config

def load_global_config(namespace: Optional[str] = "config.settings") -> dict:
    global global_config
    if global_config is None:
        global_config = read_json_from_namespace(namespace)
    return global_config