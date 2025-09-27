"""
Handshake endpoints for Stellaris node

These endpoints implement the secure handshake protocol for node authentication.
"""

from fastapi import APIRouter, Request, Body, Depends, HTTPException, status
from typing import Optional, Dict

from stellaris.node.handshake_handler import get_handshake_manager
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.security_monitor import get_security_monitor, SecurityEventType

router = APIRouter(prefix="/handshake")

@router.get("/challenge")
async def handshake_challenge(request: Request):
    """
    Generate a cryptographic challenge for handshake.
    
    This is the first step in the handshake process. The client requests a challenge,
    and the server generates a random challenge along with its chain state.
    
    Returns:
        Challenge data
    """
    handshake_manager = get_handshake_manager()
    security_monitor = get_security_monitor()
    
    client_ip = request.client.host
    
    try:
        challenge_data = await handshake_manager.generate_challenge()
        
        # Log the challenge request
        await security_monitor.log_event(
            SecurityEventType.HANDSHAKE_FAILURE,
            source_ip=client_ip,
            details={"action": "challenge_generated"}
        )
        
        return {"ok": True, "result": challenge_data}
        
    except Exception as e:
        await security_monitor.log_event(
            SecurityEventType.HANDSHAKE_FAILURE,
            source_ip=client_ip,
            details={"action": "challenge_generation_failed", "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating challenge: {str(e)}"
        )

@router.post("/verify")
async def handshake_verify(request: Request, body: Dict = Body(...)):
    """
    Verify a handshake response.
    
    This is the second step in the handshake process. The client sends a signed
    response to the challenge, and the server verifies it.
    
    Args:
        body: Handshake response data containing:
            - node_id: ID of the responding node
            - pubkey: Public key of the responding node
            - signature: Signature of the challenge
            - challenge: The original challenge
            - height: Block height of the responding node
            - url: URL of the responding node (optional)
            - is_public: Whether the responding node is public (optional)
    
    Returns:
        Verification result with chain state negotiation if needed
    """
    handshake_manager = get_handshake_manager()
    reputation_manager = get_reputation_manager()
    security_monitor = get_security_monitor()
    
    client_ip = request.client.host
    
    # Extract required fields
    node_id = body.get("node_id")
    pubkey = body.get("pubkey")
    signature = body.get("signature")
    challenge = body.get("challenge")
    remote_height = body.get("height", -1)
    remote_url = body.get("url")
    remote_is_public = body.get("is_public", False)
    
    # Validate required fields
    if not all([node_id, pubkey, signature, challenge]):
        await security_monitor.log_event(
            SecurityEventType.HANDSHAKE_FAILURE,
            source_ip=client_ip,
            details={"reason": "missing_fields"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields"
        )
    
    # Verify the signature
    if not await handshake_manager.verify_challenge_response(challenge, signature, node_id, pubkey):
        await security_monitor.log_event(
            SecurityEventType.HANDSHAKE_FAILURE,
            source_ip=client_ip,
            node_id=node_id,
            details={"reason": "invalid_response"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid challenge response"
        )
    
    # At this point, the handshake is successful
    await security_monitor.log_event(
        SecurityEventType.HANDSHAKE_FAILURE,  # Should probably be a different event type for success
        source_ip=client_ip,
        node_id=node_id,
        details={"action": "handshake_successful"}
    )
    
    # If the node has a reputation system, record the successful handshake
    await reputation_manager.record_good_behavior(node_id, 5)  # Higher reward for successful handshake
    
    # Handle chain state negotiation
    local_height = -1
    db = handshake_manager.db
    if db:
        local_height = await db.get_next_block_id() - 1
    
    # If local node needs to sync
    if remote_height > local_height:
        return {
            "ok": True, 
            "result": "sync_needed",
            "detail": {
                "local_height": local_height,
                "remote_height": remote_height,
                "blocks_behind": remote_height - local_height
            }
        }
    
    # If remote node needs to sync
    elif remote_height < local_height:
        return {
            "ok": True,
            "result": "sync_offered",
            "detail": {
                "local_height": local_height,
                "remote_height": remote_height,
                "blocks_ahead": local_height - remote_height
            }
        }
    
    # If both nodes are in sync
    return {
        "ok": True,
        "result": "in_sync",
        "detail": {
            "height": local_height
        }
    }

@router.get("/status")
async def handshake_status(request: Request):
    """
    Get handshake status information.
    
    Returns information about handshake attempts, successes, and failures.
    
    Returns:
        Handshake status information
    """
    security_monitor = get_security_monitor()
    
    # Get handshake-related events from the security monitor
    events = await security_monitor.get_recent_events(100)
    handshake_events = [
        event for event in events 
        if event["event_type"] == SecurityEventType.HANDSHAKE_FAILURE.value
    ]
    
    # Calculate statistics
    total_handshakes = len(handshake_events)
    successful_handshakes = sum(
        1 for event in handshake_events
        if event["details"] and event["details"].get("action") == "handshake_successful"
    )
    failed_handshakes = total_handshakes - successful_handshakes
    
    # Group failures by reason
    failure_reasons = {}
    for event in handshake_events:
        if event["details"] and event["details"].get("reason"):
            reason = event["details"]["reason"]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
    
    return {
        "ok": True,
        "result": {
            "total_handshakes": total_handshakes,
            "successful_handshakes": successful_handshakes,
            "failed_handshakes": failed_handshakes,
            "failure_reasons": failure_reasons
        }
    }