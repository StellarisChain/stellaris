"""
EVM Compatibility Layer for BPF VM - Enables Solidity and Hardhat support
"""

import struct
from typing import Dict, Any, Optional, List, Tuple, Union
from decimal import Decimal
from .vm import BPFVirtualMachine
from .exceptions import BPFExecutionError, BPFSecurityError, BPFResourceError

class EVMCompatibilityLayer:
    """EVM compatibility layer for BPF VM to support Solidity contracts"""
    
    # EVM opcodes - key ones needed for Solidity
    STOP = 0x00
    ADD = 0x01
    MUL = 0x02
    SUB = 0x03
    DIV = 0x04
    MOD = 0x05
    ADDMOD = 0x06
    MULMOD = 0x07
    EXP = 0x08
    SIGNEXTEND = 0x09
    
    # Comparison operations
    LT = 0x10
    GT = 0x11
    SLT = 0x12
    SGT = 0x13
    EQ = 0x14
    ISZERO = 0x15
    AND = 0x16
    OR = 0x17
    XOR = 0x18
    NOT = 0x19
    BYTE = 0x1a
    SHL = 0x1b
    SHR = 0x1c
    SAR = 0x1d
    
    # Memory operations
    MLOAD = 0x51
    MSTORE = 0x52
    MSTORE8 = 0x53
    SLOAD = 0x54
    SSTORE = 0x55
    JUMP = 0x56
    JUMPI = 0x57
    PC = 0x58
    MSIZE = 0x59
    GAS = 0x5a
    JUMPDEST = 0x5b
    
    # Stack operations
    PUSH1 = 0x60
    PUSH32 = 0x7f
    DUP1 = 0x80
    DUP16 = 0x8f
    SWAP1 = 0x90
    SWAP16 = 0x9f
    
    # Call operations
    CALL = 0xf1
    RETURN = 0xf3
    REVERT = 0xfd
    
    def __init__(self, bpf_vm: BPFVirtualMachine):
        """Initialize EVM compatibility layer"""
        self.bpf_vm = bpf_vm
        self.evm_stack = []
        self.evm_memory = bytearray(1024 * 1024)  # 1MB EVM memory
        self.evm_storage = {}  # Contract storage
        self.program_counter = 0
        self.gas_used = 0
        self.return_data = b''
        
    def execute_evm_bytecode(self, bytecode: bytes, input_data: bytes = b'') -> Tuple[bytes, int]:
        """
        Execute EVM bytecode with BPF VM backend
        
        Args:
            bytecode: EVM bytecode to execute
            input_data: Input data for the contract
            
        Returns:
            Tuple of (return_data, gas_used)
        """
        if not bytecode:
            raise BPFExecutionError("Empty EVM bytecode")
        
        # Reset state
        self.evm_stack = []
        self.evm_memory = bytearray(1024 * 1024)
        self.program_counter = 0
        self.gas_used = 0
        self.return_data = b''
        
        # Place input data in memory at standard location
        if input_data:
            self.evm_memory[:len(input_data)] = input_data
        
        # Execute bytecode
        try:
            while self.program_counter < len(bytecode):
                opcode = bytecode[self.program_counter]
                self._execute_evm_opcode(opcode, bytecode)
                self.program_counter += 1
                
                # Check gas limit
                if self.gas_used > self.bpf_vm.gas_limit:
                    raise BPFResourceError("Gas limit exceeded")
        
        except Exception as e:
            if isinstance(e, (BPFExecutionError, BPFSecurityError, BPFResourceError)):
                raise
            raise BPFExecutionError(f"EVM execution error: {e}")
        
        return self.return_data, self.gas_used
    
    def _execute_evm_opcode(self, opcode: int, bytecode: bytes):
        """Execute a single EVM opcode"""
        # Consume gas
        self._consume_gas(self._get_opcode_gas_cost(opcode))
        
        # Arithmetic operations
        if opcode == self.ADD:
            self._execute_add()
        elif opcode == self.SUB:
            self._execute_sub()
        elif opcode == self.MUL:
            self._execute_mul()
        elif opcode == self.DIV:
            self._execute_div()
        elif opcode == self.MOD:
            self._execute_mod()
        
        # Comparison operations
        elif opcode == self.LT:
            self._execute_lt()
        elif opcode == self.GT:
            self._execute_gt()
        elif opcode == self.EQ:
            self._execute_eq()
        elif opcode == self.ISZERO:
            self._execute_iszero()
        
        # Bitwise operations
        elif opcode == self.AND:
            self._execute_and()
        elif opcode == self.OR:
            self._execute_or()
        elif opcode == self.XOR:
            self._execute_xor()
        elif opcode == self.NOT:
            self._execute_not()
        
        # Memory operations
        elif opcode == self.MLOAD:
            self._execute_mload()
        elif opcode == self.MSTORE:
            self._execute_mstore()
        elif opcode == self.SLOAD:
            self._execute_sload()
        elif opcode == self.SSTORE:
            self._execute_sstore()
        
        # Stack operations
        elif self.PUSH1 <= opcode <= self.PUSH32:
            self._execute_push(opcode, bytecode)
        elif self.DUP1 <= opcode <= self.DUP16:
            self._execute_dup(opcode)
        elif self.SWAP1 <= opcode <= self.SWAP16:
            self._execute_swap(opcode)
        
        # Control flow
        elif opcode == self.JUMP:
            self._execute_jump()
        elif opcode == self.JUMPI:
            self._execute_jumpi()
        elif opcode == self.JUMPDEST:
            pass  # Jump destination, no operation
        
        # Return operations
        elif opcode == self.RETURN:
            self._execute_return()
        elif opcode == self.REVERT:
            self._execute_revert()
        elif opcode == self.STOP:
            self._execute_stop()
        
        else:
            raise BPFExecutionError(f"Unsupported EVM opcode: {hex(opcode)}")
    
    def _consume_gas(self, amount: int):
        """Consume gas for operation"""
        self.gas_used += amount
        self.bpf_vm._consume_gas(amount)
    
    def _get_opcode_gas_cost(self, opcode: int) -> int:
        """Get gas cost for EVM opcode"""
        # Simplified gas costs - in reality these vary by operation complexity
        if opcode == self.SSTORE:
            return 5000  # Storage write is expensive
        elif opcode == self.SLOAD:
            return 200   # Storage read
        elif opcode in [self.MLOAD, self.MSTORE]:
            return 3     # Memory operations
        elif opcode in [self.ADD, self.SUB, self.MUL, self.DIV, self.MOD]:
            return 3     # Arithmetic operations
        else:
            return 3     # Default cost
    
    # Stack operations
    def _stack_push(self, value: int):
        """Push value onto EVM stack"""
        if len(self.evm_stack) >= 1024:  # EVM stack limit
            raise BPFResourceError("Stack overflow")
        self.evm_stack.append(value & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
    
    def _stack_pop(self) -> int:
        """Pop value from EVM stack"""
        if not self.evm_stack:
            raise BPFExecutionError("Stack underflow")
        return self.evm_stack.pop()
    
    # Arithmetic operations
    def _execute_add(self):
        """ADD operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = (a + b) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self._stack_push(result)
    
    def _execute_sub(self):
        """SUB operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = (a - b) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self._stack_push(result)
    
    def _execute_mul(self):
        """MUL operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = (a * b) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self._stack_push(result)
    
    def _execute_div(self):
        """DIV operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        if b == 0:
            result = 0
        else:
            result = a // b
        self._stack_push(result)
    
    def _execute_mod(self):
        """MOD operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        if b == 0:
            result = 0
        else:
            result = a % b
        self._stack_push(result)
    
    # Comparison operations
    def _execute_lt(self):
        """LT operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = 1 if a < b else 0
        self._stack_push(result)
    
    def _execute_gt(self):
        """GT operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = 1 if a > b else 0
        self._stack_push(result)
    
    def _execute_eq(self):
        """EQ operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = 1 if a == b else 0
        self._stack_push(result)
    
    def _execute_iszero(self):
        """ISZERO operation"""
        a = self._stack_pop()
        result = 1 if a == 0 else 0
        self._stack_push(result)
    
    # Bitwise operations
    def _execute_and(self):
        """AND operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = a & b
        self._stack_push(result)
    
    def _execute_or(self):
        """OR operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = a | b
        self._stack_push(result)
    
    def _execute_xor(self):
        """XOR operation"""
        b = self._stack_pop()
        a = self._stack_pop()
        result = a ^ b
        self._stack_push(result)
    
    def _execute_not(self):
        """NOT operation"""
        a = self._stack_pop()
        result = (~a) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self._stack_push(result)
    
    # Memory operations
    def _execute_mload(self):
        """MLOAD operation"""
        offset = self._stack_pop()
        if offset + 32 > len(self.evm_memory):
            # Expand memory
            new_size = offset + 32
            self.evm_memory.extend(b'\x00' * (new_size - len(self.evm_memory)))
        
        # Load 32 bytes from memory
        data = self.evm_memory[offset:offset + 32]
        value = int.from_bytes(data, byteorder='big')
        self._stack_push(value)
    
    def _execute_mstore(self):
        """MSTORE operation"""
        offset = self._stack_pop()
        value = self._stack_pop()
        
        if offset + 32 > len(self.evm_memory):
            # Expand memory
            new_size = offset + 32
            self.evm_memory.extend(b'\x00' * (new_size - len(self.evm_memory)))
        
        # Store 32 bytes to memory
        data = value.to_bytes(32, byteorder='big')
        self.evm_memory[offset:offset + 32] = data
    
    def _execute_sload(self):
        """SLOAD operation"""
        key = self._stack_pop()
        value = self.evm_storage.get(key, 0)
        self._stack_push(value)
    
    def _execute_sstore(self):
        """SSTORE operation"""
        key = self._stack_pop()
        value = self._stack_pop()
        self.evm_storage[key] = value
    
    # Stack operations
    def _execute_push(self, opcode: int, bytecode: bytes):
        """PUSH operation"""
        push_size = opcode - self.PUSH1 + 1
        if self.program_counter + push_size >= len(bytecode):
            raise BPFExecutionError("PUSH beyond bytecode end")
        
        # Get the bytes to push
        data = bytecode[self.program_counter + 1:self.program_counter + 1 + push_size]
        value = int.from_bytes(data, byteorder='big')
        self._stack_push(value)
        
        # Skip the pushed bytes
        self.program_counter += push_size
    
    def _execute_dup(self, opcode: int):
        """DUP operation"""
        dup_index = opcode - self.DUP1
        if dup_index >= len(self.evm_stack):
            raise BPFExecutionError("DUP index out of range")
        
        value = self.evm_stack[-(dup_index + 1)]
        self._stack_push(value)
    
    def _execute_swap(self, opcode: int):
        """SWAP operation"""
        swap_index = opcode - self.SWAP1 + 1
        if swap_index >= len(self.evm_stack):
            raise BPFExecutionError("SWAP index out of range")
        
        # Swap top of stack with element at swap_index
        top = self.evm_stack[-1]
        self.evm_stack[-1] = self.evm_stack[-(swap_index + 1)]
        self.evm_stack[-(swap_index + 1)] = top
    
    # Control flow
    def _execute_jump(self):
        """JUMP operation"""
        dest = self._stack_pop()
        self.program_counter = dest - 1  # -1 because main loop will increment
    
    def _execute_jumpi(self):
        """JUMPI operation"""
        dest = self._stack_pop()
        condition = self._stack_pop()
        if condition != 0:
            self.program_counter = dest - 1  # -1 because main loop will increment
    
    # Return operations
    def _execute_return(self):
        """RETURN operation"""
        offset = self._stack_pop()
        size = self._stack_pop()
        
        if offset + size > len(self.evm_memory):
            raise BPFExecutionError("RETURN data out of memory bounds")
        
        self.return_data = bytes(self.evm_memory[offset:offset + size])
        # Set program counter to end to stop execution
        self.program_counter = float('inf')
    
    def _execute_revert(self):
        """REVERT operation"""
        offset = self._stack_pop()
        size = self._stack_pop()
        
        if offset + size > len(self.evm_memory):
            raise BPFExecutionError("REVERT data out of memory bounds")
        
        revert_data = bytes(self.evm_memory[offset:offset + size])
        raise BPFExecutionError(f"Contract execution reverted: {revert_data.hex()}")
    
    def _execute_stop(self):
        """STOP operation"""
        self.return_data = b''
        # Set program counter to end to stop execution
        self.program_counter = float('inf')