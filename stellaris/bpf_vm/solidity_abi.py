"""
Solidity ABI Support for BPF VM - Enables Solidity contract interaction
"""

import struct
from typing import Dict, Any, Optional, List, Tuple, Union
from decimal import Decimal
import json
from .exceptions import BPFValidationError, BPFExecutionError

class SolidityABI:
    """Solidity ABI encoder/decoder for contract interaction"""
    
    def __init__(self):
        """Initialize Solidity ABI handler"""
        self.type_sizes = {
            'uint8': 1, 'uint16': 2, 'uint32': 4, 'uint64': 8, 'uint128': 16, 'uint256': 32,
            'int8': 1, 'int16': 2, 'int32': 4, 'int64': 8, 'int128': 16, 'int256': 32,
            'address': 20, 'bool': 1, 'bytes32': 32
        }
    
    def encode_function_call(self, function_name: str, abi: Dict[str, Any], 
                           args: List[Any]) -> bytes:
        """
        Encode function call data for Solidity contract
        
        Args:
            function_name: Name of the function to call
            abi: Contract ABI
            args: Function arguments
            
        Returns:
            Encoded function call data
        """
        # Get function from ABI
        function_abi = self._get_function_abi(function_name, abi)
        
        # Generate function selector (first 4 bytes of keccak256 hash)
        function_signature = self._get_function_signature(function_name, function_abi)
        selector = self._keccak256(function_signature.encode())[:4]
        
        # Encode arguments
        encoded_args = self._encode_arguments(args, function_abi.get('inputs', []))
        
        return selector + encoded_args
    
    def decode_function_output(self, data: bytes, abi: Dict[str, Any], 
                             function_name: str) -> List[Any]:
        """
        Decode function output data
        
        Args:
            data: Raw output data
            abi: Contract ABI
            function_name: Name of the function
            
        Returns:
            Decoded output values
        """
        function_abi = self._get_function_abi(function_name, abi)
        outputs = function_abi.get('outputs', [])
        
        if not outputs:
            return []
        
        return self._decode_arguments(data, outputs)
    
    def _get_function_abi(self, function_name: str, abi: Dict[str, Any]) -> Dict[str, Any]:
        """Get function ABI from contract ABI"""
        # Handle both old format (functions dict) and new format (array)
        if 'functions' in abi:
            # Old format
            if function_name not in abi['functions']:
                raise BPFValidationError(f"Function '{function_name}' not found in ABI")
            return abi['functions'][function_name]
        
        # New format (standard Solidity ABI format)
        if isinstance(abi, list):
            for item in abi:
                if item.get('type') == 'function' and item.get('name') == function_name:
                    return item
        elif isinstance(abi, dict) and 'abi' in abi:
            # Wrapped ABI
            for item in abi['abi']:
                if item.get('type') == 'function' and item.get('name') == function_name:
                    return item
        
        raise BPFValidationError(f"Function '{function_name}' not found in ABI")
    
    def _get_function_signature(self, function_name: str, function_abi: Dict[str, Any]) -> str:
        """Generate function signature for selector calculation"""
        inputs = function_abi.get('inputs', [])
        input_types = []
        
        for input_param in inputs:
            input_types.append(input_param['type'])
        
        return f"{function_name}({','.join(input_types)})"
    
    def _encode_arguments(self, args: List[Any], input_types: List[Dict[str, Any]]) -> bytes:
        """Encode function arguments"""
        if len(args) != len(input_types):
            raise BPFValidationError(f"Argument count mismatch: {len(args)} vs {len(input_types)}")
        
        encoded_data = b''
        
        for i, (arg, param_type) in enumerate(zip(args, input_types)):
            type_name = param_type['type']
            encoded_data += self._encode_single_argument(arg, type_name)
        
        return encoded_data
    
    def _encode_single_argument(self, arg: Any, type_name: str) -> bytes:
        """Encode a single argument based on its type"""
        if type_name.startswith('uint'):
            # Unsigned integer
            size = int(type_name[4:]) if type_name[4:] else 256
            if isinstance(arg, str):
                arg = int(arg)
            return arg.to_bytes(32, byteorder='big')  # All integers are 32 bytes in ABI
        
        elif type_name.startswith('int'):
            # Signed integer
            size = int(type_name[3:]) if type_name[3:] else 256
            if isinstance(arg, str):
                arg = int(arg)
            # Handle negative numbers
            if arg < 0:
                arg = (1 << 256) + arg  # Two's complement
            return arg.to_bytes(32, byteorder='big')
        
        elif type_name == 'address':
            # Address (20 bytes, left-padded to 32 bytes)
            if isinstance(arg, str):
                if arg.startswith('0x'):
                    arg = arg[2:]
                arg_bytes = bytes.fromhex(arg)
            else:
                arg_bytes = arg
            return b'\x00' * 12 + arg_bytes[:20]  # Pad to 32 bytes
        
        elif type_name == 'bool':
            # Boolean
            return b'\x00' * 31 + (b'\x01' if arg else b'\x00')
        
        elif type_name.startswith('bytes'):
            if type_name == 'bytes':
                # Dynamic bytes
                length = len(arg)
                return length.to_bytes(32, byteorder='big') + arg + b'\x00' * (32 - (len(arg) % 32))
            else:
                # Fixed bytes
                size = int(type_name[5:])
                if isinstance(arg, str):
                    if arg.startswith('0x'):
                        arg = arg[2:]
                    arg_bytes = bytes.fromhex(arg)
                else:
                    arg_bytes = arg
                return arg_bytes[:size] + b'\x00' * (32 - size)
        
        elif type_name == 'string':
            # String (UTF-8 encoded)
            utf8_bytes = arg.encode('utf-8')
            length = len(utf8_bytes)
            return length.to_bytes(32, byteorder='big') + utf8_bytes + b'\x00' * (32 - (len(utf8_bytes) % 32))
        
        else:
            raise BPFValidationError(f"Unsupported argument type: {type_name}")
    
    def _decode_arguments(self, data: bytes, output_types: List[Dict[str, Any]]) -> List[Any]:
        """Decode function output arguments"""
        if not data:
            return []
        
        results = []
        offset = 0
        
        for param_type in output_types:
            type_name = param_type['type']
            value, consumed = self._decode_single_argument(data[offset:], type_name)
            results.append(value)
            offset += consumed
        
        return results
    
    def _decode_single_argument(self, data: bytes, type_name: str) -> Tuple[Any, int]:
        """Decode a single argument and return (value, bytes_consumed)"""
        if len(data) < 32:
            raise BPFExecutionError("Insufficient data for decoding")
        
        if type_name.startswith('uint'):
            # Unsigned integer
            value = int.from_bytes(data[:32], byteorder='big')
            return value, 32
        
        elif type_name.startswith('int'):
            # Signed integer
            value = int.from_bytes(data[:32], byteorder='big')
            # Handle negative numbers (two's complement)
            if value >= (1 << 255):
                value = value - (1 << 256)
            return value, 32
        
        elif type_name == 'address':
            # Address (last 20 bytes)
            address_bytes = data[12:32]
            return '0x' + address_bytes.hex(), 32
        
        elif type_name == 'bool':
            # Boolean
            value = data[31] != 0
            return value, 32
        
        elif type_name.startswith('bytes'):
            if type_name == 'bytes':
                # Dynamic bytes
                length = int.from_bytes(data[:32], byteorder='big')
                value = data[32:32 + length]
                # Calculate total bytes consumed (including padding)
                consumed = 32 + ((length + 31) // 32) * 32
                return value, consumed
            else:
                # Fixed bytes
                size = int(type_name[5:])
                value = data[:size]
                return value, 32
        
        elif type_name == 'string':
            # String
            length = int.from_bytes(data[:32], byteorder='big')
            value = data[32:32 + length].decode('utf-8')
            consumed = 32 + ((length + 31) // 32) * 32
            return value, consumed
        
        else:
            raise BPFValidationError(f"Unsupported output type: {type_name}")
    
    def _keccak256(self, data: bytes) -> bytes:
        """Simple keccak256 implementation for function selectors"""
        # This is a simplified implementation
        # In a real implementation, use the proper keccak256 library
        import hashlib
        return hashlib.sha256(data).digest()  # Using SHA256 as placeholder
    
    def is_solidity_abi(self, abi: Any) -> bool:
        """Check if ABI is in Solidity format"""
        if isinstance(abi, list):
            # Standard Solidity ABI format
            return True
        elif isinstance(abi, dict):
            if 'abi' in abi:
                # Wrapped ABI
                return True
            elif 'functions' in abi:
                # Check if any function has Solidity-style type definitions
                for func_name, func_def in abi['functions'].items():
                    if 'inputs' in func_def and isinstance(func_def['inputs'], list):
                        for input_param in func_def['inputs']:
                            if isinstance(input_param, dict) and 'type' in input_param:
                                return True
        return False
    
    def convert_to_solidity_abi(self, old_abi: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert old ABI format to Solidity ABI format"""
        if isinstance(old_abi, list):
            return old_abi  # Already in correct format
        
        solidity_abi = []
        
        if 'functions' in old_abi:
            for func_name, func_def in old_abi['functions'].items():
                abi_item = {
                    'type': 'function',
                    'name': func_name,
                    'inputs': func_def.get('inputs', []),
                    'outputs': func_def.get('outputs', []),
                    'stateMutability': func_def.get('stateMutability', 'nonpayable')
                }
                solidity_abi.append(abi_item)
        
        return solidity_abi