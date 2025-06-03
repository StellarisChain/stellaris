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

"""
curl -X POST "http://localhost:9000/data/add_nri/" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "mainnet-1",
    "node_ip": "192.168.1.100",
    "node_port": 8080,
    "node_type": "standard",
    "capabilities": ["routing", "forwarding"],
    "routing_table": {"default": "192.168.1.1"},
    "metadata": {"location": "datacenter-1"}
  }'
"""

def handler(request: Request, nri_data: NRISchema):
    """
    Handle adding new Node Routing Information (NRI).
    Creates a new file with the node ID, validates against schema,
    compresses it, and saves it in the /data/nri/ directory.
    
    Args:
        request: FastAPI request object
        nri_data: Validated NRI data from request body
        
    Returns:
        dict: Response with success status and file information
    """
    logger = log()
    logger.info(f"Processing NRI add request for node_id: {nri_data.node_id}")
    
    try:
        # Get storage configuration
        storage_config: dict = read_json_from_namespace("config.storage")
        if not storage_config:
            raise HTTPException(status_code=500, detail="Storage configuration not found")
        
        # Construct the NRI directory path
        data_dir = storage_config.get("data-dir", "data/")
        nri_subdir = storage_config.get("sub-dirs", {}).get("nri", "nri/")
        nri_dir = os.path.join(data_dir, nri_subdir)
        
        # Ensure the NRI directory exists
        os.makedirs(nri_dir, exist_ok=True)
        
        # Add metadata to the NRI data
        nri_dict = nri_data.dict()
        nri_dict["created_at"] = datetime.utcnow().isoformat()
        nri_dict["last_updated"] = datetime.utcnow().isoformat()
        nri_dict["version"] = "1.0"
        
        # Convert to JSON string
        json_data = json.dumps(nri_dict, indent=2, ensure_ascii=False)
        
        # Initialize the compressor
        compressor = JSONCompressor()
        
        # Compress the JSON data
        compressed_data = compressor.compress(json_data)
        
        # Define the file path using node_id as filename
        file_path = os.path.join(nri_dir, f"{nri_data.node_id}.bin")
        
        # Check if file already exists
        if os.path.exists(file_path):
            logger.warning(f"NRI file already exists for node_id: {nri_data.node_id}")
            raise HTTPException(
                status_code=409, 
                detail=f"NRI entry already exists for node_id: {nri_data.node_id}"
            )
        
        # Write the compressed data to file
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        
        # Get file statistics
        file_size = os.path.getsize(file_path)
        original_size = len(json_data.encode('utf-8'))
        compression_ratio = original_size / file_size if file_size > 0 else 0
        
        logger.info(f"Successfully created NRI file: {file_path}")
        logger.info(f"Original size: {original_size} bytes, Compressed size: {file_size} bytes, Ratio: {compression_ratio:.2f}x")
        
        return {
            "success": True,
            "message": f"NRI entry created successfully for node_id: {nri_data.node_id}",
            "node_id": nri_data.node_id,
            "file_path": file_path,
            "file_size": file_size,
            "original_size": original_size,
            "compression_ratio": round(compression_ratio, 2),
            "created_at": nri_dict["created_at"]
        }
        
    except ValidationError as e:
        logger.error(f"Validation error for NRI data: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        raise HTTPException(status_code=500, detail="Storage directory configuration error")
    
    except OSError as e:
        logger.error(f"File system error: {e}")
        raise HTTPException(status_code=500, detail="Failed to write NRI file to storage")
    
    except Exception as e:
        logger.error(f"Unexpected error creating NRI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating NRI")