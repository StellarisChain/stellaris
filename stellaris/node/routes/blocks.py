"""
API routes for block submission and querying.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel
import logging

from stellaris.node.block_processor import get_block_processor
from stellaris.node.input_validator import InputValidator
from stellaris.node.security_monitor import get_security_monitor
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.handshake_handler import get_handshake_manager, verify_handshake

# Setup logging
logger = logging.getLogger("stellaris.node.routes.blocks")

# Create router
router = APIRouter(tags=["blocks"])


class BlockSubmission(BaseModel):
    """Block submission model."""
    block: Dict[str, Any]
    handshake_token: str


class BlockResponse(BaseModel):
    """Block response model."""
    success: bool
    message: str
    block_hash: str = None


class BlocksResponse(BaseModel):
    """Blocks response model."""
    blocks: List[Dict[str, Any]]
    count: int
    next_height: Optional[int] = None


@router.post("/blocks", response_model=BlockResponse)
async def submit_block(
    submission: BlockSubmission,
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Submit a block to the network.
    
    This endpoint performs:
    1. Handshake verification
    2. Input validation
    3. Block processing
    4. Reputation tracking
    """
    # Get the block processor
    processor = get_block_processor()
    
    # Verify handshake
    if not handshake_verified:
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_handshake", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_handshake")
        
        raise HTTPException(status_code=403, detail="Invalid handshake token")
    
    # Validate block structure
    validator = InputValidator()
    if not validator.validate_block_structure(submission.block):
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_block_structure", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_block_structure")
        
        raise HTTPException(status_code=400, detail="Invalid block structure")
    
    # Process block
    try:
        success, message = await processor.submit_block(
            submission.block,
            peer_address=request.client.host
        )
        
        # Create response
        response = BlockResponse(
            success=success,
            message=message,
            block_hash=submission.block.get("hash", None) if success else None
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing block: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing block: {str(e)}")


@router.get("/blocks", response_model=BlocksResponse)
async def get_blocks(
    request: Request,
    handshake_verified: bool = Depends(verify_handshake),
    start_height: int = Query(None, description="Starting block height"),
    limit: int = Query(10, ge=1, le=100, description="Number of blocks to return"),
    direction: str = Query("desc", description="Order direction: 'asc' for ascending, 'desc' for descending")
):
    """
    Get blocks from the chain.
    
    This endpoint performs:
    1. Handshake verification
    2. Query validation
    3. Database query
    """
    # Verify handshake
    if not handshake_verified:
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_handshake", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_handshake")
        
        raise HTTPException(status_code=403, detail="Invalid handshake token")
    
    # Validate parameters
    validator = InputValidator()
    if not validator.validate_integer_range(limit, 1, 100):
        raise HTTPException(status_code=400, detail="Invalid limit")
    
    if direction not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid direction")
    
    # Get processor and database
    processor = get_block_processor()
    
    if not processor.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Determine current height if start_height is not provided
    if start_height is None:
        last_block = await processor.db.get_last_block()
        start_height = last_block.get('id', 0) if last_block else 0
    
    # Query blocks using Stellaris database format
    try:
        blocks = []
        count = len(processor.db._blocks)
        next_height = None
        
        # Get blocks from the database
        block_items = list(processor.db._blocks.items())
        
        # Sort by block ID (height)
        if direction == "desc":
            # Filter blocks with height <= start_height and sort descending
            filtered_blocks = [(hash, data) for hash, data in block_items if data.get('id', 0) <= start_height]
            filtered_blocks.sort(key=lambda x: x[1].get('id', 0), reverse=True)
        else:
            # Filter blocks with height >= start_height and sort ascending
            filtered_blocks = [(hash, data) for hash, data in block_items if data.get('id', 0) >= start_height]
            filtered_blocks.sort(key=lambda x: x[1].get('id', 0))
        
        # Take only the requested limit
        for i, (block_hash, block_data) in enumerate(filtered_blocks[:limit]):
            block_info = {
                "hash": block_hash,
                "previous_hash": block_data.get("previous_hash", ""),
                "merkle_root": block_data.get("merkle_root", ""),
                "timestamp": block_data.get("timestamp", 0),
                "difficulty": block_data.get("difficulty", 1),
                "nonce": block_data.get("random", 0),
                "height": block_data.get("id", 0),
                "size": len(block_data.get("content", "")),
                "version": 1,
                "transaction_count": len(await processor.db.get_block_transaction_hashes(block_hash)),
                "miner": block_data.get("address", ""),
                "reward": block_data.get("reward", 0)
            }
            blocks.append(block_info)
            
            # Set next_height for pagination
            if i == limit - 1:
                if direction == "desc":
                    next_height = max(0, block_data.get("id", 0) - 1)
                else:
                    next_height = block_data.get("id", 0) + 1
        
        return BlocksResponse(
            blocks=blocks,
            count=count,
            next_height=next_height
        )
        
    except Exception as e:
        logger.error(f"Error fetching blocks: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching blocks: {str(e)}")


@router.get("/blocks/{block_hash}")
async def get_block(
    block_hash: str,
    request: Request,
    handshake_verified: bool = Depends(verify_handshake),
    include_transactions: bool = Query(False, description="Whether to include transactions")
):
    """
    Get a specific block by hash.
    
    This endpoint performs:
    1. Handshake verification
    2. Hash validation
    3. Database query for block
    """
    # Verify handshake
    if not handshake_verified:
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_handshake", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_handshake")
        
        raise HTTPException(status_code=403, detail="Invalid handshake token")
    
    # Validate hash format
    validator = InputValidator()
    if not validator.validate_hash(block_hash):
        raise HTTPException(status_code=400, detail="Invalid block hash format")
    
    # Get processor and database
    processor = get_block_processor()
    
    if not processor.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Query block using Stellaris database format
    try:
        if block_hash not in processor.db._blocks:
            raise HTTPException(status_code=404, detail="Block not found")
        
        block_data = processor.db._blocks[block_hash]
        
        # Format response
        block_info = {
            "hash": block_hash,
            "previous_hash": block_data.get("previous_hash", ""),
            "merkle_root": block_data.get("merkle_root", ""),
            "timestamp": block_data.get("timestamp", 0),
            "difficulty": block_data.get("difficulty", 1),
            "nonce": block_data.get("random", 0),
            "height": block_data.get("id", 0),
            "size": len(block_data.get("content", "")),
            "version": 1,
            "transaction_count": len(await processor.db.get_block_transaction_hashes(block_hash)),
            "miner": block_data.get("address", ""),
            "reward": block_data.get("reward", 0)
        }
        
        # Include transactions if requested
        if include_transactions:
            transactions = await processor.db.get_block_transactions(block_hash, check_signatures=False, hex_only=True)
            block_info["transactions"] = transactions
        
        return block_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching block: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching block: {str(e)}")


@router.get("/blocks/height/{height}")
async def get_block_by_height(
    height: int,
    request: Request,
    handshake_verified: bool = Depends(verify_handshake),
    include_transactions: bool = Query(False, description="Whether to include transactions")
):
    """
    Get a specific block by height.
    
    This endpoint performs:
    1. Handshake verification
    2. Height validation
    3. Database query for block
    """
    # Verify handshake
    if not handshake_verified:
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_handshake", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_handshake")
        
        raise HTTPException(status_code=403, detail="Invalid handshake token")
    
    # Validate height
    if height < 0:
        raise HTTPException(status_code=400, detail="Invalid block height")
    
    # Get processor and database
    processor = get_block_processor()
    
    if not processor.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Query block using Stellaris database format (by height/id)
    try:
        # Find block with the specified height (id)
        found_block = None
        found_hash = None
        
        for block_hash, block_data in processor.db._blocks.items():
            if block_data.get('id') == height:
                found_block = block_data
                found_hash = block_hash
                break
        
        if not found_block:
            raise HTTPException(status_code=404, detail="Block not found")
        
        # Format response
        block_info = {
            "hash": found_hash,
            "previous_hash": found_block.get("previous_hash", ""),
            "merkle_root": found_block.get("merkle_root", ""),
            "timestamp": found_block.get("timestamp", 0),
            "difficulty": found_block.get("difficulty", 1),
            "nonce": found_block.get("random", 0),
            "height": found_block.get("id", 0),
            "size": len(found_block.get("content", "")),
            "version": 1,
            "transaction_count": len(await processor.db.get_block_transaction_hashes(found_hash)),
            "miner": found_block.get("address", ""),
            "reward": found_block.get("reward", 0)
        }
        
        # Include transactions if requested
        if include_transactions:
            transactions = await processor.db.get_block_transactions(found_hash, check_signatures=False, hex_only=True)
            block_info["transactions"] = transactions
        
        return block_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching block: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching block: {str(e)}")