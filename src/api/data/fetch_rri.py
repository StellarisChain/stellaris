import json
import os
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Query
from lib.compression import JSONCompressor
from util.jsonreader import read_json_from_namespace
from util.logging import log

def handler(relay_id: Optional[str] = Query(None, description="Specific relay ID to fetch. If not provided, returns all RRI files.")):
    """
    Handle fetching Relay Routing Information (RRI).
    Returns all RRI files or a specific one based on the relay_id parameter.
    
    Args:
        relay_id: Optional relay ID to fetch specific RRI data
        
    Returns:
        dict: Response with RRI data (single relay or all relays)
    """
    logger = log()
    logger.info(f"Processing RRI fetch request for relay_id: {relay_id if relay_id else 'all relays'}")
    
    try:
        # Get storage configuration
        storage_config = read_json_from_namespace("config.storage")
        if not storage_config:
            raise HTTPException(status_code=500, detail="Storage configuration not found")
        
        # Construct the RRI directory path
        data_dir = storage_config.get("data-dir", "data/")
        rri_subdir = storage_config.get("sub-dirs", {}).get("rri", "rri/")
        rri_dir = os.path.join(data_dir, rri_subdir)
        
        # Check if RRI directory exists
        if not os.path.exists(rri_dir):
            logger.warning(f"RRI directory does not exist: {rri_dir}")
            return {
                "success": True,
                "message": "No RRI data found",
                "count": 0,
                "data": []
            }
        
        # Initialize the compressor
        compressor = JSONCompressor()
        
        if relay_id:
            # Fetch specific relay
            file_path = os.path.join(rri_dir, f"{relay_id}.bin")
            
            if not os.path.exists(file_path):
                logger.warning(f"RRI file not found for relay_id: {relay_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"RRI entry not found for relay_id: {relay_id}"
                )
            
            try:
                # Read and decompress the file
                with open(file_path, 'rb') as f:
                    compressed_data = f.read()
                
                json_data = compressor.decompress(compressed_data)
                rri_data = json.loads(json_data)
                
                # Get file statistics
                file_size = os.path.getsize(file_path)
                original_size = len(json_data.encode('utf-8'))
                
                logger.info(f"Successfully fetched RRI for relay_id: {relay_id}")
                
                return {
                    "success": True,
                    "message": f"RRI data retrieved for relay_id: {relay_id}",
                    "relay_id": relay_id,
                    "file_size": file_size,
                    "original_size": original_size,
                    "compression_ratio": round(original_size / file_size, 2) if file_size > 0 else 0,
                    "data": rri_data
                }
                
            except Exception as e:
                logger.error(f"Error reading RRI file for relay_id {relay_id}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to read RRI data for relay_id: {relay_id}"
                )
        
        else:
            # Fetch all RRI files
            rri_files = []
            total_files = 0
            total_compressed_size = 0
            total_original_size = 0
            failed_files = []
            
            try:
                # List all .bin files in the RRI directory
                for filename in os.listdir(rri_dir):
                    if filename.endswith('.bin'):
                        file_path = os.path.join(rri_dir, filename)
                        relay_id_from_file = filename[:-4]  # Remove .bin extension
                        
                        try:
                            # Read and decompress the file
                            with open(file_path, 'rb') as f:
                                compressed_data = f.read()
                            
                            json_data = compressor.decompress(compressed_data)
                            rri_data = json.loads(json_data)
                            
                            # Get file statistics
                            file_size = os.path.getsize(file_path)
                            original_size = len(json_data.encode('utf-8'))
                            
                            rri_files.append({
                                "relay_id": relay_id_from_file,
                                "file_size": file_size,
                                "original_size": original_size,
                                "compression_ratio": round(original_size / file_size, 2) if file_size > 0 else 0,
                                "data": rri_data
                            })
                            
                            total_files += 1
                            total_compressed_size += file_size
                            total_original_size += original_size
                            
                        except Exception as e:
                            logger.error(f"Error reading RRI file {filename}: {e}")
                            failed_files.append({
                                "filename": filename,
                                "relay_id": relay_id_from_file,
                                "error": str(e)
                            })
                
                logger.info(f"Successfully fetched {total_files} RRI files")
                
                response = {
                    "success": True,
                    "message": f"Retrieved {total_files} RRI entries",
                    "count": total_files,
                    "total_compressed_size": total_compressed_size,
                    "total_original_size": total_original_size,
                    "overall_compression_ratio": round(total_original_size / total_compressed_size, 2) if total_compressed_size > 0 else 0,
                    "data": rri_files
                }
                
                # Include failed files info if any
                if failed_files:
                    response["failed_files"] = failed_files
                    response["failed_count"] = len(failed_files)
                
                return response
                
            except Exception as e:
                logger.error(f"Error listing RRI directory: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read RRI directory"
                )
    
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        raise HTTPException(status_code=500, detail="Storage directory configuration error")
    
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error fetching RRI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching RRI")