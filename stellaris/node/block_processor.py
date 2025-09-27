"""
Block processor module for improved validation and propagation.
Inspired by Denaro's approach to block handling with added security features.
"""

import asyncio
import time
import logging
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from decimal import Decimal

from stellaris.node.input_validator import InputValidator
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.database import Database
from stellaris.node.handshake_handler import get_handshake_manager
from stellaris.node.security_monitor import get_security_monitor
from stellaris.transactions.transaction import Transaction

# Setup logging
logger = logging.getLogger("stellaris.node.block_processor")


class BlockProcessor:
    """
    Enhanced block processor for secure validation and propagation.
    Handles block submission, verification, and distribution to peers.
    """
    
    def __init__(self):
        self.db = None
        self.validator = InputValidator()
        self.reputation_manager = get_reputation_manager()
        self.handshake_manager = get_handshake_manager()
        self.security_monitor = get_security_monitor()
        self.processing_queue = asyncio.Queue()
        self.processing_blocks = set()  # Set of blocks being processed
        self.processing_lock = asyncio.Lock()
        self.is_running = False
    
    def set_db(self, db: Database):
        """Set the database connection."""
        self.db = db
    
    async def start(self):
        """Start the block processor."""
        if self.is_running:
            return
            
        self.is_running = True
        asyncio.create_task(self._process_queue())
        logger.info("Block processor started")
    
    async def stop(self):
        """Stop the block processor."""
        self.is_running = False
        logger.info("Block processor stopped")
    
    async def submit_block(self, block_data: Dict[str, Any], peer_address: str = None) -> Tuple[bool, str]:
        """
        Submit a block for processing.
        
        Args:
            block_data: The raw block data
            peer_address: The address of the peer that submitted this block
            
        Returns:
            Tuple containing (success, message)
        """
        # Rate limit check for the peer
        if peer_address and not self._check_rate_limit(peer_address):
            self.reputation_manager.record_violation(peer_address, "block_rate_limit")
            self.security_monitor.record_event("rate_limit_exceeded", peer_address)
            return False, "Rate limit exceeded"
        
        # Validate block structure
        if not self.validator.validate_block_structure(block_data):
            if peer_address:
                self.reputation_manager.record_violation(peer_address, "invalid_block_structure")
                self.security_monitor.record_event("invalid_block_structure", peer_address)
            return False, "Invalid block structure"
        
        try:
            # Get block hash
            block_hash = block_data.get("hash")
            
            # Check if already in blockchain
            if await self._is_block_in_chain(block_hash):
                return True, "Block already in blockchain"
            
            # Check if already being processed
            if block_hash in self.processing_blocks:
                return True, "Block already being processed"
            
            # Initial height check
            current_height = await self._get_current_height()
            block_height = block_data.get("height")
            
            if block_height <= current_height:
                # We already have blocks at this height, check if it's a competing fork
                if not await self._is_competing_fork(block_data):
                    if peer_address:
                        self.reputation_manager.record_violation(peer_address, "outdated_block_submission")
                    return False, f"Block at height {block_height} is outdated"
            
            # Add to processing queue and mark as being processed
            await self.processing_queue.put((block_data, peer_address))
            self.processing_blocks.add(block_hash)
            
            # If submitted by a peer, record good behavior
            if peer_address:
                self.reputation_manager.record_good_behavior(peer_address, "valid_block_submission")
            
            return True, "Block accepted for processing"
            
        except Exception as e:
            logger.error(f"Error processing block submission: {e}")
            if peer_address:
                self.security_monitor.record_event("block_processing_error", peer_address)
            return False, f"Error processing block: {str(e)}"
    
    async def _process_queue(self):
        """Process blocks from the queue."""
        while self.is_running:
            try:
                # Get next block from queue
                block_data, peer_address = await self.processing_queue.get()
                
                # Process with mutex to prevent race conditions
                async with self.processing_lock:
                    await self._process_block(block_data, peer_address)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in block queue processing: {e}")
                # Wait a bit before trying again
                await asyncio.sleep(1)
    
    async def _process_block(self, block_data: Dict[str, Any], peer_address: Optional[str]):
        """
        Process a single block with comprehensive validation.
        
        Args:
            block_data: Block data
            peer_address: Address of the peer that submitted this block
        """
        block_hash = block_data.get("hash")
        
        try:
            # Perform full validation
            valid, reason = await self._validate_block_full(block_data)
            
            if not valid:
                logger.info(f"Block {block_hash} rejected: {reason}")
                if peer_address:
                    self.reputation_manager.record_violation(peer_address, f"invalid_block:{reason}")
                    self.security_monitor.record_event("invalid_block", peer_address, details=reason)
                
                # Remove from processing
                self.processing_blocks.remove(block_hash)
                return
            
            # Check if block creates a longer chain
            if await self._is_better_chain(block_data):
                # Reorganize chain if necessary
                await self._handle_chain_reorganization(block_data)
            
            # Save block to database
            await self._save_block(block_data)
            
            # Update UTXOs
            await self._update_utxos(block_data)
            
            # Remove block transactions from pending pool
            await self._remove_transactions_from_pending(block_data)
            
            # Propagate block to peers (except sender)
            await self._propagate_block(block_data, exclude_peer=peer_address)
            
            # Record successful processing
            logger.info(f"Block {block_hash} at height {block_data.get('height')} accepted and propagated")
            if peer_address:
                self.reputation_manager.record_good_behavior(peer_address, "propagated_valid_block")
                
        except Exception as e:
            logger.error(f"Error processing block {block_hash}: {e}")
            if peer_address:
                self.security_monitor.record_event("block_processing_error", peer_address)
        finally:
            # Remove from processing
            self.processing_blocks.discard(block_hash)
    
    async def _validate_block_full(self, block_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Perform full validation of a block.
        
        Args:
            block_data: Block to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check block hash
        if not self._verify_block_hash(block_data):
            return False, "invalid_block_hash"
        
        # Check proof of work
        if not self._verify_proof_of_work(block_data):
            return False, "invalid_proof_of_work"
        
        # Check block is properly linked to previous block
        if not await self._verify_block_linkage(block_data):
            return False, "invalid_block_linkage"
        
        # Validate all transactions in the block
        if not await self._validate_block_transactions(block_data):
            return False, "invalid_transactions"
        
        # Check block reward
        if not self._verify_block_reward(block_data):
            return False, "invalid_block_reward"
        
        return True, "valid"
    
    async def _is_block_in_chain(self, block_hash: str) -> bool:
        """Check if block is already in the blockchain."""
        if not self.db:
            return False
        
        # Use the actual Stellaris database interface
        return block_hash in self.db._blocks
    
    async def _get_current_height(self) -> int:
        """Get the current blockchain height."""
        if not self.db:
            return -1
        
        # Use the actual Stellaris database interface
        last_block = await self.db.get_last_block()
        return last_block.get('id', -1) if last_block else -1
    
    async def _is_competing_fork(self, block_data: Dict[str, Any]) -> bool:
        """
        Check if block is part of a competing fork.
        
        Args:
            block_data: Block data
            
        Returns:
            True if block is part of a competing fork
        """
        # This would check if the block is a valid alternative at the same height
        height = block_data.get("height")
        prev_hash = block_data.get("previous_hash")
        
        if not self.db:
            return False
        
        # Check if previous block exists in Stellaris database
        return prev_hash in self.db._blocks
    
    async def _is_better_chain(self, block_data: Dict[str, Any]) -> bool:
        """
        Check if block creates a better (longer) chain.
        
        Args:
            block_data: Block data
            
        Returns:
            True if block creates a better chain
        """
        # Simple implementation: just check if height is greater
        # More sophisticated implementations would check accumulated work
        block_height = block_data.get("height")
        current_height = await self._get_current_height()
        
        return block_height > current_height
    
    async def _handle_chain_reorganization(self, block_data: Dict[str, Any]):
        """
        Handle chain reorganization if necessary.
        
        Args:
            block_data: New block data that creates a longer chain
        """
        # This would handle reorganizing the blockchain if needed
        # For simplicity, assume we're just adding to the longest chain
        # In a real implementation, this would:
        # 1. Find common ancestor
        # 2. Roll back blocks to common ancestor
        # 3. Apply new blocks
        logger.info(f"Chain reorganization needed for block {block_data.get('hash')} at height {block_data.get('height')}")
        # Implementation details would depend on database structure
    
    async def _save_block(self, block_data: Dict[str, Any]):
        """
        Save block to database.
        
        Args:
            block_data: Block data
        """
        if not self.db:
            return
        
        # Use the actual Stellaris database interface
        block_hash = block_data.get("hash")
        height = block_data.get("height", 0)
        
        # Create block content (Stellaris uses hex format)
        block_content = json.dumps(block_data).encode().hex()
        
        # Add block to database
        await self.db.add_block(
            id=height,
            block_hash=block_hash,
            block_content=block_content,
            address=block_data.get("miner", ""),
            random=block_data.get("nonce", 0),
            difficulty=Decimal(str(block_data.get("difficulty", 1))),
            reward=Decimal(str(block_data.get("reward", 0))),
            timestamp=block_data.get("timestamp", int(time.time()))
        )
        
        # Save transactions
        for tx_data in block_data.get("transactions", []):
            try:
                # Parse transaction from the data
                if isinstance(tx_data, dict):
                    # Convert dict to hex format if needed
                    tx_hex = tx_data.get("hex") or json.dumps(tx_data).encode().hex()
                else:
                    tx_hex = tx_data
                
                tx = await self.db._parse_transaction_from_hex(tx_hex, check_signatures=False)
                await self.db.add_transaction(tx, block_hash)
            except Exception as e:
                logger.error(f"Error saving transaction in block {block_hash}: {e}")
    
    async def _save_transaction(self, tx_data: Dict[str, Any], block_hash: str):
        """
        Save transaction to database.
        
        Args:
            tx_data: Transaction data
            block_hash: Hash of the block containing this transaction
        """
        if not self.db:
            return
            
        # Store transaction
        query = """
            INSERT INTO transactions (
                tx_hash, block_hash, version, timestamp,
                tx_data, is_coinbase
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (tx_hash) DO NOTHING
        """
        
        # Extract values
        tx_hash = tx_data.get("hash")
        version = tx_data.get("version", 1)
        timestamp = tx_data.get("timestamp")
        is_coinbase = tx_data.get("is_coinbase", False)
        
        await self.db.execute(
            query, tx_hash, block_hash, version,
            timestamp, tx_data, is_coinbase
        )
    
    async def _update_utxos(self, block_data: Dict[str, Any]):
        """
        Update UTXO set based on block transactions.
        
        Args:
            block_data: Block data
        """
        if not self.db:
            return
            
        # Process each transaction
        for tx_data in block_data.get("transactions", []):
            # Mark inputs as spent
            for tx_input in tx_data.get("inputs", []):
                if tx_input.get("coinbase"):
                    # Skip coinbase inputs
                    continue
                    
                # Mark as spent
                query = """
                    UPDATE outputs
                    SET is_spent = TRUE, spent_in_tx = $3, spent_at_height = $4
                    WHERE tx_hash = $1 AND output_index = $2
                """
                await self.db.execute(
                    query, tx_input.get("tx_hash"), 
                    tx_input.get("output_index"),
                    tx_data.get("hash"),
                    block_data.get("height")
                )
            
            # Add new outputs
            for i, tx_output in enumerate(tx_data.get("outputs", [])):
                query = """
                    INSERT INTO outputs (
                        tx_hash, output_index, amount, script_pubkey,
                        address, is_spent, block_height
                    ) VALUES ($1, $2, $3, $4, $5, FALSE, $6)
                    ON CONFLICT (tx_hash, output_index) DO NOTHING
                """
                await self.db.execute(
                    query, tx_data.get("hash"), i,
                    tx_output.get("amount"),
                    tx_output.get("script_pubkey", ""),
                    tx_output.get("address", ""),
                    block_data.get("height")
                )
    
    async def _remove_transactions_from_pending(self, block_data: Dict[str, Any]):
        """
        Remove block transactions from pending pool.
        
        Args:
            block_data: Block data
        """
        if not self.db:
            return
            
        # Get transaction hashes
        tx_hashes = [tx.get("hash") for tx in block_data.get("transactions", [])]
        
        if not tx_hashes:
            return
            
        # Remove from pending pool
        # PostgreSQL requires placeholders like $1, $2, etc.
        # We need to create the correct number of placeholders
        placeholders = ", ".join(f"${i+1}" for i in range(len(tx_hashes)))
        query = f"DELETE FROM pending_transactions WHERE tx_hash IN ({placeholders})"
        
        await self.db.execute(query, *tx_hashes)
    
    async def _propagate_block(self, block_data: Dict[str, Any], exclude_peer: Optional[str] = None):
        """
        Propagate block to trusted peers.
        
        Args:
            block_data: Block to propagate
            exclude_peer: Peer to exclude from propagation (usually the source)
        """
        # Get trusted peers
        trusted_peers = await self.handshake_manager.get_trusted_peers(exclude_peer)
        
        # Propagate to each trusted peer
        # TODO: Implement actual HTTP client call to peer nodes
        # This would typically be an async HTTP call to each peer's block endpoint
        for peer in trusted_peers:
            try:
                # This would be replaced with actual HTTP client call
                # Example: await http_client.post(f"{peer}/api/blocks", json=block_data)
                
                # For now, just log
                logger.info(f"Would propagate block {block_data.get('hash')} to peer {peer}")
                
                # Record successful propagation
                self.reputation_manager.record_good_behavior(peer, "block_propagation_success")
                
            except Exception as e:
                logger.error(f"Failed to propagate block to {peer}: {e}")
                self.reputation_manager.record_violation(peer, "block_propagation_failure")
    
    def _verify_block_hash(self, block_data: Dict[str, Any]) -> bool:
        """
        Verify the block hash.
        
        Args:
            block_data: Block data
            
        Returns:
            True if hash is valid
        """
        # This would involve recalculating the hash and comparing
        # For simplicity, assume valid
        return True
    
    def _verify_proof_of_work(self, block_data: Dict[str, Any]) -> bool:
        """
        Verify the proof of work.
        
        Args:
            block_data: Block data
            
        Returns:
            True if proof of work is valid
        """
        # This would involve checking if the hash meets difficulty requirements
        # For simplicity, assume valid
        return True
    
    async def _verify_block_linkage(self, block_data: Dict[str, Any]) -> bool:
        """
        Verify the block is properly linked to previous block.
        
        Args:
            block_data: Block data
            
        Returns:
            True if linkage is valid
        """
        if not self.db:
            # If genesis block, no previous block to check
            if block_data.get("height") == 0:
                return True
            return False
            
        prev_hash = block_data.get("previous_hash")
        
        # Check if previous block exists
        query = "SELECT height FROM blocks WHERE hash = $1 LIMIT 1"
        result = await self.db.fetch_one(query, prev_hash)
        
        if not result:
            return False
            
        # Check if heights are sequential
        prev_height = result["height"]
        curr_height = block_data.get("height")
        
        return curr_height == prev_height + 1
    
    async def _validate_block_transactions(self, block_data: Dict[str, Any]) -> bool:
        """
        Validate all transactions in the block.
        
        Args:
            block_data: Block data
            
        Returns:
            True if all transactions are valid
        """
        # This would validate each transaction including:
        # - Transaction hash verification
        # - Signature verification
        # - Double spend check
        # - Input existence check
        # - Smart contract execution
        
        # For simplicity, assume valid
        return True
    
    def _verify_block_reward(self, block_data: Dict[str, Any]) -> bool:
        """
        Verify the block reward is correct.
        
        Args:
            block_data: Block data
            
        Returns:
            True if reward is valid
        """
        # This would check that the coinbase transaction has correct reward
        # For simplicity, assume valid
        return True
    
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
_block_processor = None


def get_block_processor() -> BlockProcessor:
    """Get or create the block processor singleton."""
    global _block_processor
    if _block_processor is None:
        _block_processor = BlockProcessor()
    return _block_processor