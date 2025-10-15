"""
Smart Contract Transaction for Stellaris blockchain
Handles contract deployment and method calls with hex-encoded contract code

Production-ready features:
- Hex-encoded contract code for safe transmission and storage
- Comprehensive input validation
- Deterministic deployment address calculation
- Gas limit enforcement
- Secure                 contract_address=contract_data.get('contract_address', ''),
                contract_code=contract_code,  # Already hex-encoded
                method_name=contract_data.get('method_name', ''),
                method_args=contract_data.get('method_args', []),
                gas_limit=int(contract_data.get('gas_limit', 100000)),
                message=base_tx.message if hasattr(base_tx, 'message') else None
            )
            
            logger.debug(f"Parsed {sc_tx._operation_name()} transaction from hex")
            return sc_tx
            
        except Exception as e:
            logger.error(f"Failed to parse smart contract transaction from hex: {e}")
            raise ValueError(f"Invalid smart contract transaction hex: {e}")
    
    def hash(self) -> str:on with Decimal support
"""

import struct
from decimal import Decimal
from io import BytesIO
from typing import List, Optional, Dict, Any
import json
import logging

from stellaris.transactions import Transaction, TransactionInput, TransactionOutput
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256


logger = logging.getLogger(__name__)


class SmartContractTransaction(Transaction):
    """
    Transaction for smart contract operations on Stellaris blockchain.
    
    Features:
    - Deployment transactions (OPERATION_DEPLOY) - creates new contracts
    - Call transactions (OPERATION_CALL) - invokes contract methods
    - Hex-encoded contract code for safe transmission
    - Deterministic deployment addresses
    - Gas metering and limits
    """
    
    OPERATION_DEPLOY = 0x01
    OPERATION_CALL = 0x02
    
    # Production limits
    MAX_CONTRACT_CODE_SIZE = 1_000_000  # 1MB
    MAX_GAS_LIMIT_DEPLOY = 10_000_000   # 10M gas for deployments
    MAX_GAS_LIMIT_CALL = 5_000_000      # 5M gas for calls
    MIN_GAS_LIMIT = 210            # Minimum gas
    
    def __init__(self, inputs: List[TransactionInput], outputs: List[TransactionOutput],
                 operation_type: int, contract_address: str = None, 
                 contract_code: str = None, method_name: str = None,
                 method_args: List[Any] = None, gas_limit: int = 100000,
                 message: bytes = None, version: int = 4):
        """
        Initialize smart contract transaction with comprehensive validation
        
        Args:
            inputs: Transaction inputs (UTXOs to spend)
            outputs: Transaction outputs (recipients and change)
            operation_type: OPERATION_DEPLOY or OPERATION_CALL
            contract_address: Address of contract (for calls) - must be 40 hex chars
            contract_code: Contract source code - will be hex-encoded if not already
            method_name: Method to call (for calls and constructor)
            method_args: Arguments for method call - must be JSON-serializable
            gas_limit: Gas limit for execution - validated against operation type
            message: Optional message bytes
            version: Transaction version (4 for smart contracts)
            
        Raises:
            ValueError: If validation fails for any parameter
        """
        # Set version to 4 for smart contracts and bypass the parent validation
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.message = message
        self._hex = None
        self.fees = None
        self.tx_hash = None
        
        # Validate operation type
        if operation_type not in (self.OPERATION_DEPLOY, self.OPERATION_CALL):
            raise ValueError(f"Invalid operation type: {operation_type}. Must be OPERATION_DEPLOY(0x01) or OPERATION_CALL(0x02)")
        
        self.operation_type = operation_type
        
        # Initialize contract-specific fields with validation
        self.contract_address = self._validate_contract_address(contract_address, operation_type)
        self.contract_code = self._validate_and_encode_contract_code(contract_code, operation_type)
        self.method_name = self._validate_method_name(method_name, operation_type)
        self.method_args = self._validate_method_args(method_args)
        self.gas_limit = self._validate_gas_limit(gas_limit, operation_type)
        
        # Execution result fields (set after execution)
        self.gas_used = 0
        self.execution_result = None
        self.execution_error = None
        
        logger.debug(f"Created {self._operation_name()} transaction with gas_limit={gas_limit}")
    
    def _validate_contract_address(self, address: str, operation_type: int) -> str:
        """Validate contract address based on operation type"""
        if operation_type == self.OPERATION_CALL:
            if not address:
                raise ValueError("Contract address is required for OPERATION_CALL")
            if not isinstance(address, str):
                raise ValueError("Contract address must be a string")
            # Remove 0x prefix if present
            clean_address = address[2:] if address.startswith('0x') else address
            if len(clean_address) != 40:
                raise ValueError(f"Contract address must be 40 hex characters, got {len(clean_address)}")
            # Validate hex format
            try:
                int(clean_address, 16)
            except ValueError:
                raise ValueError("Contract address must be valid hexadecimal")
            return clean_address
        return address or ""
    
    def _validate_and_encode_contract_code(self, code: str, operation_type: int) -> str:
        """Validate and hex-encode contract code if needed"""
        if operation_type == self.OPERATION_DEPLOY:
            if not code:
                raise ValueError("Contract code is required for OPERATION_DEPLOY")
            if not isinstance(code, str):
                raise ValueError("Contract code must be a string")
            
            # Check if already hex-encoded (starts with valid hex and even length)
            is_hex_encoded = False
            try:
                if len(code) % 2 == 0:
                    bytes.fromhex(code)
                    is_hex_encoded = True
            except ValueError:
                is_hex_encoded = False
            
            if is_hex_encoded:
                # Already hex-encoded, validate size
                decoded_size = len(code) // 2
                if decoded_size > self.MAX_CONTRACT_CODE_SIZE:
                    raise ValueError(f"Contract code too large: {decoded_size} bytes (max: {self.MAX_CONTRACT_CODE_SIZE})")
                logger.debug(f"Contract code already hex-encoded ({decoded_size} bytes)")
                return code
            else:
                # Encode to hex
                code_bytes = code.encode('utf-8')
                if len(code_bytes) > self.MAX_CONTRACT_CODE_SIZE:
                    raise ValueError(f"Contract code too large: {len(code_bytes)} bytes (max: {self.MAX_CONTRACT_CODE_SIZE})")
                hex_encoded = code_bytes.hex()
                logger.debug(f"Hex-encoded contract code ({len(code_bytes)} bytes -> {len(hex_encoded)} hex chars)")
                return hex_encoded
        return code or ""
    
    def _validate_method_name(self, method_name: str, operation_type: int) -> str:
        """Validate method name"""
        if operation_type == self.OPERATION_CALL:
            if not method_name:
                raise ValueError("Method name is required for OPERATION_CALL")
            if not isinstance(method_name, str):
                raise ValueError("Method name must be a string")
            if not method_name.strip():
                raise ValueError("Method name cannot be empty or whitespace")
            # Validate method name format (Python identifier)
            if not method_name.replace('_', '').isalnum():
                raise ValueError(f"Invalid method name format: {method_name}")
            if method_name[0].isdigit():
                raise ValueError(f"Method name cannot start with a digit: {method_name}")
        return method_name or ""
    
    def _validate_method_args(self, args: List[Any]) -> List[Any]:
        """Validate and sanitize method arguments"""
        if args is None:
            return []
        if not isinstance(args, list):
            raise ValueError("Method arguments must be a list")
        
        # Validate that arguments are JSON-serializable
        try:
            json.dumps(args, default=self._decimal_serializer)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Method arguments must be JSON-serializable: {e}")
        
        return args
    
    def _validate_gas_limit(self, gas_limit: int, operation_type: int) -> int:
        """Validate gas limit based on operation type"""
        if not isinstance(gas_limit, int):
            try:
                gas_limit = int(gas_limit)
            except (ValueError, TypeError):
                raise ValueError(f"Gas limit must be an integer, got {type(gas_limit)}")
        
        if gas_limit < self.MIN_GAS_LIMIT:
            raise ValueError(f"Gas limit too low: {gas_limit} (min: {self.MIN_GAS_LIMIT})")
        
        if operation_type == self.OPERATION_DEPLOY:
            if gas_limit > self.MAX_GAS_LIMIT_DEPLOY:
                raise ValueError(f"Gas limit too high for deployment: {gas_limit} (max: {self.MAX_GAS_LIMIT_DEPLOY})")
        else:
            if gas_limit > self.MAX_GAS_LIMIT_CALL:
                raise ValueError(f"Gas limit too high for call: {gas_limit} (max: {self.MAX_GAS_LIMIT_CALL})")
        
        return gas_limit
    
    def _operation_name(self) -> str:
        """Get human-readable operation name"""
        return "DEPLOY" if self.operation_type == self.OPERATION_DEPLOY else "CALL"
    
    @staticmethod
    def _decimal_serializer(obj):
        """JSON serializer for Decimal objects"""
        if isinstance(obj, Decimal):
            return {'__decimal__': str(obj)}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @staticmethod
    def _decimal_deserializer(dct):
        """JSON deserializer for Decimal objects"""
        if '__decimal__' in dct:
            return Decimal(dct['__decimal__'])
        return dct
    
    def get_contract_code_decoded(self) -> str:
        """
        Get the decoded contract code as UTF-8 string
        
        Returns:
            Decoded contract source code
        """
        if not self.contract_code:
            return ""
        try:
            # Decode from hex
            code_bytes = bytes.fromhex(self.contract_code)
            return code_bytes.decode('utf-8')
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode contract code: {e}")
            # Fallback: return as-is if it wasn't actually hex-encoded
            return self.contract_code
    
    def hex(self, full: bool = True, prefix = False):
        """
        Generate hex representation of transaction with hex-encoded contract code
        
        Args:
            full: Include full transaction data (including contract data)
            prefix: Add '0x' prefix to hex string
            
        Returns:
            Hex string representation of the transaction
        """
        # Use the parent class hex method for base transaction structure
        # which includes proper signature handling
        base_hex = super().hex(full)
        
        # Only add contract data when full=True
        # This is important because signatures are verified against hex(full=False)
        # which should only include the base transaction without contract data
        if not full:
            return ('0x' if prefix else '') + base_hex
        
        # Add smart contract specific data with hex-encoded contract code
        contract_data = {
            'operation_type': self.operation_type,
            'contract_address': self.contract_address,
            'contract_code_hex': self.contract_code,  # Already hex-encoded
            'method_name': self.method_name,
            'method_args': self.method_args,
            'gas_limit': self.gas_limit
        }
        
        # Serialize contract data with Decimal support
        contract_data_json = json.dumps(contract_data, separators=(',', ':'), default=self._decimal_serializer)
        contract_data_bytes = contract_data_json.encode('utf-8')
        
        # Add length prefix and contract data
        contract_hex = (
            len(contract_data_bytes).to_bytes(4, ENDIAN).hex() +
            contract_data_bytes.hex()
        )
        
        return ('0x' if prefix else '') + base_hex + contract_hex
    
    @classmethod
    async def from_hex(cls, hex_string: str, check_signatures: bool = True):
        """
        Create transaction from hex string with proper hex-encoded contract code handling
        
        Args:
            hex_string: Hex representation of transaction
            check_signatures: Whether to verify signatures
            
        Returns:
            SmartContractTransaction instance
            
        Raises:
            ValueError: If hex string is invalid or malformed
        """
        # Remove 0x prefix if present
        clean_hex = hex_string[2:] if hex_string.startswith('0x') else hex_string
        
        try:
            hex_bytes = bytes.fromhex(clean_hex)
            
            # Find and parse contract data at the end FIRST
            contract_data = None
            base_transaction_hex = clean_hex
            
            # Try to find contract data by looking for length prefix at the end
            # The contract data is appended as: [4-byte length][JSON data]
            # We need to scan from the end backwards to find this pattern
            # Note: Contract code can be large (up to 50KB), so we need to scan far back
            found_contract_data = False
            scan_limit = max(0, len(hex_bytes) - 60000)  # Scan up to 60KB back
            for i in range(len(hex_bytes) - 4, scan_limit, -1):
                try:
                    potential_len = int.from_bytes(hex_bytes[i:i+4], ENDIAN)
                    # Reasonable length check (between 50 bytes and 50KB)
                    if 50 <= potential_len <= 50000 and i + 4 + potential_len == len(hex_bytes):
                        # This looks like valid contract data length
                        contract_data_bytes = hex_bytes[i+4:i+4+potential_len]
                        try:
                            contract_data_str = contract_data_bytes.decode('utf-8')
                            
                            if contract_data_str.startswith('{') and contract_data_str.endswith('}'):
                                # Try to parse JSON with Decimal support
                                contract_data = json.loads(contract_data_str, object_hook=cls._decimal_deserializer)
                                # Get base transaction hex (without contract data)
                                base_transaction_hex = hex_bytes[:i].hex()
                                found_contract_data = True
                                logger.debug(f"Found contract data at offset {i}, length {potential_len}")
                                break
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # Not valid JSON or UTF-8, continue searching
                            continue
                except (ValueError, IndexError):
                    # Not a valid length prefix, continue searching
                    continue
            
            if not found_contract_data:
                raise ValueError("Could not parse smart contract data from hex - no valid JSON contract data found")
            
            logger.debug(f"Base transaction hex length: {len(base_transaction_hex)}, Contract data keys: {contract_data.keys()}")
            
            # Now parse base transaction using parent class with the separated hex
            try:
                base_tx = await Transaction.from_hex(base_transaction_hex, check_signatures)
            except Exception as e:
                logger.error(f"Failed to parse base transaction: {e}")
                raise ValueError(f"Failed to parse base transaction: {e}")
            
            # Extract contract-specific fields
            # Handle both old format (contract_code) and new format (contract_code_hex)
            contract_code = contract_data.get('contract_code_hex') or contract_data.get('contract_code', '')
            
            # Create smart contract transaction
            sc_tx = cls(
                inputs=base_tx.inputs,
                outputs=base_tx.outputs,
                operation_type=contract_data.get('operation_type', cls.OPERATION_DEPLOY),
                contract_address=contract_data.get('contract_address', ''),
                contract_code=contract_code,  # Already hex-encoded
                method_name=contract_data.get('method_name', ''),
                method_args=contract_data.get('method_args', []),
                gas_limit=int(contract_data.get('gas_limit', 100000)),
                message=base_tx.message if hasattr(base_tx, 'message') else None
            )
            
            logger.debug(f"Parsed {sc_tx._operation_name()} transaction from hex")
            return sc_tx
            
        except Exception as e:
            logger.error(f"Failed to parse smart contract transaction from hex: {e}")
            raise ValueError(f"Invalid smart contract transaction hex: {e}")
    
    def hash(self) -> str:
        """Get deterministic transaction hash"""
        if self.tx_hash is None:
            self.tx_hash = sha256(self.hex())
        return self.tx_hash
    
    def get_contract_deployment_address(self) -> str:
        """
        Get the deterministic address where contract will be deployed
        
        Returns:
            40-character hex address
            
        Raises:
            ValueError: If called on non-deployment transaction
        """
        if self.operation_type != self.OPERATION_DEPLOY:
            raise ValueError("Only deployment transactions have deployment addresses")
        
        # Generate deterministic deployment address from transaction data
        # Use first input's address as deployer
        sender = self.inputs[0].get_address() if self.inputs else "0x0"
        deployment_data = f"{sender}{self.hash()}{self.contract_code}"
        return sha256(deployment_data)[:40]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert transaction to dictionary for JSON serialization
        
        Returns:
            Dictionary with all transaction data including decoded contract code
        """
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
                'contract_code_hex': self.contract_code,  # Hex-encoded
                'contract_code_decoded': self.get_contract_code_decoded(),  # Human-readable
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
        """
        Calculate gas fee based on gas used and gas price
        
        Args:
            gas_price: Price per gas unit (defaults to 1 micro-token)
            
        Returns:
            Total gas fee in tokens
        """
        if gas_price is None:
            gas_price = Decimal('0.000001')  # Default: 1 microtoken per gas unit
        
        return Decimal(str(self.gas_used)) * gas_price
    
    async def get_fees(self):
        """
        Calculate total transaction fees including traditional UTXO fees and gas fees
        
        Returns:
            Total fees (traditional + gas)
        """
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
        """
        Override output verification for smart contract transactions.
        Smart contracts may have no outputs for deployment with no initial funding.
        """
        if not self.outputs:
            # Empty outputs are valid for smart contract transactions
            return True
        else:
            # If outputs exist, they must all be valid
            return all(tx_output.verify() for tx_output in self.outputs)
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        op_name = self._operation_name()
        if self.is_deployment():
            code_size = len(self.contract_code) // 2  # Hex chars to bytes
            return f"<SmartContractTransaction DEPLOY code_size={code_size}B gas_limit={self.gas_limit}>"
        else:
            return f"<SmartContractTransaction CALL contract={self.contract_address[:8]}... method={self.method_name} gas_limit={self.gas_limit}>"
