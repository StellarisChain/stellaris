"""
BPF Contract Transaction for deploying and executing smart contracts
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from stellaris.transactions.transaction import Transaction
from stellaris.transactions.transaction_input import TransactionInput
from stellaris.transactions.transaction_output import TransactionOutput
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256

class BPFContractTransaction(Transaction):
    """Transaction for BPF contract deployment and execution"""
    
    CONTRACT_DEPLOY = 0
    CONTRACT_CALL = 1
    
    def __init__(self, 
                 inputs: List[TransactionInput],
                 outputs: List[TransactionOutput],
                 contract_type: int,
                 contract_data: Dict[str, Any],
                 gas_limit: int = 100000,
                 message: bytes = None):
        """
        Initialize BPF contract transaction
        
        Args:
            inputs: Transaction inputs
            outputs: Transaction outputs
            contract_type: Type of contract operation (deploy/call)
            contract_data: Contract-specific data
            gas_limit: Gas limit for contract execution
            message: Optional message data
        """
        super().__init__(inputs, outputs, message, version=4)  # New version for BPF
        self.contract_type = contract_type
        self.contract_data = contract_data
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.execution_result = None
    
    def hex(self, full: bool = True):
        """Override hex method to include contract data"""
        # Get base transaction hex
        base_hex = super().hex(full=False)
        
        # Add contract-specific data
        contract_hex = self._serialize_contract_data()
        
        if not full:
            return base_hex + contract_hex
        
        # Add signatures if full
        signatures = []
        for tx_input in self.inputs:
            signed = tx_input.get_signature()
            if signed not in signatures:
                signatures.append(signed)
                base_hex += signed
        
        return base_hex + contract_hex
    
    def _serialize_contract_data(self) -> str:
        """Serialize contract data to hex"""
        import json
        
        # Create contract data structure
        contract_info = {
            'type': self.contract_type,
            'data': self.contract_data,
            'gas_limit': self.gas_limit
        }
        
        # Serialize to JSON then to bytes
        contract_json = json.dumps(contract_info, sort_keys=True)
        contract_bytes = contract_json.encode('utf-8')
        
        # Add length prefix
        length_prefix = len(contract_bytes).to_bytes(4, ENDIAN)
        
        return (length_prefix + contract_bytes).hex()
    
    @classmethod
    def from_hex(cls, hexstring: str, check_signatures: bool = True):
        """Create BPF contract transaction from hex string"""
        # First try to parse as regular transaction
        try:
            base_tx = super().from_hex(hexstring, check_signatures)
            
            # Check if this is a BPF contract transaction (version 4)
            if base_tx.version != 4:
                return base_tx
            
            # Extract contract data from the hex string
            # This is a simplified implementation
            # In a full implementation, we'd need to properly parse the hex
            
            # For now, create a basic contract transaction
            contract_tx = cls(
                inputs=base_tx.inputs,
                outputs=base_tx.outputs,
                contract_type=cls.CONTRACT_DEPLOY,
                contract_data={},
                message=base_tx.message
            )
            
            return contract_tx
            
        except Exception as e:
            raise ValueError(f"Invalid BPF contract transaction hex: {e}")
    
    def is_contract_deployment(self) -> bool:
        """Check if this is a contract deployment transaction"""
        return self.contract_type == self.CONTRACT_DEPLOY
    
    def is_contract_call(self) -> bool:
        """Check if this is a contract call transaction"""
        return self.contract_type == self.CONTRACT_CALL
    
    def get_contract_address(self) -> Optional[str]:
        """Get contract address for calls"""
        if self.contract_type == self.CONTRACT_CALL:
            return self.contract_data.get('contract_address')
        return None
    
    def get_function_name(self) -> Optional[str]:
        """Get function name for calls"""
        if self.contract_type == self.CONTRACT_CALL:
            return self.contract_data.get('function_name')
        return None
    
    def get_function_args(self) -> List[Any]:
        """Get function arguments for calls"""
        if self.contract_type == self.CONTRACT_CALL:
            return self.contract_data.get('args', [])
        return []
    
    def get_contract_bytecode(self) -> Optional[bytes]:
        """Get contract bytecode for deployment"""
        if self.contract_type == self.CONTRACT_DEPLOY:
            bytecode_hex = self.contract_data.get('bytecode')
            if bytecode_hex:
                return bytes.fromhex(bytecode_hex)
        return None
    
    def get_contract_abi(self) -> Optional[Dict[str, Any]]:
        """Get contract ABI for deployment"""
        if self.contract_type == self.CONTRACT_DEPLOY:
            return self.contract_data.get('abi')
        return None
    
    async def verify(self, check_double_spend: bool = True) -> bool:
        """Verify BPF contract transaction"""
        # First do standard transaction verification
        if not await super().verify(check_double_spend):
            return False
        
        # Additional BPF-specific validation
        if not self._validate_contract_data():
            return False
        
        # Validate gas limit
        if self.gas_limit <= 0 or self.gas_limit > 1000000:
            return False
        
        return True
    
    def _validate_contract_data(self) -> bool:
        """Validate contract-specific data"""
        if self.contract_type == self.CONTRACT_DEPLOY:
            # Validate deployment data
            if not self.contract_data.get('bytecode'):
                return False
            if not self.contract_data.get('abi'):
                return False
            
            # Validate bytecode format
            try:
                bytecode = bytes.fromhex(self.contract_data['bytecode'])
                if len(bytecode) == 0 or len(bytecode) > 1024 * 1024:  # 1MB limit
                    return False
            except ValueError:
                return False
            
        elif self.contract_type == self.CONTRACT_CALL:
            # Validate call data
            if not self.contract_data.get('contract_address'):
                return False
            if not self.contract_data.get('function_name'):
                return False
            
        else:
            return False
        
        return True
    
    def __str__(self):
        contract_type_str = "Deploy" if self.is_contract_deployment() else "Call"
        return f"BPFContractTransaction({contract_type_str}, gas_limit={self.gas_limit})"
    
    def __repr__(self):
        return self.__str__()