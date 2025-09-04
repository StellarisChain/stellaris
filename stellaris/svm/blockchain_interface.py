"""
Blockchain Interface for Stellaris VM
Provides VM with access to blockchain state and data
"""

import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import time

from stellaris.database import Database
from stellaris.manager import Manager
from stellaris.utils.general import sha256
from stellaris.svm.vm import StellarisVM

if TYPE_CHECKING:
    from stellaris.transactions.smart_contract_transaction import SmartContractTransaction


class StellarisBlockchainInterface:
    """Interface between VM and blockchain for real-time data access"""
    
    def __init__(self, database: Database = None):
        self.database = database or Database.instance
        self.current_block_cache = None
        self.cache_timeout = 60  # Cache for 60 seconds
        self.last_cache_time = 0
        
    async def get_current_block_number(self) -> int:
        """Get the current block height"""
        try:
            if self.database:
                last_block = await self.database.get_last_block()
                return last_block.get('id', 1) if last_block else 1
            return 1
        except Exception:
            return 1
    
    async def get_current_block_timestamp(self) -> int:
        """Get the timestamp of the current block"""
        try:
            if self.database:
                last_block = await self.database.get_last_block()
                return last_block.get('timestamp', int(time.time())) if last_block else int(time.time())
            return int(time.time())
        except Exception:
            return int(time.time())
    
    def get_current_transaction_hash(self) -> str:
        """Get current transaction hash (set by execution context)"""
        # This will be set by the transaction processor during execution
        return getattr(self, '_current_tx_hash', f"tx_{int(time.time())}_{hash(str(time.time()))}")
    
    def set_current_transaction_hash(self, tx_hash: str):
        """Set the current transaction hash"""
        self._current_tx_hash = tx_hash
    
    async def get_block_by_number(self, block_number: int) -> Optional[Dict[str, Any]]:
        """Get block data by block number"""
        try:
            if self.database:
                return await self.database.get_block_by_id(block_number)
            return None
        except Exception:
            return None
    
    async def get_block_by_hash(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """Get block data by block hash"""
        try:
            if self.database:
                return await self.database.get_block_by_hash(block_hash)
            return None
        except Exception:
            return None
    
    async def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction data by hash"""
        try:
            if self.database:
                return await self.database.get_transaction(tx_hash)
            return None
        except Exception:
            return None
    
    async def get_account_balance(self, address: str) -> Decimal:
        """Get account balance from blockchain state"""
        try:
            if self.database:
                return await self.database.get_balance(address)
            return Decimal('0')
        except Exception:
            return Decimal('0')
    
    async def get_account_nonce(self, address: str) -> int:
        """Get account nonce (transaction count)"""
        try:
            if self.database:
                # Count transactions from this address
                return await self.database.get_transaction_count(address)
            return 0
        except Exception:
            return 0
    
    async def get_contract_storage(self, contract_address: str, key: str) -> Any:
        """Get contract storage from blockchain state"""
        try:
            if self.database:
                return await self.database.get_contract_storage(contract_address, key)
            return None
        except Exception:
            return None
    
    async def set_contract_storage(self, contract_address: str, key: str, value: Any):
        """Set contract storage in blockchain state"""
        try:
            if self.database:
                await self.database.set_contract_storage(contract_address, key, value)
        except Exception:
            pass
    
    async def get_contract_code(self, contract_address: str) -> Optional[str]:
        """Get contract code by address"""
        try:
            if self.database:
                return await self.database.get_contract_code(contract_address)
            return None
        except Exception:
            return None
    
    async def get_contract_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get complete contract information"""
        try:
            if self.database:
                return await self.database.get_contract_info(contract_address)
            return None
        except Exception:
            return None
    
    async def estimate_gas(self, transaction_data: Dict[str, Any]) -> int:
        """Estimate gas needed for a transaction"""
        # Basic gas estimation - can be made more sophisticated
        base_gas = StellarisVM.BASE_GAS
        
        if transaction_data.get('operation_type') == 1:  # Deploy
            code_length = len(transaction_data.get('contract_code', ''))
            return base_gas + (code_length * StellarisVM.GAS_COSTS['base_call'])
        else:  # Call
            return base_gas + StellarisVM.GAS_COSTS['base_call']
    
    async def get_gas_price(self) -> Decimal:
        """Get current gas price"""
        # Could be dynamic based on network congestion
        return StellarisVM.GAS_PRICE  # 1 microtoken per gas unit
    
    async def validate_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """Validate transaction against blockchain state"""
        try:
            # Basic validation checks
            sender = tx_data.get('sender')
            if not sender:
                return False
            
            # Check sender balance for fees
            balance = await self.get_account_balance(sender)
            estimated_gas = await self.estimate_gas(tx_data)
            gas_price = await self.get_gas_price()
            total_cost = estimated_gas * gas_price
            
            return balance >= total_cost
        except Exception:
            return False
    
    async def get_network_difficulty(self) -> Decimal:
        """Get current network difficulty"""
        try:
            difficulty, _ = await Manager.get_difficulty() if hasattr(Manager, 'get_difficulty') else (Decimal('1'), {})
            return difficulty
        except Exception:
            return Decimal('1')
    
    async def get_network_hashrate(self) -> Decimal:
        """Get current network hashrate"""
        try:
            # Could calculate from recent blocks
            return Decimal('1000000')  # Placeholder
        except Exception:
            return Decimal('1000000')
    
    async def broadcast_transaction(self, transaction: 'SmartContractTransaction'):
        """Broadcast transaction to network"""
        try:
            if self.database:
                # Add to pending transactions
                await self.database.add_pending_transaction(transaction.hex())
        except Exception:
            pass
    
    def get_cached_block(self) -> Optional[Dict[str, Any]]:
        """Get cached current block if still valid"""
        current_time = time.time()
        if (self.current_block_cache and 
            current_time - self.last_cache_time < self.cache_timeout):
            return self.current_block_cache
        return None
    
    async def refresh_block_cache(self):
        """Refresh the current block cache"""
        try:
            if self.database:
                self.current_block_cache = await self.database.get_last_block()
                self.last_cache_time = time.time()
        except Exception:
            pass
