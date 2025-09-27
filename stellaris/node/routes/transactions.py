"""
API routes for transaction submission and querying.
"""

import time
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import logging

from stellaris.node.transaction_processor import get_transaction_processor
from stellaris.node.input_validator import InputValidator
from stellaris.node.security_monitor import get_security_monitor
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.handshake_handler import get_handshake_manager, verify_handshake

# Setup logging
logger = logging.getLogger("stellaris.node.routes.transactions")

# Create router
router = APIRouter(tags=["transactions"])


class TransactionSubmission(BaseModel):
    """Transaction submission model."""
    transaction: Dict[str, Any]
    handshake_token: str


class TransactionResponse(BaseModel):
    """Transaction response model."""
    success: bool
    message: str
    tx_hash: str = None


class PendingTransactionsResponse(BaseModel):
    """Pending transactions response model."""
    transactions: List[Dict[str, Any]]
    count: int


@router.post("/transactions", response_model=TransactionResponse)
async def submit_transaction(
    submission: TransactionSubmission,
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Submit a transaction to the network.
    
    This endpoint performs:
    1. Handshake verification
    2. Input validation
    3. Transaction processing
    4. Reputation tracking
    """
    # Get the transaction processor
    processor = get_transaction_processor()
    
    # Verify handshake
    if not handshake_verified:
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_handshake", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_handshake")
        
        raise HTTPException(status_code=403, detail="Invalid handshake token")
    
    # Validate transaction structure
    validator = InputValidator()
    if not validator.validate_transaction_structure(submission.transaction):
        # Record security event
        security_monitor = get_security_monitor()
        security_monitor.record_event("invalid_transaction_structure", request.client.host)
        
        # Record violation for the peer
        reputation_manager = get_reputation_manager()
        reputation_manager.record_violation(request.client.host, "invalid_transaction_structure")
        
        raise HTTPException(status_code=400, detail="Invalid transaction structure")
    
    # Process transaction
    try:
        success, message = await processor.submit_transaction(
            submission.transaction,
            peer_address=request.client.host
        )
        
        # Create response
        response = TransactionResponse(
            success=success,
            message=message,
            tx_hash=submission.transaction.get("hash", None) if success else None
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing transaction: {str(e)}")


@router.get("/transactions/pending", response_model=PendingTransactionsResponse)
async def get_pending_transactions(
    request: Request,
    handshake_verified: bool = Depends(verify_handshake),
    limit: int = 100,
    offset: int = 0
):
    """
    Get pending transactions from the pool.
    
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
    
    # Validate limit and offset
    validator = InputValidator()
    if not validator.validate_integer_range(limit, 1, 1000) or not validator.validate_integer_range(offset, 0, 10000):
        raise HTTPException(status_code=400, detail="Invalid limit or offset")
    
    # Get processor and database
    processor = get_transaction_processor()
    
    if not processor.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Query pending transactions using Stellaris database format
    try:
        # Get pending transactions from the actual database structure
        pending_txs = []
        count = 0
        
        if processor.db:
            # Get all pending transactions
            for tx_hash, tx_data in processor.db._pending_transactions.items():
                count += 1
                if len(pending_txs) < limit and count > offset:
                    pending_txs.append(tx_data.get('tx_hex', ''))
        
        # Format response
        transactions = []
        for tx_hex in pending_txs:
            try:
                tx = await processor.db._parse_transaction_from_hex(tx_hex, check_signatures=False)
                # Convert to dict format
                tx_dict = {
                    'hash': tx.hash,
                    'inputs': [{'tx_hash': inp.tx_hash, 'output_index': inp.output_index} for inp in tx.inputs],
                    'outputs': [{'address': out.address, 'amount': str(out.amount)} for out in tx.outputs],
                    'timestamp': getattr(tx, 'timestamp', int(time.time())),
                    'hex': tx_hex
                }
                transactions.append(tx_dict)
            except Exception:
                continue
        
        return PendingTransactionsResponse(
            transactions=transactions,
            count=count
        )
        
    except Exception as e:
        logger.error(f"Error fetching pending transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching pending transactions: {str(e)}")


@router.get("/transactions/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    request: Request,
    handshake_verified: bool = Depends(verify_handshake)
):
    """
    Get a specific transaction by hash.
    
    This endpoint performs:
    1. Handshake verification
    2. Hash validation
    3. Database query for transaction
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
    if not validator.validate_hash(tx_hash):
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")
    
    # Get processor and database
    processor = get_transaction_processor()
    
    if not processor.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Look for transaction in Stellaris database format
    try:
        # Check pending transactions first
        if tx_hash in processor.db._pending_transactions:
            tx_data = processor.db._pending_transactions[tx_hash]
            tx = await processor.db._parse_transaction_from_hex(tx_data['tx_hex'], check_signatures=False)
            
            # Return from pending pool
            return {
                "transaction": {
                    'hash': tx.hash,
                    'inputs': [{'tx_hash': inp.tx_hash, 'output_index': inp.output_index} for inp in tx.inputs],
                    'outputs': [{'address': out.address, 'amount': str(out.amount)} for out in tx.outputs],
                    'timestamp': getattr(tx, 'timestamp', int(time.time())),
                    'hex': tx_data['tx_hex']
                },
                "status": "pending",
                "block_hash": None,
                "block_height": None
            }
        
        # Check blockchain transactions
        if tx_hash in processor.db._transactions:
            tx_data = processor.db._transactions[tx_hash]
            block_hash = tx_data.get('block_hash')
            
            # Get block info
            block_data = processor.db._blocks.get(block_hash, {})
            
            tx = await processor.db._parse_transaction_from_hex(tx_data['tx_hex'], check_signatures=False)
            
            # Return from blockchain
            return {
                "transaction": {
                    'hash': tx.hash,
                    'inputs': [{'tx_hash': inp.tx_hash, 'output_index': inp.output_index} for inp in tx.inputs],
                    'outputs': [{'address': out.address, 'amount': str(out.amount)} for out in tx.outputs],
                    'timestamp': getattr(tx, 'timestamp', int(time.time())),
                    'hex': tx_data['tx_hex']
                },
                "status": "confirmed",
                "block_hash": block_hash,
                "block_height": block_data.get('id')
            }
        
        # Transaction not found
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching transaction: {str(e)}")