import hashlib
import json
import time
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from lib.VoxaCommunications_Router.stellaris.typing.block_header import BlockHeader
from lib.VoxaCommunications_Router.stellaris.typing.transactions import Transaction
from lib.VoxaCommunications_Router.stellaris.typing.block_status import BlockStatus
from lib.VoxaCommunications_Router.stellaris.typing.block import Block
from util.logging import log

class Blockchain:
    """Stellaris blockchain implementation"""
    
    def __init__(self):
        self.logger = log()
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.utxo_set: Dict[str, Dict[str, Any]] = {}  # UTXO database
        self.difficulty_target = 4  # Number of leading zeros required
        self.block_reward = 50_000_000_000  # 50 STL in stellaris (smallest unit)
        self.min_confirmations = 6
        self.max_block_size = 1_000_000  # 1MB max block size
        
        # Create genesis block
        self._create_genesis_block()
    
    def _create_genesis_block(self) -> None:
        """Create the genesis block for the Stellaris blockchain"""
        genesis_transactions = []
        
        # Create genesis block header
        header = BlockHeader(
            index=0,
            previous_hash="0" * 64,
            merkle_root="0" * 64,
            timestamp=int(time.time()),
            difficulty=self.difficulty_target,
            nonce=0
        )
        
        # Create genesis block
        genesis_block = Block(
            header=header,
            transactions=genesis_transactions
        )
        
        # Mine the genesis block
        self.mine_block(genesis_block)
        
        # Add to chain
        self.chain.append(genesis_block)
        self.logger.info(f"Genesis block created: {genesis_block.hash}")
    
    def get_latest_block(self) -> Block:
        """Get the latest block in the chain"""
        return self.chain[-1] if self.chain else None
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a transaction to the pending transactions pool"""
        # Validate transaction
        if not self.validate_transaction(transaction):
            self.logger.warning(f"Invalid transaction rejected: {transaction.tx_id}")
            return False
        
        # Check for double spending
        if self.check_double_spending(transaction):
            self.logger.warning(f"Double spending detected: {transaction.tx_id}")
            return False
        
        self.pending_transactions.append(transaction)
        self.logger.info(f"Transaction added to pending pool: {transaction.tx_id}")
        return True
    
    def create_block(self, miner_address: str) -> Block:
        """Create a new block with pending transactions"""
        if not self.pending_transactions:
            return None
        
        # Select transactions for the block (prioritize by fee)
        selected_transactions = self.select_transactions_for_block()
        
        # Add coinbase transaction (mining reward)
        coinbase_tx = self.create_coinbase_transaction(miner_address)
        selected_transactions.insert(0, coinbase_tx)
        
        # Create block header
        latest_block = self.get_latest_block()
        header = BlockHeader(
            index=latest_block.header.index + 1,
            previous_hash=latest_block.hash,
            merkle_root="",  # Will be calculated in Block.__post_init__
            timestamp=int(time.time()),
            difficulty=self.difficulty_target,
            nonce=0
        )
        
        # Create block
        new_block = Block(header=header, transactions=selected_transactions)
        new_block.header.merkle_root = new_block.calculate_merkle_root()
        
        return new_block
    
    def mine_block(self, block: Block) -> bool:
        """Mine a block using proof of work"""
        target = "0" * self.difficulty_target
        
        while not block.hash.startswith(target):
            block.header.nonce += 1
            block.hash = block.calculate_hash()
        
        self.logger.info(f"Block mined: {block.hash} with nonce: {block.header.nonce}")
        return True
    
    def add_block(self, block: Block) -> bool:
        """Add a mined block to the blockchain"""
        # Validate block
        latest_block = self.get_latest_block()
        if not block.validate_block(latest_block):
            self.logger.warning(f"Invalid block rejected: {block.hash}")
            return False
        
        # Check proof of work
        # TODO: Hash should be recalcalated after mining
        target = "0" * self.difficulty_target
        if not block.hash.startswith(target):
            self.logger.warning(f"Block does not meet difficulty target: {block.hash}")
            return False
        
        # Add block to chain
        self.chain.append(block)
        block.status = BlockStatus.CONFIRMED
        
        # Update UTXO set
        self.update_utxo_set(block)
        
        # Remove processed transactions from pending pool
        processed_tx_ids = {tx.tx_id for tx in block.transactions}
        self.pending_transactions = [
            tx for tx in self.pending_transactions 
            if tx.tx_id not in processed_tx_ids
        ]
        
        # Update confirmations for previous blocks
        self.update_confirmations()
        
        self.logger.info(f"Block added to blockchain: {block.hash}")
        return True
    
    def select_transactions_for_block(self) -> List[Transaction]:
        """Select transactions for the next block, prioritizing by fee"""
        # Sort by fee per byte (descending)
        sorted_transactions = sorted(
            self.pending_transactions,
            key=lambda tx: tx.fee,
            reverse=True
        )
        
        selected = []
        total_size = 0
        
        for tx in sorted_transactions:
            tx_size = len(json.dumps(tx.to_dict()).encode())
            if total_size + tx_size <= self.max_block_size:
                selected.append(tx)
                total_size += tx_size
            else:
                break
        
        return selected
    
    def create_coinbase_transaction(self, miner_address: str) -> Transaction:
        """Create a coinbase transaction for mining reward"""
        # TODO: Fix this
        return Transaction(
            tx_id="",  # Will be calculated in __post_init__
            inputs=[],  # Coinbase has no inputs
            outputs=[{
                'address': miner_address,
                'amount': self.block_reward,
                'script_pub_key': f'OP_DUP OP_HASH160 {miner_address} OP_EQUALVERIFY OP_CHECKSIG'
            }],
            fee=0,
            timestamp=int(time.time()),
            signature="coinbase",
            public_key="coinbase"
        )
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate a transaction"""
        # Skip validation for coinbase transactions
        if transaction.public_key == "coinbase":
            return True
        
        # Basic validation
        if transaction.fee < 0:
            return False
        
        # Validate inputs and outputs
        input_sum = sum(inp.get('amount', 0) for inp in transaction.inputs)
        output_sum = sum(out.get('amount', 0) for out in transaction.outputs)
        
        if input_sum < output_sum + transaction.fee:
            return False
        
        # TODO: Implement full signature and UTXO validation
        
        return True
    
    def check_double_spending(self, transaction: Transaction) -> bool:
        """Check if transaction attempts to double spend"""
        # Check against pending transactions
        for pending_tx in self.pending_transactions:
            for tx_input in transaction.inputs:
                for pending_input in pending_tx.inputs:
                    if (tx_input.get('tx_id') == pending_input.get('tx_id') and
                        tx_input.get('output_index') == pending_input.get('output_index')):
                        return True
        
        return False
    
    def update_utxo_set(self, block: Block) -> None:
        """Update the UTXO set with new block transactions"""
        for tx in block.transactions:
            # Remove spent UTXOs
            for tx_input in tx.inputs:
                utxo_key = f"{tx_input.get('tx_id')}:{tx_input.get('output_index')}"
                if utxo_key in self.utxo_set:
                    del self.utxo_set[utxo_key]
            
            # Add new UTXOs
            for i, output in enumerate(tx.outputs):
                utxo_key = f"{tx.tx_id}:{i}"
                self.utxo_set[utxo_key] = {
                    'tx_id': tx.tx_id,
                    'output_index': i,
                    'address': output.get('address'),
                    'amount': output.get('amount'),
                    'script_pub_key': output.get('script_pub_key'),
                    'block_height': block.header.index
                }
    
    def update_confirmations(self) -> None:
        """Update confirmation count for all blocks"""
        chain_length = len(self.chain)
        for i, block in enumerate(self.chain):
            block.confirmations = chain_length - i - 1
    
    def get_balance(self, address: str) -> int:
        """Get the balance for a specific address"""
        balance = 0
        for utxo in self.utxo_set.values():
            if utxo['address'] == address:
                balance += utxo['amount']
        return balance
    
    def get_utxos_for_address(self, address: str) -> List[Dict[str, Any]]:
        """Get all UTXOs for a specific address"""
        return [utxo for utxo in self.utxo_set.values() if utxo['address'] == address]
    
    def is_valid(self) -> bool:
        """Validate the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            if not current_block.validate_block(previous_block):
                return False
        
        return True
    
    def get_difficulty_adjustment(self) -> int:
        """Calculate difficulty adjustment based on block time"""
        if len(self.chain) < 10:  # Not enough blocks for adjustment
            return self.difficulty_target
        
        # Calculate average block time for last 10 blocks
        recent_blocks = self.chain[-10:]
        time_diff = recent_blocks[-1].header.timestamp - recent_blocks[0].header.timestamp
        avg_block_time = time_diff / 9  # 9 intervals between 10 blocks
        
        target_block_time = 600  # 10 minutes
        
        if avg_block_time < target_block_time * 0.8:  # Too fast
            return self.difficulty_target + 1
        elif avg_block_time > target_block_time * 1.2:  # Too slow
            return max(1, self.difficulty_target - 1)
        
        return self.difficulty_target
