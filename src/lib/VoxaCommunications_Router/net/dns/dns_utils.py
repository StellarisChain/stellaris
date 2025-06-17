import os
import io
import json
from typing import Dict, Any, Optional
from util.jsonreader import read_json_from_namespace
from util.logging import log
from lib.compression import JSONCompressor
from schema.dns.a_record import ARecord
from modern_benchmark import BenchmarkCollector, benchmark

logger: log = log()
benchmark_collector: BenchmarkCollector = BenchmarkCollector()


@benchmark("dns_utils.load_file", collector=benchmark_collector)
def load_file(file_name: str, path: Optional[str] = "dns") -> dict:
    """
    Fetch a JSONCompressor compresssed file, and load it into a dictionary.
    Args:
        file_name (str): The name of the file to load.
        path (Optional[str]): The path to the directory containing the file. Defaults to "dns".
    Returns:
        dict: The loaded JSON data as a dictionary.
    """
    logger.debug(f"Loading file: {file_name} from path: {path}")

    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        return None
    
    # Construct the DNS directory path
    data_dir: str = storage_config.get("data-dir", "data/")
    file_subdir: str = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
    file_dir: str = os.path.join(data_dir, file_subdir)

    # Check if the path exists
    if not os.path.exists(file_dir):
        logger.warning(f"Directory does not exist: {file_dir}")
        return None

    compressor: JSONCompressor = JSONCompressor()
    file_name = file_name.replace(".bin", "") # Remove .bin extension if present
    file_path: str = os.path.join(file_dir, f"{file_name}.bin")

    if not os.path.exists(file_path):
        logger.warning(f"File does not exist: {file_path}")
        return None
    
    with io.open(file_path, "rb") as file:
        compressed_data: bytes = file.read()
    
    json_data: str = compressor.decompress(compressed_data)
    dict_data: dict = json.loads(json_data)

    return dict_data

@benchmark("dns_utils.save_file", collector=benchmark_collector)
def save_file(file_name: str, data: dict, path: Optional[str] = "dns") -> bool:
    """
    Save a dictionary to a JSONCompressor compressed file.
    Args:
        file_name (str): The name of the file to save.
        data (dict): The data to save.
        path (Optional[str]): The path to the directory where the file will be saved. Defaults to "dns".
    Returns:
        bool: True if the file was saved successfully, False otherwise.
    """
    logger.debug(f"Saving file: {file_name} to path: {path}")

    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        return False
    
    # Construct the DNS directory path
    data_dir: str = storage_config.get("data-dir", "data/")
    file_subdir: str = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
    file_dir: str = os.path.join(data_dir, file_subdir)

    # Ensure the directory exists
    os.makedirs(file_dir, exist_ok=True)

    compressor: JSONCompressor = JSONCompressor()
    json_data: str = json.dumps(data, indent=4)
    compressed_data: bytes = compressor.compress(json_data)

    file_path: str = os.path.join(file_dir, f"{file_name}.bin")

    with io.open(file_path, "wb") as file:
        file.write(compressed_data)

    return True

