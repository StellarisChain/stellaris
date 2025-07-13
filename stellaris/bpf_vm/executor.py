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
                       gas_limit: int = 100000, contract_type: str = 'bpf') -> BPFContract:
        """
        Deploy a new BPF or EVM contract
        
        Args:
            bytecode: Contract bytecode
            abi: Contract ABI
            creator: Address of contract creator
            initial_state: Initial contract state
            gas_limit: Gas limit for deployment
            contract_type: Type of contract ('bpf' or 'evm')
            
        Returns:
            Deployed contract instance
        """
        # Create contract instance
        contract = BPFContract(
            bytecode=bytecode,
            abi=abi,
            creator=creator,
            initial_state=initial_state,
            gas_limit=gas_limit,
            contract_type=contract_type
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
        Call a contract function (BPF or EVM)
        
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
        
        # Set gas limit
        if gas_limit is None:
            gas_limit = contract.gas_limit
        
        # Execute based on contract type
        if contract.is_solidity_contract():
            return self._call_evm_contract(contract, function_name, args, caller, gas_limit)
        else:
            return self._call_bpf_contract(contract, function_name, args, caller, gas_limit)
    
    def _call_evm_contract(self, contract: BPFContract, function_name: str, 
                          args: List[Any], caller: str, gas_limit: int) -> Tuple[Any, int]:
        """Call EVM/Solidity contract function"""
        # Encode function call
        call_data = contract.encode_function_call(function_name, args)
        
        # Create VM instance
        vm = BPFVirtualMachine(gas_limit=gas_limit)
        
        # Execute EVM bytecode
        try:
            result = vm.execute(contract.bytecode, call_data, evm_mode=True)
            return_data = vm.get_evm_return_data()
            
            # Decode return data
            if return_data:
                decoded_result = contract.decode_function_output(return_data, function_name)
                return decoded_result, vm.gas_used
            else:
                return None, vm.gas_used
                
        except Exception as e:
            raise BPFExecutionError(f"EVM contract execution failed: {e}")
    
    def _call_bpf_contract(self, contract: BPFContract, function_name: str, 
                          args: List[Any], caller: str, gas_limit: int) -> Tuple[Any, int]:
        """Call BPF contract function"""
        # Get function signature
        func_sig = contract.get_function_signature(function_name)
        
        # Validate arguments
        expected_inputs = func_sig.get('inputs', [])
        if len(args) != len(expected_inputs):
            raise BPFExecutionError(f"Function '{function_name}' expects {len(expected_inputs)} arguments, got {len(args)}")
        
        # Prepare execution context
        context = {
            'function': function_name,
            'args': args,
            'caller': caller,
            'contract_address': contract.address,
            'contract_state': contract.state.copy()
        }
        
        # Encode input data
        input_data = contract.encode_function_call(function_name, args)
        
        # Create VM instance
        vm = BPFVirtualMachine(gas_limit=gas_limit)
        
        # Execute BPF bytecode
        try:
            result = vm.execute(contract.bytecode, input_data, evm_mode=False)
            
            # For BPF contracts, the result is the return value
            # In a real implementation, you'd want more sophisticated result handling
            return result, vm.gas_used
            
        except Exception as e:
            raise BPFExecutionError(f"BPF contract execution failed: {e}")
        
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
        try:
            # Handle EVM contracts with Solidity ABI
            if contract.contract_type == 'evm':
                return self._execute_evm_contract(contract, context)
            else:
                # Execute BPF contract
                return self._execute_bpf_contract(contract, context)
        except Exception as e:
            raise BPFExecutionError(f"Contract execution failed: {str(e)}")
    
    def _execute_evm_contract(self, contract: BPFContract, context: Dict[str, Any]) -> Any:
        """Execute EVM contract using compatibility layer"""
        # Encode function call using Solidity ABI
        function_name = context['function_name']
        args = context['args']
        
        # Use EVM compatibility layer to execute Solidity bytecode
        from .evm_compat import EVMCompatibilityLayer
        evm_layer = EVMCompatibilityLayer(self.vm)
        
        # Execute the EVM bytecode within BPF VM
        result = evm_layer.execute_function(
            bytecode=contract.bytecode,
            function_name=function_name,
            args=args,
            contract_state=contract.state,
            caller=context['caller'],
            gas_limit=context.get('gas_limit', contract.gas_limit)
        )
        
        # Update contract state
        contract.state.update(result.get('state_changes', {}))
        
        return result
    
    def _execute_bpf_contract(self, contract: BPFContract, context: Dict[str, Any]) -> Any:
        """Execute native BPF contract"""
        # Prepare input data for BPF execution
        input_data = self._prepare_input_data(context)
        
        # Execute the contract bytecode with security checks
        result = self.vm.execute(contract.bytecode, input_data)
        
        # Parse and return the result
        return self._parse_execution_result(result, contract, context)
    
    def _parse_execution_result(self, raw_result: Any, contract: BPFContract, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw BPF execution result into structured format"""
        try:
            if isinstance(raw_result, dict):
                return raw_result
            elif isinstance(raw_result, bytes):
                # Try to decode as JSON
                import json
                try:
                    return json.loads(raw_result.decode('utf-8'))
                except:
                    return {'output': raw_result, 'success': True}
            else:
                return {'output': raw_result, 'success': True}
        except Exception as e:
            return {'output': None, 'success': False, 'error': str(e)}
    
    def _prepare_input_data(self, context: Dict[str, Any]) -> bytes:
        """Prepare input data for BPF execution"""
        import json
        import struct
        
        # Create comprehensive input structure for BPF execution
        input_struct = {
            'caller': context['caller'],
            'function': context['function_name'],
            'args': context['args'],
            'gas_limit': context.get('gas_limit', 100000),
            'timestamp': context.get('timestamp', int(time.time())),
            'block_number': context.get('block_number', 0)
        }
        
        # Convert to optimized binary format for BPF
        try:
            # First, try to create a compact binary representation
            input_json = json.dumps(input_struct, separators=(',', ':'))
            json_bytes = input_json.encode('utf-8')
            
            # Add length prefix for BPF parsing
            length_prefix = struct.pack('<I', len(json_bytes))
            return length_prefix + json_bytes
            
        except Exception:
            # Fallback to simple encoding
            fallback_data = f"{context['function_name']}:{','.join(map(str, context['args']))}"
            return fallback_data.encode('utf-8')
    
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
        Estimate gas needed for contract execution using dry run
        
        Args:
            contract_address: Address of the contract
            function_name: Name of function to call
            args: Function arguments
            caller: Address of the caller
            
        Returns:
            Estimated gas needed
        """
        if contract_address not in self.contracts:
            raise BPFExecutionError(f"Contract not found: {contract_address}")
        
        contract = self.contracts[contract_address]
        
        try:
            # Perform a dry run to get accurate gas estimation
            original_state = contract.state.copy()
            
            # Create estimation context with maximum gas
            estimation_context = {
                'function_name': function_name,
                'args': args,
                'caller': caller,
                'gas_limit': 1000000,  # High limit for estimation
                'dry_run': True
            }
            
            # Execute with gas tracking
            start_gas = 1000000
            result = self._execute_contract_function(contract, estimation_context)
            
            # Restore original state after dry run
            contract.state = original_state
            
            # Calculate gas used
            gas_used = start_gas - result.get('gas_remaining', start_gas)
            
            # Add safety margin (20%)
            estimated_gas = int(gas_used * 1.2)
            
            # Ensure minimum gas levels
            minimum_gas = self._calculate_minimum_gas(contract, function_name, args)
            
            return max(estimated_gas, minimum_gas)
            
        except Exception as e:
            # Fallback to static estimation if dry run fails
            return self._static_gas_estimation(contract, function_name, args)
    
    def _calculate_minimum_gas(self, contract: BPFContract, function_name: str, args: List[Any]) -> int:
        """Calculate minimum gas required for function execution"""
        # Base transaction cost
        base_gas = 21000
        
        # Function call overhead
        call_gas = 3000
        
        # Argument processing cost
        arg_gas = len(args) * 1000
        
        # Contract type specific costs
        if contract.contract_type == 'evm':
            # EVM contracts require more gas for compatibility layer
            evm_overhead = 10000
            return base_gas + call_gas + arg_gas + evm_overhead
        else:
            # Native BPF contracts are more efficient
            return base_gas + call_gas + arg_gas
    
    def _static_gas_estimation(self, contract: BPFContract, function_name: str, args: List[Any]) -> int:
        """Fallback static gas estimation when dry run fails"""
        # Base gas cost
        base_gas = 21000
        
        # Function complexity estimation
        try:
            func_sig = contract.get_function_signature(function_name)
            complexity_gas = len(func_sig.get('inputs', [])) * 2000
        except:
            complexity_gas = 10000  # Default for unknown functions
        
        # State access estimation
        state_gas = len(contract.state) * 200
        
        # Bytecode size factor
        bytecode_gas = len(contract.bytecode) // 100
        
        total_gas = base_gas + complexity_gas + state_gas + bytecode_gas
        
        # Ensure reasonable bounds
        return min(max(total_gas, 25000), 500000)
    
    def reset(self):
        """Reset executor state"""
        self.contracts.clear()
        self.vm.reset()