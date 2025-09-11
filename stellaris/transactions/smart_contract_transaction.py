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
        self.gas_limit = int(gas_limit) if gas_limit else 100000
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
        # Use the parent class hex method for base transaction structure
        # which includes proper signature handling
        base_hex = super().hex(full)
        
        # Add smart contract specific data
        contract_data = {
            'operation_type': self.operation_type,
            'contract_address': self.contract_address,
            'contract_code': self.contract_code,
            'method_name': self.method_name,
            'method_args': self.method_args,
            'gas_limit': self.gas_limit
        }
        
        # Serialize contract data with Decimal support
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return {'__decimal__': str(obj)}
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        contract_data_json = json.dumps(contract_data, separators=(',', ':'), default=decimal_default)
        contract_data_bytes = contract_data_json.encode('utf-8')
        
        # Add length prefix and contract data
        contract_hex = (
            len(contract_data_bytes).to_bytes(4, ENDIAN).hex() +
            contract_data_bytes.hex()
        )
        
        return ('0x' if prefix else '') + base_hex + contract_hex
    
    @classmethod
    async def from_hex(cls, hex_string: str, check_signatures: bool = True):
        """Create transaction from hex string"""
        import json
        from io import BytesIO
        
        # Remove 0x prefix if present
        clean_hex = hex_string[2:] if hex_string.startswith('0x') else hex_string
        
        try:
            # First we need to separate the base transaction hex from the contract data
            hex_bytes = bytes.fromhex(clean_hex)
            
            # Find the contract data by looking for the length prefix at the end
            # The contract data format is: [4-byte length][contract data JSON]
            contract_data = None
            base_transaction_bytes = hex_bytes
            
            # Try to find contract data at the end
            for i in range(len(hex_bytes) - 4, 0, -1):
                try:
                    potential_len = int.from_bytes(hex_bytes[i:i+4], ENDIAN)
                    if potential_len > 0 and i + 4 + potential_len == len(hex_bytes):
                        # This looks like a valid contract data length at the end
                        contract_data_bytes = hex_bytes[i+4:i+4+potential_len]
                        contract_data_str = contract_data_bytes.decode('utf-8')
                        if contract_data_str.startswith('{') and contract_data_str.endswith('}'):
                            # Found valid JSON contract data
                            def decimal_hook(dct):
                                for key, value in dct.items():
                                    if isinstance(value, dict) and '__decimal__' in value:
                                        dct[key] = Decimal(value['__decimal__'])
                                    elif isinstance(value, list):
                                        dct[key] = [Decimal(item['__decimal__']) if isinstance(item, dict) and '__decimal__' in item else item for item in value]
                                return dct
                            
                            contract_data = json.loads(contract_data_str, object_hook=decimal_hook)
                            # Remove contract data from base transaction
                            base_transaction_bytes = hex_bytes[:i]
                            break
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
            
            if contract_data is None:
                raise ValueError("Could not parse smart contract data from hex")
            
            # Now parse the base transaction manually (since it's version 4)
            tx_bytes = BytesIO(base_transaction_bytes)
            
            # Parse version
            version = int.from_bytes(tx_bytes.read(1), ENDIAN)
            if version != 4:
                raise ValueError(f"Expected version 4, got {version}")
            
            # Parse inputs (just tx_hash and index, signatures come later)
            inputs_count = int.from_bytes(tx_bytes.read(1), ENDIAN)
            inputs = []
            
            for i in range(inputs_count):
                tx_hex = tx_bytes.read(32).hex()
                tx_index = int.from_bytes(tx_bytes.read(1), ENDIAN)
                inputs.append(TransactionInput(tx_hex, index=tx_index))
            
            # Parse outputs
            outputs_count = int.from_bytes(tx_bytes.read(1), ENDIAN)
            outputs = []
            
            for i in range(outputs_count):
                # Read address (33 bytes for version > 1)
                pubkey_bytes = tx_bytes.read(33)
                from stellaris.utils.general import bytes_to_string
                address = bytes_to_string(pubkey_bytes)
                
                # Read amount length and amount
                amount_length = int.from_bytes(tx_bytes.read(1), ENDIAN)
                amount_int = int.from_bytes(tx_bytes.read(amount_length), ENDIAN)
                amount = Decimal(str(amount_int)) / Decimal('1000000')
                
                outputs.append(TransactionOutput(address, amount))
            
            # Parse message
            message_specifier = int.from_bytes(tx_bytes.read(1), ENDIAN)
            if message_specifier == 1:
                if version <= 2:
                    message_length = int.from_bytes(tx_bytes.read(1), ENDIAN)
                else:
                    message_length = int.from_bytes(tx_bytes.read(2), ENDIAN)
                if message_length > 0:
                    message = tx_bytes.read(message_length)
                else:
                    message = None
            else:
                message = None
            
            # Parse signatures (similar to Transaction.from_hex)
            signatures = []
            while True:
                try:
                    sig_r = int.from_bytes(tx_bytes.read(32), ENDIAN)
                    sig_s = int.from_bytes(tx_bytes.read(32), ENDIAN)
                    if sig_r == 0:
                        break
                    signatures.append((sig_r, sig_s))
                except:
                    break
            
            # Assign signatures to inputs (similar logic as Transaction.from_hex)
            if len(signatures) == 1:
                for tx_input in inputs:
                    tx_input.signed = signatures[0]
            elif len(inputs) == len(signatures):
                for i, tx_input in enumerate(inputs):
                    tx_input.signed = signatures[i]
            
            # Create smart contract transaction with the parsed data
            sc_tx = cls(
                inputs=inputs,
                outputs=outputs,
                operation_type=contract_data.get('operation_type', cls.OPERATION_DEPLOY),
                contract_address=contract_data.get('contract_address', ''),
                contract_code=contract_data.get('contract_code', ''),
                method_name=contract_data.get('method_name', ''),
                method_args=contract_data.get('method_args', []),
                gas_limit=int(contract_data.get('gas_limit', 100000))
            )
            
            # Set message if present
            if message:
                sc_tx.message = message
            
            return sc_tx
            
        except Exception as e:
            raise ValueError(f"Invalid smart contract transaction hex: {e}")
    
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
    
    def _verify_outputs(self):
        """Override output verification for smart contract transactions"""
        # Smart contract transactions may have no outputs (for deployment with no funding)
        # or they may have outputs for funding/change
        if not self.outputs:
            # Empty outputs are valid for smart contract transactions
            return True
        else:
            # If outputs exist, they must all be valid
            return all(tx_output.verify() for tx_output in self.outputs)
