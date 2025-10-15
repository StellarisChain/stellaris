"""
Stellaris VM Manager for blockchain integration and scaling
Handles VM instances, state management, and execution coordination
Uses RestrictedPython for secure contract execution

Production-ready features:
- VM pooling for efficient resource utilization
- Hex-encoded contract code handling
- Comprehensive input validation
- Security monitoring and logging
- Gas tracking and limits
- State caching with TTL
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from dataclasses import dataclass
import hashlib
import json
import logging

# Use RestrictedPython-based VM for security
from stellaris.svm.restricted_vm import RestrictedStellarisVM as StellarisVM, ContractState, ExecutionContext
from stellaris.svm.blockchain_interface import StellarisBlockchainInterface
from stellaris.svm.exceptions import SVMError, SVMGasError, SVMContractError, SVMValidationError
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
from stellaris.database import Database


logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of contract execution"""
    success: bool
    result: Any = None
    gas_used: int = 0
    error: Optional[str] = None
    logs: List[str] = None
    state_changes: Dict[str, Any] = None


@dataclass
class VMPoolStats:
    """Statistics for VM pool"""
    total_vms: int = 0
    active_vms: int = 0
    pending_executions: int = 0
    total_executions: int = 0
    avg_execution_time: float = 0.0
    total_gas_used: int = 0


class StellarisVMManager:
    """
    Manager for Stellaris VM instances with scaling and integration capabilities
    """
    
    def __init__(self, database: Database = None, max_workers: int = 4, 
                 vm_pool_size: int = 8, enable_caching: bool = True):
        """
        Initialize VM Manager
        
        Args:
            database: Database instance for persistence
            max_workers: Maximum number of worker threads
            vm_pool_size: Number of VM instances in pool
            enable_caching: Enable state caching for performance
        """
        self.database = database or Database.instance
        self.blockchain_interface = StellarisBlockchainInterface(database)
        self.max_workers = max_workers
        self.vm_pool_size = vm_pool_size
        self.enable_caching = enable_caching
        
        # VM Pool and execution management
        self.vm_pool: List[StellarisVM] = []
        self.vm_pool_lock = asyncio.Lock()
        self.execution_queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # State management
        self.contract_states: Dict[str, ContractState] = {}
        self.state_cache: Dict[str, Tuple[Any, float]] = {}  # (value, timestamp)
        self.cache_ttl = 300  # 5 minutes
        
        # Statistics and monitoring
        self.stats = VMPoolStats()
        self.execution_times: List[float] = []
        self.active_executions: Dict[str, float] = {}  # tx_hash -> start_time
        
        # Initialize VM pool
        self._initialize_vm_pool()
    
    def _initialize_vm_pool(self):
        """Initialize the VM pool with pre-warmed instances"""
        for i in range(self.vm_pool_size):
            vm = StellarisVM(blockchain_interface=self.blockchain_interface)
            self.vm_pool.append(vm)
        
        self.stats.total_vms = len(self.vm_pool)
        logger.info(f"Initialized VM pool with {self.vm_pool_size} instances")
    
    async def get_vm_instance(self) -> StellarisVM:
        """Get an available VM instance from the pool"""
        async with self.vm_pool_lock:
            if self.vm_pool:
                vm = self.vm_pool.pop(0)
                self.stats.active_vms += 1
                return vm
            else:
                # Create new VM if pool is empty
                vm = StellarisVM(blockchain_interface=self.blockchain_interface)
                self.stats.active_vms += 1
                self.stats.total_vms += 1
                return vm
    
    async def return_vm_instance(self, vm: StellarisVM):
        """Return VM instance to the pool"""
        async with self.vm_pool_lock:
            # Reset VM state for reuse
            vm.execution_context = None
            vm.call_stack.clear()
            vm.loop_counters.clear()
            
            # Return to pool if under limit
            if len(self.vm_pool) < self.vm_pool_size:
                self.vm_pool.append(vm)
            
            self.stats.active_vms = max(0, self.stats.active_vms - 1)
    
    def _validate_contract_code(self, code_hex: str) -> Tuple[bool, str]:
        """
        Validate hex-encoded contract code
        
        Args:
            code_hex: Hex-encoded contract source code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code_hex:
            return False, "Contract code cannot be empty"
        
        if not isinstance(code_hex, str):
            return False, "Contract code must be a string"
        
        # Validate hex format
        if len(code_hex) % 2 != 0:
            return False, "Contract code hex must have even length"
        
        try:
            code_bytes = bytes.fromhex(code_hex)
        except ValueError:
            return False, "Contract code must be valid hexadecimal"
        
        # Validate size
        if len(code_bytes) > SmartContractTransaction.MAX_CONTRACT_CODE_SIZE:
            return False, f"Contract code too large: {len(code_bytes)} bytes (max: {SmartContractTransaction.MAX_CONTRACT_CODE_SIZE})"
        
        if len(code_bytes) < 10:
            return False, "Contract code too small to be valid"
        
        # Decode and validate as UTF-8
        try:
            code_str = code_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return False, "Contract code must be valid UTF-8 when decoded"
        
        # Basic Python syntax validation
        if 'class' not in code_str and 'def' not in code_str:
            return False, "Contract code must contain at least one class or function definition"
        
        return True, ""
    
    def _validate_contract_address(self, address: str) -> Tuple[bool, str]:
        """
        Validate contract address format
        
        Args:
            address: Contract address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not address:
            return False, "Contract address cannot be empty"
        
        if not isinstance(address, str):
            return False, "Contract address must be a string"
        
        # Remove 0x prefix if present
        clean_address = address[2:] if address.startswith('0x') else address
        
        if len(clean_address) != 40:
            return False, f"Contract address must be 40 hex characters, got {len(clean_address)}"
        
        try:
            int(clean_address, 16)
        except ValueError:
            return False, "Contract address must be valid hexadecimal"
        
        return True, ""
    
    def _validate_method_args(self, args: List[Any]) -> Tuple[bool, str]:
        """
        Validate method arguments
        
        Args:
            args: List of method arguments
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(args, list):
            return False, "Method arguments must be a list"
        
        # Validate JSON serializability
        try:
            json.dumps(args, default=lambda x: str(x) if isinstance(x, Decimal) else None)
        except (TypeError, ValueError) as e:
            return False, f"Method arguments must be JSON-serializable: {e}"
        
        # Limit argument count to prevent abuse
        if len(args) > 100:
            return False, f"Too many arguments: {len(args)} (max: 100)"
        
        return True, ""
    
    async def deploy_contract(self, transaction: SmartContractTransaction, 
                            sender: str) -> ExecutionResult:
        """
        Deploy a smart contract with comprehensive validation
        
        Args:
            transaction: Smart contract deployment transaction (with hex-encoded code)
            sender: Address of the deployer
            
        Returns:
            ExecutionResult with deployment status and contract address
            
        Raises:
            SVMValidationError: If validation fails
        """
        start_time = time.time()
        
        # Validate sender address
        if not sender or not isinstance(sender, str):
            return ExecutionResult(
                success=False,
                error="Invalid sender address",
                gas_used=0
            )
        
        # Validate hex-encoded contract code
        is_valid, error_msg = self._validate_contract_code(transaction.contract_code)
        if not is_valid:
            logger.error(f"Contract code validation failed: {error_msg}")
            return ExecutionResult(
                success=False,
                error=f"Invalid contract code: {error_msg}",
                gas_used=0
            )
        
        # Validate constructor arguments
        is_valid, error_msg = self._validate_method_args(transaction.method_args)
        if not is_valid:
            logger.error(f"Constructor arguments validation failed: {error_msg}")
            return ExecutionResult(
                success=False,
                error=f"Invalid constructor arguments: {error_msg}",
                gas_used=0
            )
        
        # Validate gas limit
        if transaction.gas_limit < SmartContractTransaction.MIN_GAS_LIMIT:
            return ExecutionResult(
                success=False,
                error=f"Gas limit too low: {transaction.gas_limit} (min: {SmartContractTransaction.MIN_GAS_LIMIT})",
                gas_used=0
            )
        
        if transaction.gas_limit > SmartContractTransaction.MAX_GAS_LIMIT_DEPLOY:
            return ExecutionResult(
                success=False,
                error=f"Gas limit too high: {transaction.gas_limit} (max: {SmartContractTransaction.MAX_GAS_LIMIT_DEPLOY})",
                gas_used=0
            )
        
        execution_id = hashlib.sha256(
            f"{sender}{time.time()}{transaction.contract_code}".encode()
        ).hexdigest()[:16]
        
        self.active_executions[execution_id] = start_time
        
        try:
            vm = await self.get_vm_instance()
            
            # Set current transaction hash for blockchain interface
            tx_hash = hashlib.sha256(transaction.hex().encode()).hexdigest()
            self.blockchain_interface.set_current_transaction_hash(tx_hash)
            
            # Decode hex-encoded contract code
            try:
                code_bytes = bytes.fromhex(transaction.contract_code)
                code_str = code_bytes.decode('utf-8')
            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"Failed to decode contract code: {e}")
                return ExecutionResult(
                    success=False,
                    error=f"Contract code decoding failed: {e}",
                    gas_used=0
                )
            
            logger.info(f"Deploying contract for {sender}, code size: {len(code_bytes)} bytes, gas_limit: {transaction.gas_limit}")
            
            # Deploy contract with decoded code
            contract_address = vm.deploy_contract(
                code=code_str,  # Pass decoded code to VM
                constructor_args=transaction.method_args,
                deployer=sender,
                gas_limit=transaction.gas_limit
            )
            
            # Update transaction with results
            transaction.contract_address = contract_address
            transaction.gas_used = vm.execution_context.gas_used if vm.execution_context else 0
            transaction.execution_result = contract_address
            
            logger.info(f"Contract deployed successfully at {contract_address}, gas used: {transaction.gas_used}")
            
            # Persist contract state
            await self._persist_contract_state(contract_address, vm.contracts[contract_address])
            
            # Record execution stats
            execution_time = time.time() - start_time
            self._record_execution_stats(execution_time, transaction.gas_used)
            
            return ExecutionResult(
                success=True,
                result=contract_address,
                gas_used=transaction.gas_used,
                state_changes={'deployed_contract': contract_address}
            )
            
        except Exception as e:
            logger.error(f"Contract deployment failed: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                error=str(e),
                gas_used=getattr(transaction, 'gas_used', 0)
            )
        
        finally:
            if 'vm' in locals():
                await self.return_vm_instance(vm)
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
    
    async def call_contract(self, transaction: SmartContractTransaction,
                          sender: str) -> ExecutionResult:
        """
        Call a smart contract method with comprehensive validation
        
        Args:
            transaction: Smart contract call transaction
            sender: Address of the caller
            
        Returns:
            ExecutionResult with call results and return value
            
        Raises:
            SVMValidationError: If validation fails
        """
        start_time = time.time()
        
        # Validate sender address
        if not sender or not isinstance(sender, str):
            return ExecutionResult(
                success=False,
                error="Invalid sender address",
                gas_used=0
            )
        
        # Validate contract address
        is_valid, error_msg = self._validate_contract_address(transaction.contract_address)
        if not is_valid:
            logger.error(f"Contract address validation failed: {error_msg}")
            return ExecutionResult(
                success=False,
                error=f"Invalid contract address: {error_msg}",
                gas_used=0
            )
        
        # Validate method name
        if not transaction.method_name or not isinstance(transaction.method_name, str):
            return ExecutionResult(
                success=False,
                error="Method name cannot be empty",
                gas_used=0
            )
        
        if not transaction.method_name.replace('_', '').isalnum():
            return ExecutionResult(
                success=False,
                error=f"Invalid method name format: {transaction.method_name}",
                gas_used=0
            )
        
        # Validate method arguments
        is_valid, error_msg = self._validate_method_args(transaction.method_args)
        if not is_valid:
            logger.error(f"Method arguments validation failed: {error_msg}")
            return ExecutionResult(
                success=False,
                error=f"Invalid method arguments: {error_msg}",
                gas_used=0
            )
        
        # Validate gas limit
        if transaction.gas_limit < SmartContractTransaction.MIN_GAS_LIMIT:
            return ExecutionResult(
                success=False,
                error=f"Gas limit too low: {transaction.gas_limit} (min: {SmartContractTransaction.MIN_GAS_LIMIT})",
                gas_used=0
            )
        
        if transaction.gas_limit > SmartContractTransaction.MAX_GAS_LIMIT_CALL:
            return ExecutionResult(
                success=False,
                error=f"Gas limit too high: {transaction.gas_limit} (max: {SmartContractTransaction.MAX_GAS_LIMIT_CALL})",
                gas_used=0
            )
        
        execution_id = hashlib.sha256(
            f"{sender}{time.time()}{transaction.contract_address}{transaction.method_name}".encode()
        ).hexdigest()[:16]
        
        self.active_executions[execution_id] = start_time
        
        try:
            vm = await self.get_vm_instance()
            
            # Load contract state
            await self._load_contract_state(vm, transaction.contract_address)
            
            # Set current transaction hash
            tx_hash = hashlib.sha256(transaction.hex().encode()).hexdigest()
            self.blockchain_interface.set_current_transaction_hash(tx_hash)
            
            logger.info(f"Calling contract {transaction.contract_address} method '{transaction.method_name}' for {sender}, gas_limit: {transaction.gas_limit}")
            
            # Execute contract method
            result = vm.call_contract(
                transaction.contract_address,
                transaction.method_name,
                *transaction.method_args,
                sender=sender,
                value=transaction.outputs[0].amount if transaction.outputs else Decimal('0'),
                gas_limit=transaction.gas_limit
            )
            
            # Update transaction with results
            transaction.gas_used = vm.execution_context.gas_used if vm.execution_context else 0
            transaction.execution_result = result
            
            logger.info(f"Contract call successful, result: {result}, gas used: {transaction.gas_used}")
            
            # Persist updated contract state
            if transaction.contract_address in vm.contracts:
                await self._persist_contract_state(
                    transaction.contract_address, 
                    vm.contracts[transaction.contract_address]
                )
            
            # Record execution stats
            execution_time = time.time() - start_time
            self._record_execution_stats(execution_time, transaction.gas_used)
            
            return ExecutionResult(
                success=True,
                result=result,
                gas_used=transaction.gas_used,
                state_changes={'contract_call': transaction.contract_address}
            )
            
        except Exception as e:
            logger.error(f"Contract call failed: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                error=str(e),
                gas_used=getattr(transaction, 'gas_used', 0)
            )
        
        finally:
            if 'vm' in locals():
                await self.return_vm_instance(vm)
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
    
    async def execute_transaction(self, transaction: SmartContractTransaction,
                                sender: str) -> ExecutionResult:
        """
        Execute a smart contract transaction (deploy or call)
        
        Args:
            transaction: Smart contract transaction
            sender: Sender address
            
        Returns:
            ExecutionResult
        """
        if transaction.is_deployment():
            return await self.deploy_contract(transaction, sender)
        else:
            return await self.call_contract(transaction, sender)
    
    async def execute_batch(self, transactions: List[Tuple[SmartContractTransaction, str]]) -> List[ExecutionResult]:
        """
        Execute multiple transactions in parallel
        
        Args:
            transactions: List of (transaction, sender) tuples
            
        Returns:
            List of ExecutionResults
        """
        tasks = []
        for transaction, sender in transactions:
            task = asyncio.create_task(self.execute_transaction(transaction, sender))
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _persist_contract_state(self, contract_address: str, state: ContractState):
        """Persist contract state to database"""
        try:
            if self.database:
                # Convert state to dictionary for storage
                state_data = {
                    'storage': state.storage,
                    'balance': str(state.balance),
                    'code': state.code,
                    'deployed_by': state.deployed_by,
                    'deployment_block': state.deployment_block
                }
                
                await self.database.save_contract_state(contract_address, state_data)
                
                # Update local cache
                if self.enable_caching:
                    self.contract_states[contract_address] = state
                    
        except Exception as e:
            logger.error(f"Failed to persist contract state: {e}")
    
    async def _load_contract_state(self, vm: StellarisVM, contract_address: str):
        """Load contract state into VM"""
        try:
            # Check cache first
            if self.enable_caching and contract_address in self.contract_states:
                vm.contracts[contract_address] = self.contract_states[contract_address]
                return
            
            # Load from database
            if self.database:
                state_data = await self.database.get_contract_state(contract_address)
                if state_data:
                    state = ContractState(
                        storage=state_data.get('storage', {}),
                        balance=Decimal(state_data.get('balance', '0')),
                        code=state_data.get('code', ''),
                        deployed_by=state_data.get('deployed_by', ''),
                        deployment_block=state_data.get('deployment_block', 0)
                    )
                    
                    vm.contracts[contract_address] = state
                    
                    # Update cache
                    if self.enable_caching:
                        self.contract_states[contract_address] = state
                        
        except Exception as e:
            logger.error(f"Failed to load contract state: {e}")
    
    def _record_execution_stats(self, execution_time: float, gas_used: int):
        """Record execution statistics"""
        self.execution_times.append(execution_time)
        self.stats.total_executions += 1
        self.stats.total_gas_used += gas_used
        
        # Keep only last 1000 execution times for average calculation
        if len(self.execution_times) > 1000:
            self.execution_times = self.execution_times[-1000:]
        
        self.stats.avg_execution_time = sum(self.execution_times) / len(self.execution_times)
    
    async def get_contract_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get contract information"""
        try:
            # Check cache first
            if self.enable_caching and contract_address in self.contract_states:
                state = self.contract_states[contract_address]
                return {
                    'address': contract_address,
                    'deployed_by': state.deployed_by,
                    'deployment_block': state.deployment_block,
                    'balance': str(state.balance),
                    'storage_keys': list(state.storage.keys())
                }
            
            # Load from database
            if self.database:
                return await self.database.get_contract_info(contract_address)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get contract info: {e}")
            return None
    
    async def estimate_gas(self, transaction: SmartContractTransaction) -> int:
        """Estimate gas needed for transaction"""
        return await self.blockchain_interface.estimate_gas(transaction.to_dict())
    
    def get_stats(self) -> VMPoolStats:
        """Get current VM pool statistics"""
        self.stats.pending_executions = len(self.active_executions)
        return self.stats
    
    async def cleanup(self):
        """Cleanup resources"""
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clear pools and caches
        self.vm_pool.clear()
        self.contract_states.clear()
        self.state_cache.clear()
        self.active_executions.clear()
        
        logger.info("VM Manager cleanup completed")
