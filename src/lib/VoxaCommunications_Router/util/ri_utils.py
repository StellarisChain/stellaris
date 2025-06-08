import os
import json
from typing import Optional
from util.jsonreader import read_json_from_namespace
from util.logging import log
from lib.compression import JSONCompressor

def fetch_ri(file_name, path: Optional[str] = "local") -> dict:
    """
    Fetch Node Routing Information (NRI) from local storage.
        
    Returns:
        dict: Response with success status and file information
    """
    
    logger = log()
    logger.info(f"Loading local NRI data")
    
    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        return None
    
    # Construct the NRI directory path
    data_dir = storage_config.get("data-dir", "data/")
    nri_subdir = dict(storage_config.get("sub-dirs", {})).get(path, "local/")
    nri_dir = os.path.join(data_dir, nri_subdir)
    
    # Ensure the NRI directory exists, if it dosen't, something is wrong
    if not os.path.exists(nri_dir):
        logger.warning(f"NRI directory does not exist: {nri_dir}")
        return None
    
    # Initialize the compressor
    compressor = JSONCompressor()
    # Fetch specific node
    file_path = os.path.join(nri_dir, f"{file_name}.bin")
    
    if not os.path.exists(file_path):
        logger.warning(f"RI file not found")
        return None
    
    # Read and decompress the file
    with open(file_path, 'rb') as f:
        compressed_data = f.read()
    
    json_data = compressor.decompress(compressed_data)
    nri_data = json.loads(json_data)
    
    # Get file statistics
    file_size = os.path.getsize(file_path)
    original_size = len(json_data.encode('utf-8'))
    
    logger.info(f"Successfully fetched local RI")
    
    return {
        "success": True,
        "file_info": {
            "file_path": file_path,
            "file_size": file_size,
            "original_size": original_size,
            "data": nri_data
        }
    }