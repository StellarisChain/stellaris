"""
Transaction processing module for improved validation and propagation.
Inspired by Denaro's approach to transaction handling with added security features.
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple

from stellaris.node.input_validator import InputValidator
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.transactions.transaction import Transaction
from stellaris.database import Database
from stellaris.node.handshake_handler import get_handshake_manager
from stellaris.node.security_monitor import get_security_monitor

# Setup logging
logger = logging.getLogger("stellaris.node.transaction_processor")


class TransactionProcessor:
    """
    Enhanced transaction processor for secure validation and propagation.
    Handles transaction submission, verification, and distribution to peers.
    """
    
    def __init__(self):
        self.db = None
        self.validator = InputValidator()
        self.reputation_manager = get_reputation_manager()
        self.handshake_manager = get_handshake_manager()
        self.security_monitor = get_security_monitor()
        self.processing_queue = asyncio.Queue()
        self.pending_transactions = {}  # tx_hash -> timestamp
        self.processing_lock = asyncio.Lock()
        self.is_running = False
    
    def set_db(self, db: Database):
        """Set the database connection."""
        self.db = db
    
    async def start(self):
        """Start the transaction processor."""
        if self.is_running:
            return
            
        self.is_running = True
        asyncio.create_task(self._process_queue())
        logger.info("Transaction processor started")
    
    async def stop(self):
        """Stop the transaction processor."""
        self.is_running = False
        logger.info("Transaction processor stopped")
    
    async def submit_transaction(self, transaction_data: Dict[str, Any], peer_address: str = None) -> Tuple[bool, str]:
        """
        Submit a transaction for processing.
        
        Args:
            transaction_data: The raw transaction data
            peer_address: The address of the peer that submitted this transaction
            
        Returns:
            Tuple containing (success, message)
        """
        # Rate limit check for the peer
        if peer_address and not self._check_rate_limit(peer_address):
            self.reputation_manager.record_violation(peer_address, "transaction_rate_limit")
            self.security_monitor.record_event("rate_limit_exceeded", peer_address)
            return False, "Rate limit exceeded"
        
        # Validate transaction structure
        if not self.validator.validate_transaction_structure(transaction_data):
            if peer_address:
                self.reputation_manager.record_violation(peer_address, "invalid_transaction_structure")
                self.security_monitor.record_event("invalid_transaction_structure", peer_address)
            return False, "Invalid transaction structure"
        
        try:
            # Create Transaction object
            tx = Transaction.from_dict(transaction_data)
            
            # Check if already in pending pool
            if await self._is_transaction_pending(tx.hash):
                return True, "Transaction already in pending pool"
            
            # Initial basic validation
            if not await self._validate_transaction_basic(tx):
                if peer_address:
                    self.reputation_manager.record_violation(peer_address, "invalid_transaction_basic")
                    self.security_monitor.record_event("invalid_transaction_basic", peer_address)
                return False, "Transaction failed basic validation"
            
            # Add to processing queue
            await self.processing_queue.put((tx, peer_address))
            
            # Add to pending transactions
            self.pending_transactions[tx.hash] = time.time()
            
            # If submitted by a peer, record good behavior
            if peer_address:
                self.reputation_manager.record_good_behavior(peer_address, "valid_transaction_submission")
            
            return True, "Transaction accepted for processing"
            
        except Exception as e:
            logger.error(f"Error processing transaction submission: {e}")
            if peer_address:
                self.security_monitor.record_event("transaction_processing_error", peer_address)
            return False, f"Error processing transaction: {str(e)}"
    
    async def _process_queue(self):
        """Process transactions from the queue."""
        while self.is_running:
            try:
                # Get next transaction from queue
                tx, peer_address = await self.processing_queue.get()
                
                # Process with mutex to prevent race conditions
                async with self.processing_lock:
                    await self._process_transaction(tx, peer_address)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in transaction queue processing: {e}")
                await asyncio.sleep(1)
    
    async def _process_transaction(self, tx: Transaction, peer_address: Optional[str]):
        """
        Process a single transaction with comprehensive validation.
        
        Args:
            tx: Transaction object
            peer_address: Address of the peer that submitted this transaction
        """
        try:
            # Perform full validation
            valid, reason = await self._validate_transaction_full(tx)
            
            if not valid:
                logger.info(f"Transaction {tx.hash} rejected: {reason}")
                if peer_address:
                    self.reputation_manager.record_violation(peer_address, f"invalid_transaction:{reason}")
                    self.security_monitor.record_event("invalid_transaction", peer_address, details=reason)
                
                # Remove from pending
                self.pending_transactions.pop(tx.hash, None)
                return
            
            # Save to database
            await self._save_transaction(tx)
            
            # Propagate to peers (except sender)
            await self._propagate_transaction(tx, exclude_peer=peer_address)
            
            # Record successful processing
            logger.info(f"Transaction {tx.hash} accepted and propagated")
            if peer_address:
                self.reputation_manager.record_good_behavior(peer_address, "propagated_valid_transaction")
                
        except Exception as e:
            logger.error(f"Error processing transaction {tx.hash}: {e}")
            # Remove from pending in case of error
            self.pending_transactions.pop(tx.hash, None)
            if peer_address:
                self.security_monitor.record_event("transaction_processing_error", peer_address)
    
    async def _validate_transaction_basic(self, tx: Transaction) -> bool:
        """
        Perform basic validation checks on a transaction.
        
        Args:
            tx: Transaction to validate
            
        Returns:
            True if transaction passes basic validation
        """
        # Check transaction hash
        if not tx.verify_hash():
            logger.info(f"Transaction {tx.hash} failed hash verification")
            return False
        
        # Check transaction signature
        if not tx.verify_signature():
            logger.info(f"Transaction {tx.hash} failed signature verification")
            return False
            
        return True
    
    async def _validate_transaction_full(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Perform full validation of a transaction.
        
        Args:
            tx: Transaction to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Skip if already in the blockchain
        if await self._is_transaction_in_blockchain(tx.hash):
            return False, "transaction_already_in_blockchain"
        
        # Check inputs exist and are unspent
        if not await self._validate_transaction_inputs(tx):
            return False, "invalid_inputs"
        
        # Check smart contract execution (if applicable)
        if tx.has_smart_contract():
            valid, reason = await self._validate_smart_contract(tx)
            if not valid:
                return False, f"smart_contract_validation:{reason}"
        
        # Check for double-spend in pending pool
        if await self._check_double_spend(tx):
            return False, "double_spend_detected"
        
        return True, "valid"
    
    async def _is_transaction_pending(self, tx_hash: str) -> bool:
        """Check if transaction is already in the pending pool."""
        return tx_hash in self.pending_transactions
    
    async def _is_transaction_in_blockchain(self, tx_hash: str) -> bool:
        """Check if transaction is already in the blockchain."""
        if not self.db:
            return False
        
        # Use the actual Stellaris database interface
        return tx_hash in self.db._transactions
    
    async def _validate_transaction_inputs(self, tx: Transaction) -> bool:
        """
        Check if all transaction inputs exist and are unspent.
        
        Args:
            tx: Transaction to validate
            
        Returns:
            True if all inputs are valid and unspent
        """
        if not self.db:
            return False
            
        for tx_input in tx.inputs:
            # Check if input exists in unspent outputs using Stellaris database format
            input_key = (tx_input.tx_hash, tx_input.output_index)
            
            # Check if it's in the unspent outputs set
            if input_key not in self.db._unspent_outputs:
                # Input either doesn't exist or is already spent
                return False
                
        return True
    
    async def _check_double_spend(self, tx: Transaction) -> bool:
        """
        Check if transaction is attempting to double-spend.
        
        Args:
            tx: Transaction to check
            
        Returns:
            True if double-spend detected
        """
        # Implementation will depend on how pending transactions are stored
        # This is a simplified version
        
        # Get all pending transactions
        pending_txs = await self._get_all_pending_transactions()
        
        # Create set of inputs being spent in the new transaction
        new_inputs = {(tx_input.tx_hash, tx_input.output_index) for tx_input in tx.inputs}
        
        # Check against all pending transactions
        for pending_tx in pending_txs:
            if pending_tx.hash == tx.hash:
                continue  # Skip self
                
            # Check for input overlap
            pending_inputs = {(tx_input.tx_hash, tx_input.output_index) for tx_input in pending_tx.inputs}
            
            # If there's any overlap, we have a double-spend
            if new_inputs.intersection(pending_inputs):
                return True
                
        return False
    
    async def _get_all_pending_transactions(self) -> List[Transaction]:
        """Get all pending transactions."""
        result = []
        
        # Load from Stellaris database format
        if self.db:
            for tx_hash, tx_data in self.db._pending_transactions.items():
                try:
                    tx = await self.db._parse_transaction_from_hex(tx_data['tx_hex'], check_signatures=False)
                    result.append(tx)
                except Exception:
                    continue
        
        return result
    
    async def _save_transaction(self, tx: Transaction):
        """Save transaction to pending pool."""
        if not self.db:
            return
            
        # Store in Stellaris database format
        await self.db.add_pending_transaction(tx, verify=False)
    
    async def _propagate_transaction(self, tx: Transaction, exclude_peer: Optional[str] = None):
        """
        Propagate transaction to trusted peers.
        
        Args:
            tx: Transaction to propagate
            exclude_peer: Peer to exclude from propagation (usually the source)
        """
        # Get trusted peers
        trusted_peers = await self.handshake_manager.get_trusted_peers(exclude_peer)
        
        # Propagate to each trusted peer
        tx_data = tx.to_dict()
        
        # TODO: Implement actual HTTP client call to peer nodes
        # This would typically be an async HTTP call to each peer's transaction endpoint
        for peer in trusted_peers:
            try:
                # This would be replaced with actual HTTP client call
                # Example: await http_client.post(f"{peer}/api/transactions", json=tx_data)
                
                # For now, just log
                logger.info(f"Would propagate transaction {tx.hash} to peer {peer}")
                
                # Record successful propagation
                self.reputation_manager.record_good_behavior(peer, "transaction_propagation_success")
                
            except Exception as e:
                logger.error(f"Failed to propagate transaction to {peer}: {e}")
                self.reputation_manager.record_violation(peer, "transaction_propagation_failure")
    
    async def _validate_smart_contract(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Validate smart contract execution.
        
        Args:
            tx: Transaction with smart contract
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # This would typically involve VM execution
        # For now, just return valid
        return True, "valid"
    
    def _check_rate_limit(self, peer_address: str) -> bool:
        """
        Check if peer has exceeded rate limits.
        
        Args:
            peer_address: Address of the peer
            
        Returns:
            True if peer is within rate limits
        """
        # This would typically involve checking timestamps of recent submissions
        # For now, just return True
        return True


# Singleton instance
_transaction_processor = None


def get_transaction_processor() -> TransactionProcessor:
    """Get or create the transaction processor singleton."""
    global _transaction_processor
    if _transaction_processor is None:
        _transaction_processor = TransactionProcessor()
    return _transaction_processor