global_config: dict = {
    "type": "relay" # or "node"
}

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
