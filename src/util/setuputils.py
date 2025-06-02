from typing import Optional
from util.dirutils import create_dir_if_not_exists
from util.jsonreader import read_json_from_namespace

def setup_directories(config_namespace: Optional[str] = "config.storage") -> None:
    config: dict = read_json_from_namespace(config_namespace)
    if not config:
        raise ValueError(f"Configuration not found for namespace: {config_namespace}")
    directories = config.get("sub-dirs", {})
    if not directories:
        raise ValueError("No directories specified in the configuration.")
    for dir_name, dir_path in directories.items():
        if not dir_path:
            raise ValueError(f"Directory path for {dir_name} is empty.")
        full_path = f"{config['data-dir']}{dir_path}"
        create_dir_if_not_exists(full_path)