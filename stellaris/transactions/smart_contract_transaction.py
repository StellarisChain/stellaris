"""
Smart Contract Transaction for Stellaris blockchain
Handles contract deployment and method calls
"""

import struct
from decimal import Decimal
from io import BytesIO
from typing import List, Optional, Dict, Any
import json

from stellaris.transactions import Transaction, TransactionInput, TransactionOutput
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256


class SmartContractTransaction(Transaction):
    """Transaction for smart contract operations"""
    
    OPERATION_DEPLOY = 0x01
    OPERATION_CALL = 0x02
    
    def __init__(self, inputs: List[TransactionInput], outputs: List[TransactionOutput],
                 operation_type: int, contract_address: str = None, 
                 contract_code: str = None, method_name: str = None,
                 method_args: List[Any] = None, gas_limit: int = 100000,
                 message: bytes = None, version: int = 4):
        """
        Initialize smart contract transaction
        
        Args:
            inputs: Transaction inputs
            outputs: Transaction outputs  
            operation_type: OPERATION_DEPLOY or OPERATION_CALL
            contract_address: Address of contract (for calls)
            contract_code: Contract source code (for deployment)
            method_name: Method to call (for calls)
            method_args: Arguments for method call
            gas_limit: Gas limit for execution
            message: Optional message
            version: Transaction version (4 for smart contracts)
        """
        # Set version to 4 for smart contracts and bypass the parent validation
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.message = message
        self._hex = None
        self.fees = None
        self.tx_hash = None
        
        self.operation_type = operation_type
        self.contract_address = contract_address or ""
        self.contract_code = contract_code or ""
        self.method_name = method_name or ""
        self.method_args = method_args or []
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.execution_result = None
        self.execution_error = None
        
        # Validate operation
        if operation_type == self.OPERATION_DEPLOY:
            if not contract_code:
                raise ValueError("Contract code required for deployment")
        elif operation_type == self.OPERATION_CALL:
            if not contract_address or not method_name:
                raise ValueError("Contract address and method name required for call")
        else:
            raise ValueError(f"Invalid operation type: {operation_type}")
    
    def hex(self, full: bool = True, prefix = False):
        """Generate hex representation of transaction"""
        # Basic transaction structure for smart contracts
        inputs_hex = ''.join(tx_input.tobytes().hex() for tx_input in self.inputs)
        outputs_hex = ''.join(tx_output.tobytes().hex() for tx_output in self.outputs)
        
        message_hex = ''
        if self.message:
            message_hex = len(self.message).to_bytes(4, ENDIAN).hex() + self.message.hex()
        else:
            message_hex = (0).to_bytes(4, ENDIAN).hex()
        
        # Base transaction hex
        base_hex = ''.join([
            self.version.to_bytes(1, ENDIAN).hex(),
            len(self.inputs).to_bytes(1, ENDIAN).hex(),
            inputs_hex,
            len(self.outputs).to_bytes(1, ENDIAN).hex(), 
            outputs_hex,
            message_hex
        ])
        
        # Add smart contract specific data
        contract_data = {
            'operation_type': self.operation_type,
            'contract_address': self.contract_address,
            'contract_code': self.contract_code,
            'method_name': self.method_name,
            'method_args': self.method_args,
            'gas_limit': self.gas_limit
        }
        
        # Serialize contract data
        contract_data_json = json.dumps(contract_data, separators=(',', ':'))
        contract_data_bytes = contract_data_json.encode('utf-8')
        
        # Add length prefix and contract data
        contract_hex = (
            len(contract_data_bytes).to_bytes(4, ENDIAN).hex() +
            contract_data_bytes.hex()
        )
        
        return '0x' if prefix else '' + base_hex + contract_hex
    
    @classmethod
    async def from_hex(cls, hex_string: str, check_signatures: bool = True):
        """Create transaction from hex string"""
        import json
        from io import BytesIO
        
        # Remove 0x prefix if present
        clean_hex = hex_string[2:] if hex_string.startswith('0x') else hex_string
        
        # Extract basic transaction data
        hex_bytes = bytes.fromhex(clean_hex)
        data_stream = BytesIO(hex_bytes)
        
        try:
            # Parse regular transaction data first
            version = int.from_bytes(data_stream.read(1), ENDIAN)
            
            # Skip input/output counts and data (simplified parsing)
            input_count = int.from_bytes(data_stream.read(1), ENDIAN)
            for _ in range(input_count):
                # Skip input data (32 bytes hash + 1 byte index + variable signature)
                data_stream.read(32)  # tx_hash
                data_stream.read(1)   # index
                sig_len = int.from_bytes(data_stream.read(1), ENDIAN)
                data_stream.read(sig_len)  # signature
            
            output_count = int.from_bytes(data_stream.read(1), ENDIAN)
            for _ in range(output_count):
                # Skip output data (8 bytes amount + variable address)
                data_stream.read(8)  # amount
                addr_len = int.from_bytes(data_stream.read(1), ENDIAN)
                data_stream.read(addr_len)  # address
            
            # Skip message length and message
            msg_len = int.from_bytes(data_stream.read(4), ENDIAN)
            data_stream.read(msg_len)
            
            # Parse smart contract data
            contract_data_len = int.from_bytes(data_stream.read(4), ENDIAN)
            contract_data_bytes = data_stream.read(contract_data_len)
            contract_data = json.loads(contract_data_bytes.decode('utf-8'))
            
            # Create smart contract transaction
            sc_tx = cls(
                inputs=[],  # Simplified for now
                outputs=[],  # Simplified for now
                operation_type=contract_data.get('operation_type', cls.OPERATION_DEPLOY),
                contract_address=contract_data.get('contract_address', ''),
                contract_code=contract_data.get('contract_code', ''),
                method_name=contract_data.get('method_name', ''),
                method_args=contract_data.get('method_args', []),
                gas_limit=contract_data.get('gas_limit', 100000)
            )
            
            sc_tx._hex = hex_string
            return sc_tx
            
        except Exception as e:
            # Fallback to basic transaction for compatibility
            sc_tx = cls(
                inputs=[],
                outputs=[],
                operation_type=cls.OPERATION_DEPLOY,
                contract_code="",
                gas_limit=100000
            )
            sc_tx._hex = hex_string
            return sc_tx
    
    def hash(self) -> str:
        """Get transaction hash"""
        if self.tx_hash is None:
            self.tx_hash = sha256(self.hex())
        return self.tx_hash
    
    def get_contract_deployment_address(self) -> str:
        """Get the address where contract will be deployed"""
        if self.operation_type != self.OPERATION_DEPLOY:
            raise ValueError("Only deployment transactions have deployment addresses")
        
        # Use transaction hash and sender to generate deterministic address
        # For now use a simplified approach since get_address is async
        sender = "deployer_address"  # This will be set properly during execution
        return sha256(f"{sender}{self.hex()}{self.contract_code}")[:40]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary for JSON serialization"""
        base_dict = {
            'type': 'smart_contract',
            'operation_type': self.operation_type,
            'operation_name': 'deploy' if self.operation_type == self.OPERATION_DEPLOY else 'call',
            'inputs': [inp.to_dict() for inp in self.inputs],
            'outputs': [out.to_dict() for out in self.outputs],
            'gas_limit': self.gas_limit,
            'gas_used': self.gas_used,
            'version': self.version,
            'hash': sha256(self.hex()),
        }
        
        if self.operation_type == self.OPERATION_DEPLOY:
            base_dict.update({
                'contract_code': self.contract_code,
                'deployment_address': self.get_contract_deployment_address()
            })
        else:
            base_dict.update({
                'contract_address': self.contract_address,
                'method_name': self.method_name,
                'method_args': self.method_args
            })
        
        if self.execution_result is not None:
            base_dict['execution_result'] = self.execution_result
        
        if self.execution_error is not None:
            base_dict['execution_error'] = str(self.execution_error)
        
        return base_dict
    
    def calculate_gas_fee(self, gas_price: Decimal = None) -> Decimal:
        """Calculate gas fee based on gas used and current gas price"""
        if gas_price is None:
            # Use default gas price from VM
            gas_price = Decimal('0.000001')  # Default: 1 microtoken per gas unit
        
        return Decimal(str(self.gas_used)) * gas_price
    
    async def get_fees(self):
        """Calculate total transaction fees including gas fees"""
        # First calculate traditional transaction fees (input - output difference)
        traditional_fees = await super().get_fees()
        
        # Add gas fees on top of traditional fees
        gas_fees = self.calculate_gas_fee()
        
        # Total fees = traditional fees + gas fees
        total_fees = traditional_fees + gas_fees
        self.fees = total_fees
        
        return total_fees
    
    def is_deployment(self) -> bool:
        """Check if this is a contract deployment transaction"""
        return self.operation_type == self.OPERATION_DEPLOY
    
    def is_call(self) -> bool:
        """Check if this is a contract call transaction"""
        return self.operation_type == self.OPERATION_CALL
