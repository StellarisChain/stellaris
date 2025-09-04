"""
Stellaris Virtual Machine for secure execution of Python smart contracts
"""

import ast
import sys
import time
import copy
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from decimal import Decimal, getcontext
from dataclasses import dataclass, field
from contextlib import contextmanager
import hashlib
import json

from p2pd import Dec

from stellaris.svm.exceptions import (
    SVMError, SVMSecurityError, SVMResourceError, 
    SVMTimeoutError, SVMMemoryError, SVMGasError,
    SVMValidationError, SVMContractError, SVMInvalidCallError
)

# Set high precision for Decimal operations
getcontext().prec = 28

@dataclass
class ContractState:
    """Represents the persistent state of a smart contract"""
    storage: Dict[str, Any] = field(default_factory=dict)
    balance: Decimal = field(default=Decimal('0'))
    code: str = ""
    deployed_by: str = ""
    deployment_block: int = 0

@dataclass
class ExecutionContext:
    """Context for contract execution"""
    sender: str
    contract_address: str
    value: Decimal = field(default=Decimal('0'))
    gas_limit: int = 100000
    gas_used: int = 0
    block_number: int = 0
    block_timestamp: int = 0
    transaction_hash: str = ""

@dataclass
class ContractCall:
    """Represents a contract method call"""
    method_name: str
    args: List[Any]
    kwargs: Dict[str, Any]

class SecureBuiltins:
    """Secure built-in functions for smart contracts"""
    
    @staticmethod
    def secure_print(*args, **kwargs):
        """Secure print that limits output"""
        output = ' '.join(str(arg) for arg in args)
        if len(output) > 1000:
            raise SVMSecurityError("Print output too long")
        return output
    
    @staticmethod
    def secure_len(obj):
        """Secure length function"""
        return len(obj)
    
    @staticmethod
    def secure_str(obj):
        """Secure string conversion"""
        result = str(obj)
        if len(result) > 10000:
            raise SVMSecurityError("String too long")
        return result
    
    @staticmethod
    def secure_int(obj):
        """Secure integer conversion"""
        return int(obj)
    
    @staticmethod
    def secure_abs(obj):
        """Secure absolute value"""
        return abs(obj)
    
    @staticmethod
    def secure_min(*args):
        """Secure minimum function"""
        return min(args)
    
    @staticmethod
    def secure_max(*args):
        """Secure maximum function"""
        return max(args)

class SmartContract:
    """Base class for smart contracts"""
    
    def __init__(self, vm: 'StellarisVM', address: str):
        self.vm = vm
        self.address = address
        self._exports = {}
        
        # Auto-register methods that don't start with underscore and aren't constructor
        for name in dir(self):
            if not name.startswith('_') and name != 'constructor':
                attr = getattr(self, name)
                if callable(attr) and not name in ['vm', 'address', 'export', 'get_storage', 'set_storage', 'call_contract', 'get_balance', 'transfer']:
                    self._exports[name] = attr
        
    def export(self, func: Callable) -> Callable:
        """Decorator to mark functions as contract exports"""
        self._exports[func.__name__] = func
        return func
    
    def get_storage(self, key: str) -> Any:
        """Get value from contract storage"""
        return self.vm.get_contract_storage(self.address, key)
    
    def set_storage(self, key: str, value: Any):
        """Set value in contract storage"""
        self.vm.set_contract_storage(self.address, key, value)
    
    def call_contract(self, address: str, method: str, *args, **kwargs) -> Any:
        """Call another contract"""
        return self.vm.call_contract(address, method, *args, **kwargs)
    
    def get_balance(self, address: str) -> Decimal:
        """Get balance of an address"""
        return self.vm.get_balance(address)
    
    def transfer(self, to: str, amount: Decimal):
        """Transfer tokens from contract to address"""
        self.vm.transfer(self.address, to, amount)

class StellarisVM:
    """
    Stellaris Virtual Machine for executing Python smart contracts
    """
    
    # Execution limits
    MAX_EXECUTION_TIME = 30.0  # 30 seconds
    MAX_MEMORY_USAGE = 50 * 1024 * 1024  # 50MB
    MAX_RECURSION_DEPTH = 100
    MAX_LOOP_ITERATIONS = 1000000
    
    # Gas costs
    GAS_COSTS: dict[str, float | Decimal] = {
        'base_call': 0.0001,
        'storage_write': 0.002,
        'storage_read': 0.001,
        'memory_word': 0.0003,
        'computation': 0.0001,
        'transfer': 0.9,
        'contract_creation': 1,
    }
    
    # Gas constants
    MAX_GAS_LIMIT = 10_000_000
    BASE_GAS = 1
    GAS_PRICE = Decimal('0.000001')
    
    def __init__(self, blockchain_interface=None):
        """
        Initialize the Stellaris VM
        
        Args:
            blockchain_interface: Interface to blockchain for getting block data
        """
        self.contracts: Dict[str, ContractState] = {}
        self.balances: Dict[str, Decimal] = {}
        self.execution_context: Optional[ExecutionContext] = None
        self.call_stack: List[str] = []
        self.loop_counters: Dict[str, int] = {}
        self.blockchain_interface = blockchain_interface
        
        # Security restrictions
        self.allowed_imports = {
            'decimal', 'datetime', 'hashlib', 'json', 'math', 're', 'typing', 'time',
            'dataclasses', 'stellaris.svm.vm', 'stellaris.svm.exceptions', 'sys', 'os'
        }
        
        self.forbidden_calls = {
            'eval', 'exec', 'compile', 'open', 'file',
            'input', 'raw_input', 'exit', 'quit', 'reload', 'vars',
            'globals', 'locals', 'dir', 'delattr', '__builtins__'
        }
        
        # Create secure builtins
        self.secure_builtins = {
            'print': SecureBuiltins.secure_print,
            'len': SecureBuiltins.secure_len,
            'str': SecureBuiltins.secure_str,
            'int': SecureBuiltins.secure_int,
            'abs': SecureBuiltins.secure_abs,
            'min': SecureBuiltins.secure_min,
            'max': SecureBuiltins.secure_max,
            'getattr': getattr,
            'hasattr': hasattr,
            'setattr': setattr,
            'isinstance': isinstance,
            '__import__': self._secure_import,
            '__build_class__': __build_class__,
            'super': super,
            'type': type,
            'object': object,
            'property': property,
            'staticmethod': staticmethod,
            'classmethod': classmethod,
            'bool': bool,
            'float': float,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'frozenset': frozenset,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sorted': sorted,
            'reversed': reversed,
            'all': all,
            'any': any,
            'sum': sum,
            'Exception': Exception,
            'ValueError': ValueError,
            'TypeError': TypeError,
            'KeyError': KeyError,
            'AttributeError': AttributeError,
            'IndexError': IndexError,
            'Decimal': Decimal,
            'True': True,
            'False': False,
            'None': None,
        }
    
    def get_current_block_number(self) -> int:
        """Get current block number from blockchain interface"""
        if self.blockchain_interface and hasattr(self.blockchain_interface, 'get_current_block_number'):
            # Use asyncio to run the async method if we're in an async context
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, but need to handle this sync call
                    # For now, return a cached value or default
                    return getattr(self.blockchain_interface, '_cached_block_number', 1)
                else:
                    return loop.run_until_complete(self.blockchain_interface.get_current_block_number())
            except RuntimeError:
                # No event loop, return cached or default
                return getattr(self.blockchain_interface, '_cached_block_number', 1)
        return 1  # Default fallback
    
    def get_current_block_timestamp(self) -> int:
        """Get current block timestamp from blockchain interface"""
        if self.blockchain_interface and hasattr(self.blockchain_interface, 'get_current_block_timestamp'):
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return getattr(self.blockchain_interface, '_cached_block_timestamp', int(time.time()))
                else:
                    return loop.run_until_complete(self.blockchain_interface.get_current_block_timestamp())
            except RuntimeError:
                return getattr(self.blockchain_interface, '_cached_block_timestamp', int(time.time()))
        return int(time.time())  # Default fallback
    
    def get_transaction_hash(self) -> str:
        """Get current transaction hash from blockchain interface"""
        if self.blockchain_interface and hasattr(self.blockchain_interface, 'get_current_transaction_hash'):
            return self.blockchain_interface.get_current_transaction_hash()
        return f"tx_{int(time.time())}_{hash(str(time.time()))}"  # Default fallback
    
    def _secure_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Secure import function that only allows whitelisted modules"""
        if name not in self.allowed_imports:
            raise SVMSecurityError(f"Import not allowed: {name}")
        
        # Handle special cases for our VM modules
        if name == 'stellaris.svm.vm':
            # Return a module-like object with SmartContract
            class VMModule:
                SmartContract = SmartContract
            return VMModule()
        
        # For other allowed imports, use the real import
        return __import__(name, globals, locals, fromlist, level)
    
    def _consume_gas(self, amount: int):
        """Consume gas for operation"""
        if not self.execution_context:
            return
            
        self.execution_context.gas_used += amount
        if self.execution_context.gas_used > self.execution_context.gas_limit:
            raise SVMGasError(f"Gas limit exceeded: {self.execution_context.gas_used} > {self.execution_context.gas_limit}")
    
    def _validate_contract_code(self, code: str) -> bool:
        """Validate contract code for security"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SVMValidationError(f"Syntax error in contract: {e}")
        
        # Check for forbidden constructs
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.allowed_imports:
                        raise SVMSecurityError(f"Forbidden import: {alias.name}")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module not in self.allowed_imports:
                    raise SVMSecurityError(f"Forbidden import: {node.module}")
            
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.forbidden_calls:
                        raise SVMSecurityError(f"Forbidden function call: {node.func.id}")
        
        return True
    
    def deploy_contract(self, code: str, constructor_args: List[Any], 
                       deployer: str, gas_limit: int = 1000000) -> str:
        """Deploy a new smart contract"""
        
        # Validate code
        self._validate_contract_code(code)
        
        # Generate contract address
        contract_address = hashlib.sha256(
            f"{deployer}{time.time()}{code}".encode()
        ).hexdigest()[:40]
        
        # Create execution context
        context = ExecutionContext(
            sender=deployer,
            contract_address=contract_address,
            gas_limit=gas_limit,
            block_number=self.get_current_block_number(),
            block_timestamp=self.get_current_block_timestamp(),
            transaction_hash=self.get_transaction_hash()
        )
        
        self.execution_context = context
        self._consume_gas(self.GAS_COSTS['contract_creation'])
        
        try:
            # Create contract state
            contract_state = ContractState(
                code=code,
                deployed_by=deployer,
                deployment_block=context.block_number
            )
            
            self.contracts[contract_address] = contract_state
            
            # Create and initialize contract instance first
            execution_env = self._create_execution_environment(contract_address)
            exec(contract_state.code, execution_env)
            
            # Find the contract class
            contract_class = None
            for name, obj in execution_env.items():
                if isinstance(obj, type) and issubclass(obj, SmartContract):
                    contract_class = obj
                    break
            
            if not contract_class:
                raise SVMContractError("No contract class found")
            
            # Create contract instance (this runs __init__ and registers exports)
            contract_instance = contract_class(self, contract_address)
            
            # Transfer pending exports from contract context to instance
            if 'self' in execution_env and hasattr(execution_env['self'], '_pending_exports'):
                for method_name, method_func in execution_env['self']._pending_exports.items():
                    # Bind the method to the contract instance
                    bound_method = method_func.__get__(contract_instance, contract_class)
                    contract_instance._exports[method_name] = bound_method
            
            # Store the contract instance for later use
            contract_state.instance = contract_instance
            
            # Execute constructor if present and arguments provided
            if constructor_args and 'constructor' in contract_instance._exports:
                # Make sure execution context is available
                if not self.execution_context:
                    self.execution_context = ExecutionContext(
                        sender=deployer,
                        contract_address=contract_address,
                        gas_limit=gas_limit,
                        block_number=self.get_current_block_number(),
                        block_timestamp=self.get_current_block_timestamp(),
                        transaction_hash=self.get_transaction_hash()
                    )
                # Call constructor with sender as first argument (like regular method calls)
                contract_instance._exports['constructor'](self.execution_context.sender, *constructor_args)
            
            return contract_address
            
        finally:
            self.execution_context = None
    
    def call_contract(self, contract_address: str, method_name: str, 
                     *args, sender: str = None, value: Decimal = None,
                     gas_limit: int = 100000, **kwargs) -> Any:
        """Call a contract method"""
        
        if contract_address not in self.contracts:
            raise SVMContractError(f"Contract not found: {contract_address}")
        
        # Set up execution context
        context = ExecutionContext(
            sender=sender or "0x0",
            contract_address=contract_address,
            value=value or Decimal('0'),
            gas_limit=gas_limit,
            block_number=self.get_current_block_number(),
            block_timestamp=self.get_current_block_timestamp(),
            transaction_hash=self.get_transaction_hash()
        )
        
        old_context: ExecutionContext | None = self.execution_context
        self.execution_context = context
        
        try:
            self._consume_gas(self.GAS_COSTS['base_call'])
            return self._execute_contract_method(contract_address, method_name, args, kwargs)
        finally:
            self.execution_context = old_context
    
    def _execute_contract_method(self, contract_address: str, method_name: str, 
                                args: List[Any], kwargs: Dict[str, Any]) -> Any:
        """Execute a specific contract method"""
        
        contract_state = self.contracts[contract_address]
        
        # Check recursion depth
        if len(self.call_stack) >= self.MAX_RECURSION_DEPTH:
            raise SVMResourceError("Maximum recursion depth exceeded")
        
        self.call_stack.append(f"{contract_address}.{method_name}")
        
        try:
            # Use stored contract instance if available, otherwise create new one
            if hasattr(contract_state, 'instance') and contract_state.instance:
                contract_instance = contract_state.instance
            else:
                # Fallback: create new instance
                execution_env = self._create_execution_environment(contract_address)
                exec(contract_state.code, execution_env)
                
                contract_class = None
                for name, obj in execution_env.items():
                    if isinstance(obj, type) and issubclass(obj, SmartContract):
                        contract_class = obj
                        break
                
                if not contract_class:
                    raise SVMContractError("No contract class found")
                
                contract_instance = contract_class(self, contract_address)
            
            # Special handling for constructor
            if method_name == 'constructor':
                if hasattr(contract_instance, 'constructor'):
                    method = contract_instance.constructor
                else:
                    # No constructor defined, just return
                    return True
            else:
                # Call the method
                if method_name not in contract_instance._exports:
                    available_methods = list(contract_instance._exports.keys())
                    raise SVMInvalidCallError(
                        f"Method {method_name} not exported", 
                        available_methods=available_methods
                    )
                method = contract_instance._exports[method_name]
            
            # Execute with timeout
            start_time = time.time()
            result = None
            
            def execute_method():
                nonlocal result
                # Add sender as first argument for compatibility
                if self.execution_context:
                    result = method(self.execution_context.sender, *args, **kwargs)
                else:
                    result = method(*args, **kwargs)
            
            thread = threading.Thread(target=execute_method)
            thread.daemon = True
            thread.start()
            thread.join(timeout=self.MAX_EXECUTION_TIME)
            
            if thread.is_alive():
                raise SVMTimeoutError("Contract execution timeout")
            
            return result
            
        finally:
            self.call_stack.pop()
    
    def _create_execution_environment(self, contract_address: str) -> Dict[str, Any]:
        """Create secure execution environment for contract"""
        env = copy.deepcopy(self.secure_builtins)
        
        # Create contract context object that will be available as 'self' during class definition
        class ContractContext:
            def __init__(self, vm_instance, contract_addr):
                self.vm = vm_instance
                self.address = contract_addr
                self.storage = vm_instance._create_storage_proxy(contract_addr)
                self.balance = vm_instance.get_balance(contract_addr)
                self._pending_exports = {}  # Store exports until contract instance is created
            
            def export(self, func):
                """Decorator to mark methods as exported"""
                self._pending_exports[func.__name__] = func
                return func
            
            def set_storage(self, key, value):
                """Proxy for storage operations during contract definition"""
                return self.vm.set_contract_storage(self.address, key, value)
            
            def get_storage(self, key, default=None):
                """Proxy for storage operations during contract definition"""
                return self.vm.get_contract_storage(self.address, key) or default
        
        # Create the context instance
        contract_context = ContractContext(self, contract_address)
        
        env.update({
            'SmartContract': SmartContract,
            '__name__': '__main__',
            '__file__': f'<contract:{contract_address}>',
            '__builtins__': self.secure_builtins,
            'self': contract_context,  # This makes @self.export work
            'Contract': lambda addr: self._create_contract_proxy(addr),
        })
        
        return env
    
    def _register_export(self, contract_address: str, func: Callable) -> Callable:
        """Register an exported function"""
        # This is handled by the SmartContract class
        return func
    
    def _create_storage_proxy(self, contract_address: str):
        """Create a storage proxy for contract state"""
        class StorageProxy:
            def __init__(self, vm, address):
                self.vm = vm
                self.address = address
            
            def get(self, key: str, default=None):
                return self.vm.get_contract_storage(self.address, key) or default
            
            def __getitem__(self, key: str):
                return self.vm.get_contract_storage(self.address, key)
            
            def __setitem__(self, key: str, value: Any):
                self.vm.set_contract_storage(self.address, key, value)
            
            def update(self, data: Dict[str, Any]):
                for key, value in data.items():
                    self.vm.set_contract_storage(self.address, key, value)
        
        return StorageProxy(self, contract_address)
    
    def _create_contract_proxy(self, contract_address: str):
        """Create a proxy to call other contracts"""
        class ContractProxy:
            def __init__(self, vm, address):
                self.vm = vm
                self.address = address
            
            def __getattr__(self, method_name: str):
                def call_method(*args, **kwargs):
                    return self.vm.call_contract(self.address, method_name, *args, **kwargs)
                return call_method
        
        return ContractProxy(self, contract_address)
    
    def get_contract_storage(self, contract_address: str, key: str) -> Any:
        """Get value from contract storage"""
        if contract_address not in self.contracts:
            return None
        
        self._consume_gas(self.GAS_COSTS['storage_read'])
        return self.contracts[contract_address].storage.get(key)
    
    def set_contract_storage(self, contract_address: str, key: str, value: Any):
        """Set value in contract storage"""
        if contract_address not in self.contracts:
            raise SVMContractError(f"Contract not found: {contract_address}")
        
        self._consume_gas(self.GAS_COSTS['storage_write'])
        self.contracts[contract_address].storage[key] = value
    
    def get_balance(self, address: str) -> Decimal:
        """Get balance of an address"""
        return self.balances.get(address, Decimal('0'))
    
    def set_balance(self, address: str, amount: Decimal):
        """Set balance of an address"""
        self.balances[address] = amount
    
    def transfer(self, from_addr: str, to_addr: str, amount: Decimal):
        """Transfer tokens between addresses"""
        if amount <= 0:
            raise SVMContractError("Transfer amount must be positive")
        
        from_balance = self.get_balance(from_addr)
        if from_balance < amount:
            raise SVMContractError(f"Insufficient balance: {from_balance} < {amount}")
        
        self._consume_gas(self.GAS_COSTS['transfer'])
        
        self.set_balance(from_addr, from_balance - amount)
        self.set_balance(to_addr, self.get_balance(to_addr) + amount)
    
    def get_contract_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get contract information"""
        if contract_address not in self.contracts:
            return None
        
        contract = self.contracts[contract_address]
        return {
            'address': contract_address,
            'deployed_by': contract.deployed_by,
            'deployment_block': contract.deployment_block,
            'balance': contract.balance,
            'storage_keys': list(contract.storage.keys())
        }