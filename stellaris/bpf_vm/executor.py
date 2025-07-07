"""
BPF Executor for managing contract execution within the blockchain
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from .vm import BPFVirtualMachine
from .contract import BPFContract
from .exceptions import BPFExecutionError, BPFSecurityError, BPFResourceError

class BPFExecutor:
    """Manages BPF contract execution within the blockchain context"""
    
    def __init__(self, contracts_storage: Dict[str, BPFContract] = None):
        """
        Initialize BPF executor
        
        Args:
            contracts_storage: Storage for deployed contracts
        """
        self.contracts = contracts_storage or {}
        self.vm = BPFVirtualMachine()
    
    def deploy_contract(self, bytecode: bytes, abi: Dict[str, Any], creator: str, 
                       initial_state: Optional[Dict[str, Any]] = None,
                       gas_limit: int = 100000) -> BPFContract:
        """
        Deploy a new BPF contract
        
        Args:
            bytecode: Contract bytecode
            abi: Contract ABI
            creator: Address of contract creator
            initial_state: Initial contract state
            gas_limit: Gas limit for deployment
            
        Returns:
            Deployed contract instance
        """
        # Create contract instance
        contract = BPFContract(
            bytecode=bytecode,
            abi=abi,
            creator=creator,
            initial_state=initial_state,
            gas_limit=gas_limit
        )
        
        # Validate contract can be deployed
        self._validate_deployment(contract)
        
        # Store contract
        self.contracts[contract.address] = contract
        
        return contract
    
    def _validate_deployment(self, contract: BPFContract):
        """Validate contract can be safely deployed"""
        # Check if contract address already exists
        if contract.address in self.contracts:
            raise BPFExecutionError(f"Contract already exists at address {contract.address}")
        
        # Validate bytecode by attempting to load it
        try:
            # Create a temporary VM to validate bytecode
            temp_vm = BPFVirtualMachine(gas_limit=1000)
            # Just validate the bytecode format, don't execute
            if len(contract.bytecode) % 8 != 0:
                raise BPFExecutionError("Invalid bytecode format")
        except Exception as e:
            raise BPFExecutionError(f"Invalid contract bytecode: {e}")
    
    def call_contract(self, contract_address: str, function_name: str, 
                     args: List[Any], caller: str, gas_limit: Optional[int] = None) -> Tuple[Any, int]:
        """
        Call a contract function
        
        Args:
            contract_address: Address of the contract
            function_name: Name of function to call
            args: Function arguments
            caller: Address of the caller
            gas_limit: Gas limit for execution
            
        Returns:
            Tuple of (result, gas_used)
        """
        # Get contract
        if contract_address not in self.contracts:
            raise BPFExecutionError(f"Contract not found: {contract_address}")
        
        contract = self.contracts[contract_address]
        
        # Validate function exists
        if not contract.has_function(function_name):
            raise BPFExecutionError(f"Function '{function_name}' not found in contract")
        
        # Get function signature
        func_sig = contract.get_function_signature(function_name)
        
        # Validate arguments
        self._validate_function_args(func_sig, args)
        
        # Setup VM for execution
        vm_gas_limit = gas_limit or contract.gas_limit
        self.vm = BPFVirtualMachine(gas_limit=vm_gas_limit)
        
        # Prepare execution context
        context = {
            'caller': caller,
            'contract_address': contract_address,
            'function_name': function_name,
            'args': args,
            'state': contract.state.copy()
        }
        
        # Execute contract
        try:
            result = self._execute_contract_function(contract, context)
            
            # Update contract state if execution succeeded
            contract.state.update(context['state'])
            
            return result, self.vm.gas_used
            
        except Exception as e:
            # Don't update state on execution failure
            raise BPFExecutionError(f"Contract execution failed: {e}")
    
    def _validate_function_args(self, func_sig: Dict[str, Any], args: List[Any]):
        """Validate function arguments against signature"""
        expected_args = func_sig.get('inputs', [])
        
        if len(args) != len(expected_args):
            raise BPFExecutionError(f"Wrong number of arguments: expected {len(expected_args)}, got {len(args)}")
        
        # Basic type validation
        for i, (arg, expected) in enumerate(zip(args, expected_args)):
            arg_type = expected.get('type', 'unknown')
            if arg_type == 'uint256' and not isinstance(arg, int):
                raise BPFExecutionError(f"Argument {i} expected uint256, got {type(arg)}")
            elif arg_type == 'string' and not isinstance(arg, str):
                raise BPFExecutionError(f"Argument {i} expected string, got {type(arg)}")
            elif arg_type == 'bytes' and not isinstance(arg, bytes):
                raise BPFExecutionError(f"Argument {i} expected bytes, got {type(arg)}")
    
    def _execute_contract_function(self, contract: BPFContract, context: Dict[str, Any]) -> Any:
        """Execute a contract function with context"""
        # For now, implement a simple execution model
        # In a full implementation, this would compile the function call
        # into BPF bytecode and execute it
        
        # Prepare input data (simplified)
        input_data = self._prepare_input_data(context)
        
        # Execute the contract bytecode
        result = self.vm.execute(contract.bytecode, input_data)
        
        return result
    
    def _prepare_input_data(self, context: Dict[str, Any]) -> bytes:
        """Prepare input data for BPF execution"""
        # Simple serialization of context
        # In a full implementation, this would use a proper ABI encoder
        import json
        
        # Create a simplified input structure
        input_struct = {
            'caller': context['caller'],
            'function': context['function_name'],
            'args': context['args']
        }
        
        # Convert to bytes (simplified)
        input_json = json.dumps(input_struct)
        return input_json.encode('utf-8')
    
    def get_contract(self, address: str) -> Optional[BPFContract]:
        """Get contract by address"""
        return self.contracts.get(address)
    
    def get_all_contracts(self) -> Dict[str, BPFContract]:
        """Get all deployed contracts"""
        return self.contracts.copy()
    
    def get_contract_state(self, address: str) -> Optional[Dict[str, Any]]:
        """Get contract state"""
        contract = self.contracts.get(address)
        if contract:
            return contract.state.copy()
        return None
    
    def estimate_gas(self, contract_address: str, function_name: str, 
                     args: List[Any], caller: str) -> int:
        """
        Estimate gas needed for contract execution
        
        Args:
            contract_address: Address of the contract
            function_name: Name of function to call
            args: Function arguments
            caller: Address of the caller
            
        Returns:
            Estimated gas needed
        """
        # Simple gas estimation
        # In a full implementation, this would do a dry run
        
        if contract_address not in self.contracts:
            raise BPFExecutionError(f"Contract not found: {contract_address}")
        
        contract = self.contracts[contract_address]
        
        # Base gas cost
        base_gas = 21000
        
        # Add gas for function complexity
        func_sig = contract.get_function_signature(function_name)
        complexity_gas = len(func_sig.get('inputs', [])) * 1000
        
        # Add gas for state access
        state_gas = len(contract.state) * 100
        
        return base_gas + complexity_gas + state_gas
    
    def reset(self):
        """Reset executor state"""
        self.contracts.clear()
        self.vm.reset()