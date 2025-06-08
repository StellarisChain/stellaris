import os
import json
from typing import Optional, Dict, Any
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

def save_ri(file_name: str, data: Dict[Any, Any], path: Optional[str] = "local") -> dict:
    """
    Save Node Routing Information (NRI) to local storage with compression.
    
    Args:
        file_name (str): Name of the file to save (without extension)
        data (Dict[Any, Any]): The NRI data to save
        path (str, optional): Storage path subdirectory. Defaults to "local".
        
    Returns:
        dict: Response with success status and file information
    """
    
    logger = log()
    logger.info(f"Saving local NRI data: {file_name}")
    
    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        logger.error("Storage configuration not found")
        return {
            "success": False,
            "error": "Storage configuration not available"
        }
    
    # Construct the NRI directory path
    data_dir = storage_config.get("data-dir", "data/")
    nri_subdir = dict(storage_config.get("sub-dirs", {})).get(path, "local/")
    nri_dir = os.path.join(data_dir, nri_subdir)
    
    # Ensure the NRI directory exists, create if it doesn't
    if not os.path.exists(nri_dir):
        logger.info(f"Creating NRI directory: {nri_dir}")
        try:
            os.makedirs(nri_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create NRI directory: {e}")
            return {
                "success": False,
                "error": f"Failed to create directory: {e}"
            }
    
    # Initialize the compressor
    compressor = JSONCompressor()
    file_path = os.path.join(nri_dir, f"{file_name}.bin")
    
    try:
        # Convert data to JSON string
        json_data = json.dumps(data, indent=2)
        original_size = len(json_data.encode('utf-8'))
        
        # Compress the JSON data
        compressed_data = compressor.compress(json_data)
        
        # Write compressed data to file
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        
        # Get file statistics
        file_size = os.path.getsize(file_path)
        compression_ratio = (1 - file_size / original_size) * 100 if original_size > 0 else 0
        
        logger.info(f"Successfully saved NRI data to {file_path}")
        logger.info(f"Compression: {original_size} -> {file_size} bytes ({compression_ratio:.1f}% saved)")
        
        return {
            "success": True,
            "file_info": {
                "file_path": file_path,
                "file_size": file_size,
                "original_size": original_size,
                "compression_ratio": compression_ratio,
                "records_saved": len(data) if isinstance(data, (dict, list)) else 1
            }
        }
        
    except json.JSONEncodeError as e:
        logger.error(f"Failed to serialize data to JSON: {e}")
        return {
            "success": False,
            "error": f"JSON serialization error: {e}"
        }
    except Exception as e:
        logger.error(f"Failed to save NRI data: {e}")
        return {
            "success": False,
            "error": f"Save operation failed: {e}"
        }