"""
BPF Contract representation and management with Solidity support
"""

import hashlib
from typing import Dict, Any, Optional, List
from decimal import Decimal
from .exceptions import BPFValidationError
from .solidity_abi import SolidityABI

class BPFContract:
    """Represents a BPF smart contract with EVM/Solidity compatibility"""
    
    def __init__(self, 
                 bytecode: bytes,
                 abi: Dict[str, Any],
                 creator: str,
                 initial_state: Optional[Dict[str, Any]] = None,
                 gas_limit: int = 100000,
                 contract_type: str = 'bpf'):
        """
        Initialize a BPF contract
        
        Args:
            bytecode: The BPF bytecode or EVM bytecode
            abi: Contract ABI (Application Binary Interface)
            creator: Address of the contract creator
            initial_state: Initial contract state
            gas_limit: Maximum gas limit for execution
            contract_type: Type of contract ('bpf' or 'evm')
        """
        self.bytecode = bytecode
        self.abi = abi
        self.creator = creator
        self.state = initial_state or {}
        self.gas_limit = gas_limit
        self.contract_type = contract_type
        self.address = self._compute_address()
        
        # Solidity ABI handler
        self.solidity_abi = SolidityABI()
        
        # Auto-detect contract type from ABI if not specified
        if contract_type == 'bpf' and self.solidity_abi.is_solidity_abi(abi):
            self.contract_type = 'evm'
        
        # Validate contract on creation
        self._validate()
    
    def _compute_address(self) -> str:
        """Compute contract address from bytecode and creator"""
        content = self.bytecode + self.creator.encode('utf-8')
        return hashlib.sha256(content).hexdigest()
    
    def _validate(self):
        """Validate contract bytecode and structure"""
        if not self.bytecode:
            raise BPFValidationError("Empty contract bytecode")
        
        if len(self.bytecode) > 1024 * 1024:  # 1MB limit
            raise BPFValidationError("Contract bytecode too large")
        
        if not self.abi:
            raise BPFValidationError("Contract ABI required")
        
        if not isinstance(self.abi, (dict, list)):
            raise BPFValidationError("Invalid ABI format")
        
        # Validate based on contract type
        if self.contract_type == 'bpf':
            if isinstance(self.abi, dict) and 'functions' not in self.abi:
                raise BPFValidationError("BPF ABI must contain functions")
        elif self.contract_type == 'evm':
            # EVM/Solidity ABI validation
            if not self.solidity_abi.is_solidity_abi(self.abi):
                raise BPFValidationError("Invalid Solidity ABI format")
    
    def is_solidity_contract(self) -> bool:
        """Check if this is a Solidity contract"""
        return self.contract_type == 'evm'
    
    def get_function_names(self) -> List[str]:
        """Get list of contract function names"""
        if self.contract_type == 'evm':
            # Handle Solidity ABI format
            if isinstance(self.abi, list):
                return [item['name'] for item in self.abi if item.get('type') == 'function']
            elif isinstance(self.abi, dict) and 'abi' in self.abi:
                return [item['name'] for item in self.abi['abi'] if item.get('type') == 'function']
        
        # Handle BPF ABI format
        return list(self.abi.get('functions', {}).keys())
    
    def has_function(self, function_name: str) -> bool:
        """Check if contract has a specific function"""
        return function_name in self.get_function_names()
    
    def get_function_signature(self, function_name: str) -> Dict[str, Any]:
        """Get function signature from ABI"""
        if self.contract_type == 'evm':
            return self.solidity_abi._get_function_abi(function_name, self.abi)
        
        # BPF format
        functions = self.abi.get('functions', {})
        if function_name not in functions:
            raise BPFValidationError(f"Function '{function_name}' not found in contract")
        return functions[function_name]
    
    def encode_function_call(self, function_name: str, args: List[Any]) -> bytes:
        """Encode function call data (for Solidity contracts)"""
        if self.contract_type == 'evm':
            return self.solidity_abi.encode_function_call(function_name, self.abi, args)
        else:
            # For BPF contracts, we'll use a simple encoding
            import json
            call_data = {
                'function': function_name,
                'args': args
            }
            return json.dumps(call_data).encode('utf-8')
    
    def decode_function_output(self, data: bytes, function_name: str) -> List[Any]:
        """Decode function output data (for Solidity contracts)"""
        if self.contract_type == 'evm':
            return self.solidity_abi.decode_function_output(data, self.abi, function_name)
        else:
            # For BPF contracts, assume JSON-encoded output
            import json
            try:
                return json.loads(data.decode('utf-8'))
            except:
                return [data.decode('utf-8', errors='ignore')]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to dictionary for storage"""
        return {
            'address': self.address,
            'bytecode': self.bytecode.hex(),
            'abi': self.abi,
            'creator': self.creator,
            'state': self.state,
            'gas_limit': self.gas_limit,
            'contract_type': self.contract_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BPFContract':
        """Create contract from dictionary"""
        contract = cls(
            bytecode=bytes.fromhex(data['bytecode']),
            abi=data['abi'],
            creator=data['creator'],
            initial_state=data.get('state', {}),
            gas_limit=data.get('gas_limit', 100000),
            contract_type=data.get('contract_type', 'bpf')
        )
        contract.address = data['address']
        return contract
    
    def __str__(self):
        return f"BPFContract(address={self.address[:16]}..., creator={self.creator[:16]}..., type={self.contract_type})"
    
    def __repr__(self):
        return self.__str__()