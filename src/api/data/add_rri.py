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
from schema.RRISchema import RRISchema

def handler(request: Request, rri_data: RRISchema):
    """
    Handle adding new Relay Routing Information (RRI).
    Creates a new file with the relay ID, validates against schema,
    compresses it, and saves it in the /data/rri/ directory.
    
    Args:
        request: FastAPI request object
        rri_data: Validated RRI data from request body
        
    Returns:
        dict: Response with success status and file information
    """
    logger = log()
    logger.info(f"Processing RRI add request for relay_id: {rri_data.relay_id}")
    
    try:
        # Get storage configuration
        storage_config: dict = read_json_from_namespace("config.storage")
        if not storage_config:
            raise HTTPException(status_code=500, detail="Storage configuration not found")
        
        # Construct the RRI directory path
        data_dir = storage_config.get("data-dir", "data/")
        rri_subdir = storage_config.get("sub-dirs", {}).get("rri", "rri/")
        rri_dir = os.path.join(data_dir, rri_subdir)
        
        # Ensure the RRI directory exists
        os.makedirs(rri_dir, exist_ok=True)
        
        # Add metadata to the RRI data
        rri_dict = rri_data.dict()
        rri_dict["created_at"] = datetime.utcnow().isoformat()
        rri_dict["last_updated"] = datetime.utcnow().isoformat()
        rri_dict["version"] = "1.0"
        
        # Convert to JSON string
        json_data = json.dumps(rri_dict, indent=2, ensure_ascii=False)
        
        # Initialize the compressor
        compressor = JSONCompressor()
        
        # Compress the JSON data
        compressed_data = compressor.compress(json_data)
        
        # Define the file path using relay_id as filename
        file_path = os.path.join(rri_dir, f"{rri_data.relay_id}.bin")
        
        # Check if file already exists
        if os.path.exists(file_path):
            logger.warning(f"RRI file already exists for relay_id: {rri_data.relay_id}")
            raise HTTPException(
                status_code=409, 
                detail=f"RRI entry already exists for relay_id: {rri_data.relay_id}"
            )
        
        # Write the compressed data to file
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        
        # Get file statistics
        file_size = os.path.getsize(file_path)
        original_size = len(json_data.encode('utf-8'))
        compression_ratio = original_size / file_size if file_size > 0 else 0
        
        logger.info(f"Successfully created RRI file: {file_path}")
        logger.info(f"Original size: {original_size} bytes, Compressed size: {file_size} bytes, Ratio: {compression_ratio:.2f}x")
        
        return {
            "success": True,
            "message": f"RRI entry created successfully for relay_id: {rri_data.relay_id}",
            "relay_id": rri_data.relay_id,
            "file_path": file_path,
            "file_size": file_size,
            "original_size": original_size,
            "compression_ratio": round(compression_ratio, 2),
            "created_at": rri_dict["created_at"]
        }
        
    except ValidationError as e:
        logger.error(f"Validation error for RRI data: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        raise HTTPException(status_code=500, detail="Storage directory configuration error")
    
    except OSError as e:
        logger.error(f"File system error: {e}")
        raise HTTPException(status_code=500, detail="Failed to write RRI file to storage")
    
    except Exception as e:
        logger.error(f"Unexpected error creating RRI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating RRI")