"""
Smart Contract Transaction Processor for Stellaris blockchain
Handles validation and execution of smart contract transactions during block processing
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import logging

from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
from stellaris.transactions import Transaction
from stellaris.svm.vm_manager import StellarisVMManager, ExecutionResult
from stellaris.svm.exceptions import SVMError, SVMGasError, SVMContractError
from stellaris.database import Database
from stellaris.utils.general import sha256


logger = logging.getLogger(__name__)


class SmartContractProcessor:
    """Processes smart contract transactions for block validation and execution"""
    
    def __init__(self, vm_manager: StellarisVMManager, database: Database):
        self.vm_manager = vm_manager
        self.database = database
        self.execution_cache: Dict[str, ExecutionResult] = {}
    
    async def validate_smart_contract_transaction(self, 
                                                transaction: SmartContractTransaction,
                                                sender: str,
                                                block_context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a smart contract transaction
        
        Args:
            transaction: Smart contract transaction to validate
            sender: Sender address
            block_context: Block context (number, timestamp, etc.)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation
            if transaction.gas_limit <= 0:
                return False, "Gas limit must be positive"
            
            if transaction.gas_limit > 10_000_000:  # 10M gas limit
                return False, "Gas limit too high"
            
            # Validate deployment transactions
            if transaction.is_deployment():
                if not transaction.contract_code:
                    return False, "Contract code cannot be empty"
                
                if len(transaction.contract_code) > 1_000_000:  # 1MB code limit
                    return False, "Contract code too large"
                
                # Check if contract already exists at deployment address
                deployment_address = transaction.get_contract_deployment_address()
                if await self.database.contract_exists(deployment_address):
                    return False, f"Contract already exists at address {deployment_address}"
            
            # Validate call transactions
            elif transaction.is_call():
                if not transaction.contract_address:
                    return False, "Contract address cannot be empty"
                
                if not transaction.method_name:
                    return False, "Method name cannot be empty"
                
                # Check if contract exists
                if not await self.database.contract_exists(transaction.contract_address):
                    return False, f"Contract not found at address {transaction.contract_address}"
            
            # Validate sender has sufficient funds for gas
            sender_balance = await self.database.get_balance(sender)
            gas_price = await self.vm_manager.blockchain_interface.get_gas_price()
            max_gas_cost = Decimal(str(transaction.gas_limit)) * gas_price
            
            if sender_balance < max_gas_cost:
                return False, f"Insufficient balance for gas: {sender_balance} < {max_gas_cost}"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error validating smart contract transaction: {e}")
            return False, str(e)
    
    async def execute_smart_contract_transaction(self,
                                               transaction: SmartContractTransaction,
                                               sender: str,
                                               block_context: Dict[str, Any]) -> ExecutionResult:
        """
        Execute a smart contract transaction
        
        Args:
            transaction: Smart contract transaction to execute
            sender: Sender address
            block_context: Block context (number, timestamp, etc.)
            
        Returns:
            ExecutionResult
        """
        tx_hash = sha256(transaction.hex())
        
        # Check execution cache
        if tx_hash in self.execution_cache:
            return self.execution_cache[tx_hash]
        
        try:
            # Set blockchain interface context
            self.vm_manager.blockchain_interface.set_current_transaction_hash(tx_hash)
            
            # Execute the transaction
            result = await self.vm_manager.execute_transaction(transaction, sender)
            
            # Cache the result
            self.execution_cache[tx_hash] = result
            
            # Update transaction with execution results
            transaction.gas_used = result.gas_used
            transaction.execution_result = result.result
            if not result.success:
                transaction.execution_error = result.error
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing smart contract transaction: {e}")
            result = ExecutionResult(
                success=False,
                error=str(e),
                gas_used=transaction.gas_limit  # Consume all gas on error
            )
            self.execution_cache[tx_hash] = result
            return result
    
    async def process_smart_contract_transactions_in_block(self,
                                                         transactions: List[Transaction],
                                                         block_context: Dict[str, Any]) -> List[ExecutionResult]:
        """
        Process all smart contract transactions in a block
        
        Args:
            transactions: List of all transactions in block
            block_context: Block context information
            
        Returns:
            List of ExecutionResults for smart contract transactions
        """
        results = []
        sc_transactions = []
        
        # Extract smart contract transactions
        for tx in transactions:
            if isinstance(tx, SmartContractTransaction):
                sc_transactions.append(tx)
        
        if not sc_transactions:
            return results
        
        logger.info(f"Processing {len(sc_transactions)} smart contract transactions in block")
        
        # Process transactions sequentially to maintain state consistency
        for sc_tx in sc_transactions:
            try:
                # Get sender from transaction inputs
                sender = sc_tx.inputs[0].get_address() if sc_tx.inputs else "0x0"
                
                # Validate transaction
                is_valid, error = await self.validate_smart_contract_transaction(
                    sc_tx, sender, block_context
                )
                
                if not is_valid:
                    result = ExecutionResult(
                        success=False,
                        error=f"Validation failed: {error}",
                        gas_used=0
                    )
                else:
                    # Execute transaction
                    result = await self.execute_smart_contract_transaction(
                        sc_tx, sender, block_context
                    )
                
                results.append(result)
                
                # Log execution
                if result.success:
                    logger.info(f"Smart contract transaction executed successfully: {sha256(sc_tx.hex())}")
                else:
                    logger.warning(f"Smart contract transaction failed: {result.error}")
                
            except Exception as e:
                logger.error(f"Error processing smart contract transaction: {e}")
                result = ExecutionResult(
                    success=False,
                    error=str(e),
                    gas_used=sc_tx.gas_limit
                )
                results.append(result)
        
        return results
    
    async def validate_block_smart_contracts(self,
                                           transactions: List[Transaction],
                                           block_context: Dict[str, Any]) -> bool:
        """
        Validate all smart contract transactions in a block
        
        Args:
            transactions: List of all transactions in block
            block_context: Block context information
            
        Returns:
            True if all smart contract transactions are valid
        """
        for tx in transactions:
            if isinstance(tx, SmartContractTransaction):
                sender = tx.inputs[0].get_address() if tx.inputs else "0x0"
                is_valid, error = await self.validate_smart_contract_transaction(
                    tx, sender, block_context
                )
                if not is_valid:
                    logger.error(f"Invalid smart contract transaction: {error}")
                    return False
        
        return True
    
    async def calculate_total_gas_used(self, transactions: List[Transaction]) -> int:
        """Calculate total gas used by smart contract transactions"""
        total_gas = 0
        for tx in transactions:
            if isinstance(tx, SmartContractTransaction):
                total_gas += getattr(tx, 'gas_used', 0)
        return total_gas
    
    async def get_block_gas_limit(self, block_number: int) -> int:
        """Get the gas limit for a block"""
        # Start with a base gas limit and potentially adjust based on network conditions
        base_gas_limit = 50_000_000  # 50M gas per block
        
        # Could implement dynamic gas limit adjustments here
        # based on network usage, block number, etc.
        
        return base_gas_limit
    
    def clear_execution_cache(self):
        """Clear the execution cache"""
        self.execution_cache.clear()
    
    async def revert_smart_contract_state_changes(self, transactions: List[Transaction]):
        """Revert state changes made by smart contract transactions (for block reorganization)"""
        # This would be used during chain reorganization
        # For now, we rely on the database transaction rollback capabilities
        logger.warning("Smart contract state reversion not fully implemented")
        pass
