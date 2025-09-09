"""
Integration Guide: Adding RestrictedPython to Stellaris VM

This guide shows how to enhance your existing Stellaris VM with RestrictedPython
for improved security when executing smart contracts.
"""

from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_globals, safe_builtins
from typing import Dict, Any, Optional
from decimal import Decimal

class RestrictedVMEnhancement:
    """
    Enhancement class to add RestrictedPython support to existing Stellaris VM
    """
    
    def __init__(self, original_vm):
        """
        Initialize with reference to original VM
        
        Args:
            original_vm: Your existing StellarisVM instance
        """
        self.vm = original_vm
        self.restricted_globals = self._create_restricted_globals()
    
    def _create_restricted_globals(self) -> Dict[str, Any]:
        """Create secure globals for RestrictedPython execution"""
        
        # Start with RestrictedPython's safe defaults
        restricted_globals = safe_globals.copy()
        restricted_builtins = safe_builtins.copy()
        
        # Add essential functions for smart contracts
        restricted_builtins.update({
            'len': len,
            'str': self._safe_str,
            'int': int,
            'float': float,
            'bool': bool,
            'min': min,
            'max': max,
            'sum': sum,
            'abs': abs,
            'round': round,
            'range': self._safe_range,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'enumerate': enumerate,
            'zip': zip,
            'sorted': sorted,
            'reversed': reversed,
            'Decimal': Decimal,
            # Contract-specific functions
            'print': self._safe_print,
        })
        
        restricted_globals.update({
            '__builtins__': restricted_builtins,
            # Security guards
            '_getattr_': self._safe_getattr,
            '_getitem_': self._safe_getitem,
            '_getiter_': self._safe_getiter,
            '_write_': self._safe_write,
            # Allow iteration
            '_iter_unpack_sequence_': lambda x, spec: x,
        })
        
        return restricted_globals
    
    def _safe_str(self, obj):
        """Safe string conversion with length limits"""
        result = str(obj)
        if len(result) > 10000:
            raise ValueError("String too long")
        return result
    
    def _safe_range(self, *args):
        """Safe range function with iteration limits"""
        if len(args) == 1:
            stop = args[0]
            start, step = 0, 1
        elif len(args) == 2:
            start, stop = args
            step = 1
        elif len(args) == 3:
            start, stop, step = args
        else:
            raise TypeError("range() takes 1 to 3 arguments")
        
        # Limit range size to prevent memory exhaustion
        if abs((stop - start) // step) > 1000000:
            raise ValueError("Range too large")
        
        return range(start, stop, step)
    
    def _safe_print(self, *args, **kwargs):
        """Safe print that captures output instead of printing to stdout"""
        output = ' '.join(str(arg) for arg in args)
        if len(output) > 1000:
            raise ValueError("Print output too long")
        
        # In a real implementation, you might want to:
        # 1. Log this output for debugging
        # 2. Return it as part of transaction results
        # 3. Store it in execution context
        return output
    
    def _safe_getattr(self, obj, name):
        """Safe attribute access that blocks dangerous attributes"""
        if name.startswith('_'):
            raise AttributeError(f"Access to private attribute '{name}' is forbidden")
        
        # Block access to dangerous attributes
        forbidden = {'__class__', '__dict__', '__globals__', '__locals__', '__module__'}
        if name in forbidden:
            raise AttributeError(f"Access to '{name}' is forbidden")
        
        return getattr(obj, name)
    
    def _safe_getitem(self, obj, key):
        """Safe item access"""
        return obj[key]
    
    def _safe_getiter(self, obj):
        """Safe iteration"""
        return iter(obj)
    
    def _safe_write(self, obj):
        """Safe write guard"""
        return obj
    
    def compile_contract_secure(self, code: str, contract_name: str) -> Any:
        """
        Compile contract code using RestrictedPython
        
        Args:
            code: Smart contract source code
            contract_name: Name/identifier for the contract
            
        Returns:
            Compiled code object or None if compilation failed
        """
        try:
            # Use RestrictedPython to compile the code
            compiled_code = compile_restricted(
                code,
                filename=f'<contract:{contract_name}>',
                mode='exec'
            )
            
            if compiled_code is None:
                raise ValueError("Code contains restricted operations")
            
            return compiled_code
            
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {e}")
        except Exception as e:
            raise ValueError(f"Compilation failed: {e}")
    
    def execute_contract_secure(self, compiled_code: Any, contract_address: str) -> Dict[str, Any]:
        """
        Execute compiled contract code in a restricted environment
        
        Args:
            compiled_code: Code compiled with RestrictedPython
            contract_address: Address of the contract
            
        Returns:
            Execution environment with contract definitions
        """
        # Create execution environment
        env = self.restricted_globals.copy()
        
        # Add contract-specific context
        env.update({
            '__name__': '__main__',
            '__file__': f'<contract:{contract_address}>',
            # Add your VM's contract base class
            'SmartContract': self.vm.SmartContract if hasattr(self.vm, 'SmartContract') else object,
            # Add storage interface
            'storage': self._create_storage_interface(contract_address),
            # Add contract utilities
            'get_balance': lambda addr: self.vm.get_balance(addr),
            'transfer': lambda to, amount: self._safe_transfer(contract_address, to, amount),
            'call_contract': lambda addr, method, *args: self.vm.call_contract(addr, method, *args),
        })
        
        # Execute the code
        exec(compiled_code, env)
        
        return env
    
    def _create_storage_interface(self, contract_address: str):
        """Create a storage interface for the contract"""
        class RestrictedStorage:
            def __init__(self, vm, address):
                self.vm = vm
                self.address = address
            
            def get(self, key: str, default=None):
                if not isinstance(key, str):
                    raise TypeError("Storage key must be string")
                return self.vm.get_contract_storage(self.address, key) or default
            
            def set(self, key: str, value):
                if not isinstance(key, str):
                    raise TypeError("Storage key must be string")
                # Limit storage value size
                if isinstance(value, str) and len(value) > 100000:
                    raise ValueError("Storage value too large")
                self.vm.set_contract_storage(self.address, key, value)
            
            def __getitem__(self, key):
                return self.get(key)
            
            def __setitem__(self, key, value):
                self.set(key, value)
        
        return RestrictedStorage(self.vm, contract_address)
    
    def _safe_transfer(self, from_address: str, to_address: str, amount):
        """Safe transfer with validation"""
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError("Transfer amount must be positive")
            
            return self.vm.transfer(from_address, to_address, amount)
        except Exception as e:
            raise ValueError(f"Transfer failed: {e}")

def integrate_with_existing_vm(vm_instance):
    """
    Example of how to integrate RestrictedPython with your existing VM
    
    Args:
        vm_instance: Your existing StellarisVM instance
    """
    
    # Create the enhancement
    enhancement = RestrictedVMEnhancement(vm_instance)
    
    # Example: Override the deploy_contract method
    original_deploy = vm_instance.deploy_contract
    
    def enhanced_deploy_contract(code: str, deployer: str, constructor_args=None, gas_limit=1000000):
        """Enhanced deploy_contract that uses RestrictedPython"""
        
        # Generate contract address (use your existing logic)
        import hashlib
        import time
        contract_address = hashlib.sha256(
            f"{deployer}{code}{time.time()}".encode()
        ).hexdigest()[:40]
        
        try:
            # Compile with RestrictedPython
            compiled_code = enhancement.compile_contract_secure(code, contract_address)
            
            # Execute in restricted environment
            env = enhancement.execute_contract_secure(compiled_code, contract_address)
            
            # Continue with your existing deployment logic...
            # (Find contract class, create instance, etc.)
            
            print(f"Contract {contract_address} deployed with RestrictedPython security")
            return contract_address
            
        except Exception as e:
            raise Exception(f"Secure deployment failed: {e}")
    
    # Replace the method
    vm_instance.deploy_contract_secure = enhanced_deploy_contract
    
    return enhancement

# Example usage
def example_usage():
    """Example of how to use the RestrictedPython enhancement"""
    
    # Assuming you have your existing VM
    # from stellaris.svm.vm import StellarisVM
    # vm = StellarisVM()
    
    # For demo purposes, create a mock VM
    class MockVM:
        def __init__(self):
            self.contracts = {}
            self.balances = {"deployer": Decimal('1000')}
        
        def get_balance(self, address):
            return self.balances.get(address, Decimal('0'))
        
        def get_contract_storage(self, contract_address, key):
            if contract_address in self.contracts:
                return self.contracts[contract_address].get(key)
            return None
        
        def set_contract_storage(self, contract_address, key, value):
            if contract_address not in self.contracts:
                self.contracts[contract_address] = {}
            self.contracts[contract_address][key] = value
        
        def transfer(self, from_addr, to_addr, amount):
            if self.get_balance(from_addr) >= amount:
                self.balances[from_addr] = self.get_balance(from_addr) - amount
                self.balances[to_addr] = self.get_balance(to_addr) + amount
                return True
            raise ValueError("Insufficient balance")
    
    # Create mock VM and enhance it
    vm = MockVM()
    enhancement = integrate_with_existing_vm(vm)
    
    print("RestrictedPython integration complete!")
    print("Your VM now has enhanced security for smart contract execution.")
    
    # Test with a simple contract
    simple_contract = '''
def get_message():
    return "Hello from restricted contract!"

def store_data(key, value):
    storage[key] = value
    return f"Stored {value} at {key}"
'''
    
    try:
        compiled = enhancement.compile_contract_secure(simple_contract, "test_contract")
        env = enhancement.execute_contract_secure(compiled, "test_contract_addr")
        
        # Test function calls
        result = env['get_message']()
        print(f"Contract function result: {result}")
        
        result = env['store_data']("test_key", "test_value")
        print(f"Storage operation result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    example_usage()
