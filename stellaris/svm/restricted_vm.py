"""
Enhanced Stellaris Virtual Machine using RestrictedPython for secure contract execution
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

# RestrictedPython imports
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_globals, safe_builtins

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
    compiled_code: Any = None  # Store compiled RestrictedPython code
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

class RestrictedSecurityPolicy:
    """Enhanced security policy for RestrictedPython"""
    
    # Allowed imports - very restrictive
    ALLOWED_MODULES = {
        'decimal': ['Decimal'],
        'datetime': ['datetime', 'date', 'time', 'timedelta'],
        'hashlib': ['sha256', 'md5', 'sha1'],
        'json': ['loads', 'dumps'],
        'math': ['sqrt', 'pow', 'abs', 'floor', 'ceil', 'round'],
        're': ['match', 'search', 'findall', 'sub'],
        'typing': ['List', 'Dict', 'Optional', 'Union', 'Any'],
    }
    
    # Forbidden attributes and methods
    FORBIDDEN_ATTRS = {
        '__import__', '__builtins__', '__globals__', '__locals__',
        '__dict__', '__class__', '__bases__', '__mro__', '__subclasses__',
        'exec', 'eval', 'compile', 'open', 'file', 'input', 'raw_input',
        'reload', 'vars', 'dir', 'globals', 'locals', 'exit', 'quit'
    }
    
    def check_name(self, name):
        """Check if a name is allowed"""
        if name in self.FORBIDDEN_ATTRS:
            raise SVMSecurityError(f"Access to '{name}' is forbidden")
        return name
    
    def check_getattr(self, obj, name):
        """Check attribute access"""
        if name.startswith('_'):
            raise SVMSecurityError(f"Access to private attribute '{name}' is forbidden")
        if name in self.FORBIDDEN_ATTRS:
            raise SVMSecurityError(f"Access to '{name}' is forbidden")
        return getattr(obj, name)

class SecureBuiltins:
    """Enhanced secure built-in functions for smart contracts"""
    
    @staticmethod
    def secure_print(*args, **kwargs):
        """Secure print that limits output and logs to execution context"""
        output = ' '.join(str(arg) for arg in args)
        if len(output) > 1000:
            raise SVMSecurityError("Print output too long")
        # In a real implementation, you might want to capture this output
        # for debugging or logging purposes
        return output
    
    @staticmethod
    def secure_len(obj):
        """Secure length function with limits"""
        try:
            length = len(obj)
            if length > 1000000:  # Limit to prevent memory exhaustion
                raise SVMResourceError("Object too large")
            return length
        except Exception as e:
            raise SVMSecurityError(f"Invalid length operation: {e}")
    
    @staticmethod
    def secure_str(obj):
        """Secure string conversion with length limits"""
        try:
            result = str(obj)
            if len(result) > 10000:
                raise SVMSecurityError("String too long")
            return result
        except Exception as e:
            raise SVMSecurityError(f"Invalid string conversion: {e}")
    
    @staticmethod
    def secure_getattr(obj, name, default=None):
        """Secure getattr that prevents access to private attributes"""
        if name.startswith('_'):
            raise SVMSecurityError(f"Access to private attribute '{name}' is forbidden")
        return getattr(obj, name, default)
    
    @staticmethod
    def secure_hasattr(obj, name):
        """Secure hasattr that prevents probing private attributes"""
        if name.startswith('_'):
            return False
        return hasattr(obj, name)

class SmartContract:
    """Base class for smart contracts with RestrictedPython support"""
    
    def __init__(self, vm: 'RestrictedStellarisVM', address: str):
        self.vm = vm
        self.address = address
        self._exports = {}
        
        # Auto-register methods that don't start with underscore
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

class RestrictedStellarisVM:
    """
    Enhanced Stellaris Virtual Machine using RestrictedPython for secure contract execution
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
    
    def __init__(self, blockchain_interface=None):
        """Initialize the RestrictedPython-based Stellaris VM"""
        self.contracts: Dict[str, ContractState] = {}
        self.balances: Dict[str, Decimal] = {}
        self.execution_context: Optional[ExecutionContext] = None
        self.call_stack: List[str] = []
        self.loop_counters: Dict[str, int] = {}
        self.blockchain_interface = blockchain_interface
        self.security_policy = RestrictedSecurityPolicy()
        
        # Create secure globals for RestrictedPython
        self.secure_globals = self._create_secure_globals()
        
    def _create_secure_globals(self) -> Dict[str, Any]:
        """Create secure globals dictionary for RestrictedPython execution"""
        # Start with RestrictedPython's safe globals
        secure_globals = safe_globals.copy()
        
        # Add our custom secure builtins
        secure_builtins = safe_builtins.copy()
        secure_builtins.update({
            'print': SecureBuiltins.secure_print,
            'len': SecureBuiltins.secure_len,
            'str': SecureBuiltins.secure_str,
            'getattr': SecureBuiltins.secure_getattr,
            'hasattr': SecureBuiltins.secure_hasattr,
            # Add controlled access to common types
            'Decimal': Decimal,
            'dict': dict,
            'list': list,
            'tuple': tuple,
            'set': set,
            'int': int,
            'float': float,
            'bool': bool,
            'min': min,
            'max': max,
            'sum': sum,
            'abs': abs,
            'round': round,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sorted': sorted,
            'reversed': reversed,
        })
        
        secure_globals.update({
            '__builtins__': secure_builtins,
            'SmartContract': SmartContract,
            # Security guards
            '_getattr_': self.security_policy.check_getattr,
            '_getitem_': lambda obj, key: obj[key],  # Allow item access
            '_getiter_': lambda obj: iter(obj),  # Allow iteration
            '_write_': lambda x: x,  # Allow writes (controlled by storage proxy)
        })
        
        return secure_globals
    
    def _compile_contract_code(self, code: str, contract_address: str) -> Any:
        """Compile contract code using RestrictedPython"""
        try:
            # Compile the code with RestrictedPython
            compiled_code = compile_restricted(
                code, 
                filename=f'<contract:{contract_address}>', 
                mode='exec'
            )
            
            if compiled_code is None:
                raise SVMValidationError("Failed to compile contract code")
                
            return compiled_code
            
        except SyntaxError as e:
            raise SVMValidationError(f"Syntax error in contract code: {e}")
        except Exception as e:
            raise SVMValidationError(f"Failed to compile contract: {e}")
    
    def deploy_contract(self, code: str, deployer: str, constructor_args: List[Any] = None, 
                       gas_limit: int = 1000000) -> str:
        """Deploy a smart contract using RestrictedPython compilation"""
        
        # Generate contract address
        contract_address = hashlib.sha256(
            f"{deployer}{code}{time.time()}".encode()
        ).hexdigest()[:40]
        
        # Set up execution context
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
            # Compile the contract code
            compiled_code = self._compile_contract_code(code, contract_address)
            
            # Create contract state
            contract_state = ContractState(
                code=code,
                compiled_code=compiled_code,
                deployed_by=deployer,
                deployment_block=context.block_number
            )
            
            self.contracts[contract_address] = contract_state
            
            # Create execution environment and execute
            execution_env = self._create_execution_environment(contract_address)
            exec(compiled_code, execution_env)
            
            # Find and instantiate the contract class
            contract_class = None
            for name, obj in execution_env.items():
                if isinstance(obj, type) and issubclass(obj, SmartContract) and obj is not SmartContract:
                    contract_class = obj
                    break
            
            if not contract_class:
                raise SVMContractError("No contract class found")
            
            # Create contract instance
            contract_instance = contract_class(self, contract_address)
            contract_state.instance = contract_instance
            
            # Execute constructor if present
            if constructor_args and 'constructor' in contract_instance._exports:
                self.call_contract(contract_address, 'constructor', *constructor_args)
            
            return contract_address
            
        except Exception as e:
            # Clean up on failure
            if contract_address in self.contracts:
                del self.contracts[contract_address]
            raise SVMContractError(f"Contract deployment failed: {e}")
        finally:
            self.execution_context = None
    
    def call_contract(self, contract_address: str, method_name: str, *args, **kwargs) -> Any:
        """Call a contract method using RestrictedPython execution"""
        
        if contract_address not in self.contracts:
            raise SVMContractError(f"Contract {contract_address} not found")
        
        contract_state = self.contracts[contract_address]
        
        # Set up execution context if not already set
        if not self.execution_context:
            context = ExecutionContext(
                sender="system",  # Should be set by caller
                contract_address=contract_address,
                gas_limit=100000,
                block_number=self.get_current_block_number(),
                block_timestamp=self.get_current_block_timestamp(),
                transaction_hash=self.get_transaction_hash()
            )
            self.execution_context = context
        
        self._consume_gas(self.GAS_COSTS['base_call'])
        
        try:
            # Use stored contract instance if available
            if hasattr(contract_state, 'instance') and contract_state.instance:
                contract_instance = contract_state.instance
            else:
                # Recreate instance using compiled code
                execution_env = self._create_execution_environment(contract_address)
                exec(contract_state.compiled_code, execution_env)
                
                contract_class = None
                for name, obj in execution_env.items():
                    if isinstance(obj, type) and issubclass(obj, SmartContract) and obj is not SmartContract:
                        contract_class = obj
                        break
                
                if not contract_class:
                    raise SVMContractError("No contract class found")
                
                contract_instance = contract_class(self, contract_address)
                contract_state.instance = contract_instance
            
            # Get the method
            if method_name == 'constructor':
                if hasattr(contract_instance, 'constructor'):
                    method = contract_instance.constructor
                else:
                    return True
            else:
                if method_name not in contract_instance._exports:
                    available_methods = list(contract_instance._exports.keys())
                    raise SVMInvalidCallError(
                        f"Method {method_name} not exported", 
                        available_methods=available_methods
                    )
                method = contract_instance._exports[method_name]
            
            # Execute with timeout and security
            start_time = time.time()
            result = None
            
            def execute_method():
                nonlocal result
                try:
                    # Execute in restricted environment
                    if self.execution_context:
                        result = method(self.execution_context.sender, *args, **kwargs)
                    else:
                        result = method(*args, **kwargs)
                except Exception as e:
                    raise SVMError(f"Contract execution error: {e}")
            
            # Run with timeout
            thread = threading.Thread(target=execute_method)
            thread.daemon = True
            thread.start()
            thread.join(timeout=self.MAX_EXECUTION_TIME)
            
            if thread.is_alive():
                raise SVMTimeoutError(f"Contract execution timeout after {self.MAX_EXECUTION_TIME}s")
            
            execution_time = time.time() - start_time
            self._consume_gas(Decimal(str(execution_time)) * self.GAS_COSTS['computation'])
            
            return result
            
        except Exception as e:
            if isinstance(e, (SVMError, SVMSecurityError)):
                raise
            raise SVMError(f"Contract call failed: {e}")
    
    def _create_execution_environment(self, contract_address: str) -> Dict[str, Any]:
        """Create secure execution environment using RestrictedPython globals"""
        env = self.secure_globals.copy()
        
        # Add contract-specific context
        contract_context = self._create_contract_context(contract_address)
        
        env.update({
            '__name__': '__main__',
            '__file__': f'<contract:{contract_address}>',
            'self': contract_context,
            'Contract': lambda addr: self._create_contract_proxy(addr),
        })
        
        return env
    
    def _create_contract_context(self, contract_address: str):
        """Create contract context for execution"""
        class ContractContext:
            def __init__(self, vm_instance, contract_addr):
                self.vm = vm_instance
                self.address = contract_addr
                self.storage = vm_instance._create_storage_proxy(contract_addr)
                self.balance = vm_instance.get_balance(contract_addr)
                self._pending_exports = {}
            
            def export(self, func):
                """Decorator to mark methods as exported"""
                self._pending_exports[func.__name__] = func
                return func
            
            def set_storage(self, key, value):
                return self.vm.set_contract_storage(self.address, key, value)
            
            def get_storage(self, key, default=None):
                return self.vm.get_contract_storage(self.address, key) or default
        
        return ContractContext(self, contract_address)
    
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
        
        return StorageProxy(self, contract_address)
    
    def _create_contract_proxy(self, contract_address: str):
        """Create a proxy to call other contracts"""
        class ContractProxy:
            def __init__(self, vm, address):
                self.vm = vm
                self.address = address
            
            def call(self, method: str, *args, **kwargs):
                return self.vm.call_contract(self.address, method, *args, **kwargs)
        
        return ContractProxy(self, contract_address)
    
    # Utility methods (implement these based on your existing VM)
    def get_balance(self, address: str) -> Decimal:
        """Get balance of an address"""
        return self.balances.get(address, Decimal('0'))
    
    def get_contract_storage(self, contract_address: str, key: str) -> Any:
        """Get value from contract storage"""
        if contract_address in self.contracts:
            return self.contracts[contract_address].storage.get(key)
        return None
    
    def set_contract_storage(self, contract_address: str, key: str, value: Any):
        """Set value in contract storage"""
        if contract_address in self.contracts:
            self.contracts[contract_address].storage[key] = value
            self._consume_gas(self.GAS_COSTS['storage_write'])
    
    def transfer(self, from_address: str, to_address: str, amount: Decimal):
        """Transfer tokens between addresses"""
        if self.get_balance(from_address) < amount:
            raise SVMError("Insufficient balance")
        
        self.balances[from_address] = self.get_balance(from_address) - amount
        self.balances[to_address] = self.get_balance(to_address) + amount
        self._consume_gas(self.GAS_COSTS['transfer'])
    
    def _consume_gas(self, amount: Union[int, float, Decimal]):
        """Consume gas for operation"""
        if self.execution_context:
            gas_to_consume = int(amount) if isinstance(amount, (int, float)) else int(amount)
            self.execution_context.gas_used += gas_to_consume
            
            if self.execution_context.gas_used > self.execution_context.gas_limit:
                raise SVMGasError("Out of gas")
    
    def get_current_block_number(self) -> int:
        """Get current block number"""
        return 1  # Placeholder
    
    def get_current_block_timestamp(self) -> int:
        """Get current block timestamp"""
        return int(time.time())
    
    def get_transaction_hash(self) -> str:
        """Get current transaction hash"""
        return "0x" + "0" * 64  # Placeholder
