"""
API routes for node status and chain synchronization.
"""

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import logging

from stellaris.node.chain_sync import get_chain_synchronizer
from stellaris.node.security_monitor import get_security_monitor
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.handshake_handler import get_handshake_manager, verify_handshake

# Setup logging
logger = logging.getLogger("stellaris.node.routes.status")

# Create router
router = APIRouter(tags=["status"])


class NodeStatus(BaseModel):
    """Node status model."""
    height: int
    peers: int
    is_syncing: bool
    sync_progress: Optional[float] = None
    version: str = "0.1.0"
    uptime: float


class SyncStatus(BaseModel):
    """Sync status model."""
    is_syncing: bool
    last_sync_time: float
    last_sync_duration: float
    blocks_processed: int
    sync_failures: int
    known_peers: Dict[str, int]


@router.get("/status", response_model=NodeStatus)
async def get_status(
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Get current node status.
    
    This endpoint provides:
    1. Current blockchain height
    2. Number of connected peers
    3. Sync status
    4. Node version
    5. Uptime
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
    
    # Get services
    chain_sync = get_chain_synchronizer()
    handshake_manager = get_handshake_manager()
    
    if not chain_sync.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get current height using Stellaris database format
        height = await chain_sync._get_our_height()
        
        # Get peers
        peers = await handshake_manager.get_trusted_peers()
        peer_count = len(peers)
        
        # Get sync status
        is_syncing = chain_sync.is_syncing
        
        # Calculate sync progress if syncing
        sync_progress = None
        if is_syncing and chain_sync.known_peer_heights:
            # Find max peer height
            max_peer_height = max(chain_sync.known_peer_heights.values()) if chain_sync.known_peer_heights else height
            if max_peer_height > height and max_peer_height > 0:
                sync_progress = height / max_peer_height
        
        # Get uptime (simulated)
        import time
        uptime = time.time() - chain_sync.sync_stats.get("start_time", time.time())
        
        return NodeStatus(
            height=height,
            peers=peer_count,
            is_syncing=is_syncing,
            sync_progress=sync_progress,
            uptime=uptime
        )
        
    except Exception as e:
        logger.error(f"Error getting node status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting node status: {str(e)}")


@router.get("/status/sync", response_model=SyncStatus)
async def get_sync_status(
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Get detailed synchronization status.
    
    This endpoint provides:
    1. Current sync status
    2. Last sync time and duration
    3. Number of blocks processed
    4. Sync failures
    5. Known peers and their heights
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
    
    # Get chain sync
    chain_sync = get_chain_synchronizer()
    
    if not chain_sync.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get sync stats
        stats = chain_sync.sync_stats
        
        return SyncStatus(
            is_syncing=chain_sync.is_syncing,
            last_sync_time=stats.get("last_sync_time", 0),
            last_sync_duration=stats.get("last_sync_duration", 0),
            blocks_processed=stats.get("blocks_processed", 0),
            sync_failures=stats.get("sync_failures", 0),
            known_peers=chain_sync.known_peer_heights
        )
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}")


@router.post("/status/sync/trigger")
async def trigger_sync(
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Trigger a manual synchronization.
    
    This endpoint allows triggering a manual sync with peers.
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
    
    # Get chain sync
    chain_sync = get_chain_synchronizer()
    
    if not chain_sync.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Check if already syncing
        if chain_sync.is_syncing:
            return {"success": False, "message": "Sync already in progress"}
        
        # Trigger sync
        asyncio.create_task(chain_sync.sync_with_peers())
        
        return {"success": True, "message": "Sync triggered successfully"}
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=f"Error triggering sync: {str(e)}")