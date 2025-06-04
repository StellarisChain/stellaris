import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Request
from pydantic import BaseModel, validator, ValidationError
from lib.compression import JSONCompressor
from util.jsonreader import read_json_from_namespace
from util.logging import log
from schema.NRISchema import NRISchema

def handler():
    """
    Handle fetching Node Routing Information (NRI).
        
    Returns:
        dict: Response with success status and file information
    """
    logger = log()
    logger.info(f"Loading local NRI data")
    
    try:
        # Get storage configuration
        storage_config: dict = read_json_from_namespace("config.storage")
        if not storage_config:
            raise HTTPException(status_code=500, detail="Storage configuration not found")
        
        # Construct the NRI directory path
        data_dir = storage_config.get("data-dir", "data/")
        nri_subdir = storage_config.get("sub-dirs", {}).get("local", "local/")
        nri_dir = os.path.join(data_dir, nri_subdir)
        
        # Ensure the NRI directory exists, if it dosen't, something is wrong
        if not os.path.exists(nri_dir):
            logger.warning(f"NRI directory does not exist: {nri_dir}")
            return {
                "success": False,
                "message": "No NRI data found",
            }
        
        # Initialize the compressor
        compressor = JSONCompressor()
        # Fetch specific node
        file_path = os.path.join(nri_dir, f"nri.bin")
        
        if not os.path.exists(file_path):
            logger.warning(f"NRI file not found")
            raise HTTPException(
                status_code=404,
                detail=f"NRI entry not found"
            )
        
        try:
            # Read and decompress the file
            with open(file_path, 'rb') as f:
                compressed_data = f.read()
            
            json_data = compressor.decompress(compressed_data)
            nri_data = json.loads(json_data)
            
            # Get file statistics
            file_size = os.path.getsize(file_path)
            original_size = len(json_data.encode('utf-8'))
            
            logger.info(f"Successfully fetched local NRI")
            
            return {
                "success": True,
                "message": f"NRI data retrieved",
                "file_size": file_size,
                "original_size": original_size, # Irrevalant however, we keep it for consistency
                "compression_ratio": round(original_size / file_size, 2) if file_size > 0 else 0,
                "data": nri_data
            }
            
        except Exception as e:
            logger.error(f"Error reading NRI file for: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read NRI data"
            )
    
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        raise HTTPException(status_code=500, detail="Storage directory configuration error")
    
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error fetching NRI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching NRI")