"""
Blockchain interface for Stellaris VM to provide real blockchain context
"""

import time
from typing import Optional
from decimal import Decimal

class BlockchainInterface:
    """
    Interface between Stellaris VM and blockchain data
    This would typically connect to the actual blockchain node
    """
    
    def __init__(self, current_block_number: int = 1, current_block_timestamp: Optional[int] = None):
        self.current_block_number = current_block_number
        self.current_block_timestamp = current_block_timestamp or int(time.time())
        self.current_transaction_hash = None
        self.block_gas_limit = 8000000
        self.base_fee = Decimal('0.0001')
    
    def get_current_block_number(self) -> int:
        """Get the current block number"""
        return self.current_block_number
    
    def get_current_block_timestamp(self) -> int:
        """Get the current block timestamp"""
        return self.current_block_timestamp
    
    def get_current_transaction_hash(self) -> str:
        """Get the current transaction hash"""
        return self.current_transaction_hash or f"tx_{self.current_block_number}_{int(time.time())}"
    
    def get_block_gas_limit(self) -> int:
        """Get the current block gas limit"""
        return self.block_gas_limit
    
    def get_base_fee(self) -> Decimal:
        """Get the current base fee"""
        return self.base_fee
    
    def set_transaction_context(self, tx_hash: str, block_number: Optional[int] = None, timestamp: Optional[int] = None):
        """Set the current transaction context"""
        self.current_transaction_hash = tx_hash
        if block_number:
            self.current_block_number = block_number
        if timestamp:
            self.current_block_timestamp = timestamp
    
    def advance_block(self, timestamp: Optional[int] = None):
        """Advance to the next block"""
        self.current_block_number += 1
        self.current_block_timestamp = timestamp or int(time.time())
        self.current_transaction_hash = None
    
    def get_balance(self, address: str) -> Decimal:
        """Get balance of an address (would connect to blockchain state)"""
        # This is a mock implementation
        return Decimal('1000.0')
    
    def transfer(self, from_addr: str, to_addr: str, amount: Decimal) -> bool:
        """Transfer native tokens (would submit to blockchain)"""
        # This is a mock implementation
        return True
