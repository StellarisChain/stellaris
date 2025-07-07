"""
BPF Contract representation and management
"""

import hashlib
from typing import Dict, Any, Optional, List
from decimal import Decimal
from .exceptions import BPFValidationError

class BPFContract:
    """Represents a BPF smart contract"""
    
    def __init__(self, 
                 bytecode: bytes,
                 abi: Dict[str, Any],
                 creator: str,
                 initial_state: Optional[Dict[str, Any]] = None,
                 gas_limit: int = 100000):
        """
        Initialize a BPF contract
        
        Args:
            bytecode: The BPF bytecode
            abi: Contract ABI (Application Binary Interface)
            creator: Address of the contract creator
            initial_state: Initial contract state
            gas_limit: Maximum gas limit for execution
        """
        self.bytecode = bytecode
        self.abi = abi
        self.creator = creator
        self.state = initial_state or {}
        self.gas_limit = gas_limit
        self.address = self._compute_address()
        
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
        
        if not isinstance(self.abi, dict):
            raise BPFValidationError("Invalid ABI format")
        
        if 'functions' not in self.abi:
            raise BPFValidationError("ABI must contain functions")
    
    def get_function_names(self) -> List[str]:
        """Get list of contract function names"""
        return list(self.abi.get('functions', {}).keys())
    
    def has_function(self, function_name: str) -> bool:
        """Check if contract has a specific function"""
        return function_name in self.abi.get('functions', {})
    
    def get_function_signature(self, function_name: str) -> Dict[str, Any]:
        """Get function signature from ABI"""
        functions = self.abi.get('functions', {})
        if function_name not in functions:
            raise BPFValidationError(f"Function '{function_name}' not found in contract")
        return functions[function_name]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to dictionary for storage"""
        return {
            'address': self.address,
            'bytecode': self.bytecode.hex(),
            'abi': self.abi,
            'creator': self.creator,
            'state': self.state,
            'gas_limit': self.gas_limit
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BPFContract':
        """Create contract from dictionary"""
        contract = cls(
            bytecode=bytes.fromhex(data['bytecode']),
            abi=data['abi'],
            creator=data['creator'],
            initial_state=data.get('state', {}),
            gas_limit=data.get('gas_limit', 100000)
        )
        contract.address = data['address']
        return contract
    
    def __str__(self):
        return f"BPFContract(address={self.address[:16]}..., creator={self.creator[:16]}...)"
    
    def __repr__(self):
        return self.__str__()