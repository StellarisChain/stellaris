import json
import os
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Query
from lib.compression import JSONCompressor
from util.jsonreader import read_json_from_namespace
from util.logging import log

def handler(node_id: Optional[str] = Query(None, description="Specific node ID to fetch. If not provided, returns all NRI files.")):
    """
    Handle fetching Node Routing Information (NRI).
    Returns all NRI files or a specific one based on the node_id parameter.
    
    Args:
        node_id: Optional node ID to fetch specific NRI data
        
    Returns:
        dict: Response with NRI data (single node or all nodes)
    """
    logger = log()
    logger.info(f"Processing NRI fetch request for node_id: {node_id if node_id else 'all nodes'}")
    
    try:
        # Get storage configuration
        storage_config = read_json_from_namespace("config.storage")
        if not storage_config:
            raise HTTPException(status_code=500, detail="Storage configuration not found")
        
        # Construct the NRI directory path
        data_dir = storage_config.get("data-dir", "data/")
        nri_subdir = storage_config.get("sub-dirs", {}).get("nri", "nri/")
        nri_dir = os.path.join(data_dir, nri_subdir)
        
        # Check if NRI directory exists
        if not os.path.exists(nri_dir):
            logger.warning(f"NRI directory does not exist: {nri_dir}")
            return {
                "success": True,
                "message": "No NRI data found",
                "count": 0,
                "data": []
            }
        
        # Initialize the compressor
        compressor = JSONCompressor()
        
        if node_id:
            # Fetch specific node
            file_path = os.path.join(nri_dir, f"{node_id}.bin")
            
            if not os.path.exists(file_path):
                logger.warning(f"NRI file not found for node_id: {node_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"NRI entry not found for node_id: {node_id}"
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
                
                logger.info(f"Successfully fetched NRI for node_id: {node_id}")
                
                return {
                    "success": True,
                    "message": f"NRI data retrieved for node_id: {node_id}",
                    "node_id": node_id,
                    "file_size": file_size,
                    "original_size": original_size,
                    "compression_ratio": round(original_size / file_size, 2) if file_size > 0 else 0,
                    "data": nri_data
                }
                
            except Exception as e:
                logger.error(f"Error reading NRI file for node_id {node_id}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to read NRI data for node_id: {node_id}"
                )
        
        else:
            # Fetch all NRI files
            nri_files = []
            total_files = 0
            total_compressed_size = 0
            total_original_size = 0
            failed_files = []
            
            try:
                # List all .bin files in the NRI directory
                for filename in os.listdir(nri_dir):
                    if filename.endswith('.bin'):
                        file_path = os.path.join(nri_dir, filename)
                        node_id_from_file = filename[:-4]  # Remove .bin extension
                        
                        try:
                            # Read and decompress the file
                            with open(file_path, 'rb') as f:
                                compressed_data = f.read()
                            
                            json_data = compressor.decompress(compressed_data)
                            nri_data = json.loads(json_data)
                            
                            # Get file statistics
                            file_size = os.path.getsize(file_path)
                            original_size = len(json_data.encode('utf-8'))
                            
                            nri_files.append({
                                "node_id": node_id_from_file,
                                "file_size": file_size,
                                "original_size": original_size,
                                "compression_ratio": round(original_size / file_size, 2) if file_size > 0 else 0,
                                "data": nri_data
                            })
                            
                            total_files += 1
                            total_compressed_size += file_size
                            total_original_size += original_size
                            
                        except Exception as e:
                            logger.error(f"Error reading NRI file {filename}: {e}")
                            failed_files.append({
                                "filename": filename,
                                "node_id": node_id_from_file,
                                "error": str(e)
                            })
                
                logger.info(f"Successfully fetched {total_files} NRI files")
                
                response = {
                    "success": True,
                    "message": f"Retrieved {total_files} NRI entries",
                    "count": total_files,
                    "total_compressed_size": total_compressed_size,
                    "total_original_size": total_original_size,
                    "overall_compression_ratio": round(total_original_size / total_compressed_size, 2) if total_compressed_size > 0 else 0,
                    "data": nri_files
                }
                
                # Include failed files info if any
                if failed_files:
                    response["failed_files"] = failed_files
                    response["failed_count"] = len(failed_files)
                
                return response
                
            except Exception as e:
                logger.error(f"Error listing NRI directory: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read NRI directory"
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