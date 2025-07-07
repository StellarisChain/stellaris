"""
BPF Virtual Machine for secure execution of BPF programs
"""

import time
import signal
import struct
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from .exceptions import (
    BPFExecutionError, BPFSecurityError, BPFResourceError, 
    BPFTimeoutError, BPFMemoryError, BPFGasError
)

class BPFVirtualMachine:
    """Secure BPF Virtual Machine implementation"""
    
    # BPF instruction opcodes
    BPF_LD = 0x00
    BPF_LDX = 0x01
    BPF_ST = 0x02
    BPF_STX = 0x03
    BPF_ALU = 0x04
    BPF_JMP = 0x05
    BPF_RET = 0x06
    BPF_MISC = 0x07
    
    # Memory and execution limits
    MAX_MEMORY = 1024 * 1024  # 1MB
    MAX_INSTRUCTIONS = 10000
    MAX_EXECUTION_TIME = 5.0  # 5 seconds
    MAX_STACK_DEPTH = 256
    
    def __init__(self, gas_limit: int = 100000):
        """
        Initialize BPF VM with security limits
        
        Args:
            gas_limit: Maximum gas for execution
        """
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.memory = bytearray(self.MAX_MEMORY)
        self.registers = [0] * 11  # r0-r10
        self.stack = []
        self.program_counter = 0
        self.instructions_executed = 0
        self.start_time = 0
        self.is_running = False
        
        # Security context
        self.allowed_syscalls = {
            'bpf_map_lookup_elem',
            'bpf_map_update_elem',
            'bpf_map_delete_elem',
            'bpf_get_prandom_u32',
            'bpf_ktime_get_ns'
        }
    
    def _consume_gas(self, amount: int):
        """Consume gas for operation"""
        self.gas_used += amount
        if self.gas_used > self.gas_limit:
            raise BPFGasError(f"Gas limit exceeded: {self.gas_used} > {self.gas_limit}")
    
    def _check_execution_limits(self):
        """Check various execution limits"""
        # Check instruction limit
        if self.instructions_executed >= self.MAX_INSTRUCTIONS:
            raise BPFResourceError("Maximum instructions exceeded")
        
        # Check time limit
        if time.time() - self.start_time > self.MAX_EXECUTION_TIME:
            raise BPFTimeoutError("Execution timeout")
        
        # Check stack depth
        if len(self.stack) > self.MAX_STACK_DEPTH:
            raise BPFResourceError("Stack overflow")
    
    def _validate_memory_access(self, address: int, size: int = 1):
        """Validate memory access is within bounds"""
        if address < 0 or address + size > len(self.memory):
            raise BPFMemoryError(f"Memory access out of bounds: {address}")
    
    def _decode_instruction(self, instruction: int) -> Tuple[int, int, int, int, int]:
        """Decode BPF instruction"""
        opcode = instruction & 0xFF
        dst_reg = (instruction >> 8) & 0xF
        src_reg = (instruction >> 12) & 0xF
        offset = (instruction >> 16) & 0xFFFF
        imm = instruction >> 32
        
        return opcode, dst_reg, src_reg, offset, imm
    
    def _execute_instruction(self, instruction: int):
        """Execute a single BPF instruction"""
        opcode, dst_reg, src_reg, offset, imm = self._decode_instruction(instruction)
        
        # Consume gas based on instruction complexity
        gas_cost = self._get_instruction_gas_cost(opcode)
        self._consume_gas(gas_cost)
        
        # Execute instruction based on opcode
        if opcode == self.BPF_LD:
            self._execute_load(dst_reg, src_reg, offset, imm)
        elif opcode == self.BPF_ST:
            self._execute_store(dst_reg, src_reg, offset, imm)
        elif opcode == self.BPF_ALU:
            self._execute_alu(dst_reg, src_reg, offset, imm)
        elif opcode == self.BPF_JMP:
            self._execute_jump(dst_reg, src_reg, offset, imm)
        elif opcode == self.BPF_RET:
            self._execute_return(dst_reg, src_reg, offset, imm)
        else:
            raise BPFExecutionError(f"Unknown opcode: {opcode}")
    
    def _get_instruction_gas_cost(self, opcode: int) -> int:
        """Get gas cost for instruction"""
        base_costs = {
            self.BPF_LD: 1,
            self.BPF_ST: 1,
            self.BPF_ALU: 1,
            self.BPF_JMP: 1,
            self.BPF_RET: 1
        }
        return base_costs.get(opcode, 1)
    
    def _execute_load(self, dst_reg: int, src_reg: int, offset: int, imm: int):
        """Execute load instruction"""
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        
        # Load immediate value
        if src_reg == 0:
            self.registers[dst_reg] = imm
        else:
            # Load from memory
            if src_reg >= len(self.registers):
                raise BPFExecutionError(f"Invalid source register: {src_reg}")
            
            addr = self.registers[src_reg] + offset
            self._validate_memory_access(addr, 8)
            self.registers[dst_reg] = struct.unpack('<Q', self.memory[addr:addr+8])[0]
    
    def _execute_store(self, dst_reg: int, src_reg: int, offset: int, imm: int):
        """Execute store instruction"""
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        
        addr = self.registers[dst_reg] + offset
        self._validate_memory_access(addr, 8)
        
        if src_reg == 0:
            # Store immediate value
            struct.pack_into('<Q', self.memory, addr, imm)
        else:
            # Store register value
            if src_reg >= len(self.registers):
                raise BPFExecutionError(f"Invalid source register: {src_reg}")
            struct.pack_into('<Q', self.memory, addr, self.registers[src_reg])
    
    def _execute_alu(self, dst_reg: int, src_reg: int, offset: int, imm: int):
        """Execute ALU instruction"""
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        
        # Simple ALU operations (ADD, SUB, etc.)
        operation = offset & 0xF
        
        if operation == 0:  # ADD
            if src_reg == 0:
                self.registers[dst_reg] += imm
            else:
                if src_reg >= len(self.registers):
                    raise BPFExecutionError(f"Invalid source register: {src_reg}")
                self.registers[dst_reg] += self.registers[src_reg]
        elif operation == 1:  # SUB
            if src_reg == 0:
                self.registers[dst_reg] -= imm
            else:
                if src_reg >= len(self.registers):
                    raise BPFExecutionError(f"Invalid source register: {src_reg}")
                self.registers[dst_reg] -= self.registers[src_reg]
        
        # Ensure register values stay within bounds
        self.registers[dst_reg] &= 0xFFFFFFFFFFFFFFFF
    
    def _execute_jump(self, dst_reg: int, src_reg: int, offset: int, imm: int):
        """Execute jump instruction"""
        # Unconditional jump
        if dst_reg == 0 and src_reg == 0:
            self.program_counter += offset
        else:
            # Conditional jump based on register comparison
            if dst_reg >= len(self.registers):
                raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
            
            condition_met = False
            if src_reg == 0:
                condition_met = self.registers[dst_reg] == imm
            else:
                if src_reg >= len(self.registers):
                    raise BPFExecutionError(f"Invalid source register: {src_reg}")
                condition_met = self.registers[dst_reg] == self.registers[src_reg]
            
            if condition_met:
                self.program_counter += offset
    
    def _execute_return(self, dst_reg: int, src_reg: int, offset: int, imm: int):
        """Execute return instruction"""
        self.is_running = False
        return self.registers[0]  # Return value in r0
    
    def execute(self, bytecode: bytes, input_data: Optional[bytes] = None) -> int:
        """
        Execute BPF program with security controls
        
        Args:
            bytecode: BPF bytecode to execute
            input_data: Input data for the program
            
        Returns:
            Exit code from program
        """
        if len(bytecode) == 0:
            raise BPFExecutionError("Empty bytecode")
        
        if len(bytecode) % 8 != 0:
            raise BPFExecutionError("Invalid bytecode length")
        
        # Setup execution environment
        self.start_time = time.time()
        self.is_running = True
        self.program_counter = 0
        self.instructions_executed = 0
        self.gas_used = 0
        
        # Initialize input data in memory
        if input_data:
            if len(input_data) > 1024:  # Limit input size
                raise BPFExecutionError("Input data too large")
            self.memory[:len(input_data)] = input_data
        
        # Convert bytecode to instructions
        instructions = []
        for i in range(0, len(bytecode), 8):
            instruction = struct.unpack('<Q', bytecode[i:i+8])[0]
            instructions.append(instruction)
        
        # Execute instructions
        try:
            while self.is_running and self.program_counter < len(instructions):
                self._check_execution_limits()
                
                instruction = instructions[self.program_counter]
                self._execute_instruction(instruction)
                
                self.program_counter += 1
                self.instructions_executed += 1
            
            # If we reach here without explicit return, return 0
            return 0
            
        except Exception as e:
            # Clean up and re-raise
            self.is_running = False
            raise
    
    def reset(self):
        """Reset VM state"""
        self.gas_used = 0
        self.memory = bytearray(self.MAX_MEMORY)
        self.registers = [0] * 11
        self.stack = []
        self.program_counter = 0
        self.instructions_executed = 0
        self.is_running = False