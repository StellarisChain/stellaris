"""
BPF Virtual Machine for secure execution of BPF programs with EVM compatibility
"""

import time
import signal
import struct
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from stellaris.svm.exceptions import (
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
        Initialize BPF VM with security limits and EVM compatibility
        
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
        
        # EVM compatibility flag
        self.evm_mode = False
        self.evm_compat = None
        
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
    
    def _decode_instruction(self, instruction: int) -> Dict[str, int]:
        """Decode BPF instruction per Linux Kernel BPF ISA"""
        # 64-bit instruction layout
        opcode = instruction & 0xFF
        dst_reg = (instruction >> 8) & 0xF
        src_reg = (instruction >> 12) & 0xF
        offset = ((instruction >> 16) & 0xFFFF)
        # offset is signed 16-bit
        if offset & 0x8000:
            offset -= 0x10000
        imm = (instruction >> 32) & 0xFFFFFFFF
        # imm is signed 32-bit
        if imm & 0x80000000:
            imm -= 0x100000000
        # Instruction class is lower 3 bits of opcode
        instr_class = opcode & 0x7
        # Mode is bits 5-3
        mode = (opcode >> 5) & 0x7
        # Size is bits 4-3
        size = (opcode >> 3) & 0x3
        # ALU/JMP op code (upper 4 bits)
        alu_jmp_op = (opcode >> 4) & 0xF
        # Source bit (bit 3)
        src_bit = (opcode >> 3) & 0x1
        return {
            'opcode': opcode,
            'instr_class': instr_class,
            'mode': mode,
            'size': size,
            'alu_jmp_op': alu_jmp_op,
            'src_bit': src_bit,
            'dst_reg': dst_reg,
            'src_reg': src_reg,
            'offset': offset,
            'imm': imm,
        }
    
    def _execute_instruction(self, instruction: int):
        """Execute a single BPF instruction (ISA compliant stub)"""
        fields = self._decode_instruction(instruction)
        opcode = fields['opcode']
        instr_class = fields['instr_class']
        mode = fields['mode']
        size = fields['size']
        alu_jmp_op = fields['alu_jmp_op']
        src_bit = fields['src_bit']
        dst_reg = fields['dst_reg']
        src_reg = fields['src_reg']
        offset = fields['offset']
        imm = fields['imm']

        # Consume gas based on instruction complexity
        gas_cost = self._get_instruction_gas_cost(opcode)
        self._consume_gas(gas_cost)

        # Dispatch by instruction class
        if instr_class == 0x0:  # LD
            self._execute_ld(mode, size, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x1:  # LDX
            self._execute_ldx(mode, size, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x2:  # ST
            self._execute_st(mode, size, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x3:  # STX
            self._execute_stx(mode, size, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x4:  # ALU/ALU64
            self._execute_alu(instr_class, alu_jmp_op, src_bit, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x5 or instr_class == 0x6:  # JMP/JMP32
            self._execute_jmp(instr_class, alu_jmp_op, src_bit, dst_reg, src_reg, offset, imm, instruction)
        elif instr_class == 0x7:  # ALU64 (for byte swap, etc.)
            self._execute_alu(instr_class, alu_jmp_op, src_bit, dst_reg, src_reg, offset, imm, instruction)
        else:
            raise BPFExecutionError(f"Unknown instruction class: {instr_class}")

    # --- Instruction class/mode stubs ---
    def _execute_ld(self, mode, size, dst_reg, src_reg, offset, imm, instruction):
        # Only IMM mode is valid for LD (for 64-bit immediate loads)
        if mode == 0:  # IMM
            # Wide (128-bit) immediate: next instruction provides high 32 bits
            # This is a simplification: in real BPF, the next instruction is a pseudo-instruction
            # For now, just load 64-bit immediate
            if dst_reg >= len(self.registers):
                raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
            self.registers[dst_reg] = imm & 0xFFFFFFFFFFFFFFFF
        else:
            raise BPFExecutionError(f"Unsupported LD mode: {mode}")

    def _execute_ldx(self, mode, size, dst_reg, src_reg, offset, imm, instruction):
        # LDX: dst = *(size *)(src + offset)
        if dst_reg >= len(self.registers) or src_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid register: dst={dst_reg}, src={src_reg}")
        addr = self.registers[src_reg] + offset
        if mode == 3:  # MEM
            if size == 0:  # W (4 bytes)
                self._validate_memory_access(addr, 4)
                self.registers[dst_reg] = struct.unpack('<I', self.memory[addr:addr+4])[0]
            elif size == 1:  # H (2 bytes)
                self._validate_memory_access(addr, 2)
                self.registers[dst_reg] = struct.unpack('<H', self.memory[addr:addr+2])[0]
            elif size == 2:  # B (1 byte)
                self._validate_memory_access(addr, 1)
                self.registers[dst_reg] = self.memory[addr]
            elif size == 3:  # DW (8 bytes)
                self._validate_memory_access(addr, 8)
                self.registers[dst_reg] = struct.unpack('<Q', self.memory[addr:addr+8])[0]
            else:
                raise BPFExecutionError(f"Invalid LDX size: {size}")
        elif mode == 4:  # MEMSX (sign-extension load)
            if size == 0:  # W (4 bytes)
                self._validate_memory_access(addr, 4)
                val = struct.unpack('<i', self.memory[addr:addr+4])[0]
                self.registers[dst_reg] = val & 0xFFFFFFFFFFFFFFFF
            elif size == 1:  # H (2 bytes)
                self._validate_memory_access(addr, 2)
                val = struct.unpack('<h', self.memory[addr:addr+2])[0]
                self.registers[dst_reg] = val & 0xFFFFFFFFFFFFFFFF
            elif size == 2:  # B (1 byte)
                self._validate_memory_access(addr, 1)
                val = struct.unpack('<b', self.memory[addr:addr+1])[0]
                self.registers[dst_reg] = val & 0xFFFFFFFFFFFFFFFF
            else:
                raise BPFExecutionError(f"Invalid LDX MEMSX size: {size}")
        else:
            raise BPFExecutionError(f"Unsupported LDX mode: {mode}")

    def _execute_st(self, mode, size, dst_reg, src_reg, offset, imm, instruction):
        # ST: *(size *)(dst + offset) = imm
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        addr = self.registers[dst_reg] + offset
        if mode == 3:  # MEM
            if size == 0:  # W
                self._validate_memory_access(addr, 4)
                struct.pack_into('<I', self.memory, addr, imm & 0xFFFFFFFF)
            elif size == 1:  # H
                self._validate_memory_access(addr, 2)
                struct.pack_into('<H', self.memory, addr, imm & 0xFFFF)
            elif size == 2:  # B
                self._validate_memory_access(addr, 1)
                self.memory[addr] = imm & 0xFF
            elif size == 3:  # DW
                self._validate_memory_access(addr, 8)
                struct.pack_into('<Q', self.memory, addr, imm & 0xFFFFFFFFFFFFFFFF)
            else:
                raise BPFExecutionError(f"Invalid ST size: {size}")
        else:
            raise BPFExecutionError(f"Unsupported ST mode: {mode}")

    def _execute_stx(self, mode, size, dst_reg, src_reg, offset, imm, instruction):
        # STX: *(size *)(dst + offset) = src
        if dst_reg >= len(self.registers) or src_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid register: dst={dst_reg}, src={src_reg}")
        addr = self.registers[dst_reg] + offset
        if mode == 3:  # MEM
            if size == 0:  # W
                self._validate_memory_access(addr, 4)
                struct.pack_into('<I', self.memory, addr, self.registers[src_reg] & 0xFFFFFFFF)
            elif size == 1:  # H
                self._validate_memory_access(addr, 2)
                struct.pack_into('<H', self.memory, addr, self.registers[src_reg] & 0xFFFF)
            elif size == 2:  # B
                self._validate_memory_access(addr, 1)
                self.memory[addr] = self.registers[src_reg] & 0xFF
            elif size == 3:  # DW
                self._validate_memory_access(addr, 8)
                struct.pack_into('<Q', self.memory, addr, self.registers[src_reg] & 0xFFFFFFFFFFFFFFFF)
            else:
                raise BPFExecutionError(f"Invalid STX size: {size}")
        else:
            raise BPFExecutionError(f"Unsupported STX mode: {mode}")

    def _execute_alu(self, instr_class, alu_jmp_op, src_bit, dst_reg, src_reg, offset, imm, instruction):
        # Implements ALU/ALU64 operations as per BPF ISA
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        is_alu64 = (instr_class == 0x7)
        mask = 0xFFFFFFFFFFFFFFFF if is_alu64 else 0xFFFFFFFF
        def get_src():
            if src_bit == 0:
                return imm
            else:
                if src_reg >= len(self.registers):
                    raise BPFExecutionError(f"Invalid source register: {src_reg}")
                return self.registers[src_reg]
        src = get_src()
        dst = self.registers[dst_reg]
        op = alu_jmp_op
        # ALU/ALU64 operation codes
        if op == 0x0:  # ADD
            result = (dst + src) & mask
        elif op == 0x1:  # SUB
            result = (dst - src) & mask
        elif op == 0x2:  # MUL
            result = (dst * src) & mask
        elif op == 0x3:  # DIV/SDIV
            if src == 0:
                result = 0 if not is_alu64 else 0
            else:
                if src_bit == 0 or not is_alu64:
                    result = (dst // src) & mask
                else:
                    # signed division
                    sdst = dst if dst < (1 << 63) else dst - (1 << 64)
                    ssrc = src if src < (1 << 63) else src - (1 << 64)
                    if ssrc == -1 and sdst == -(1 << 63):
                        result = sdst & mask
                    else:
                        result = int(sdst / ssrc) & mask
        elif op == 0x4:  # OR
            result = (dst | src) & mask
        elif op == 0x5:  # AND
            result = (dst & src) & mask
        elif op == 0x6:  # LSH
            shift = src & (0x3F if is_alu64 else 0x1F)
            result = (dst << shift) & mask
        elif op == 0x7:  # RSH
            shift = src & (0x3F if is_alu64 else 0x1F)
            result = (dst >> shift) & mask
        elif op == 0x8:  # NEG
            result = (-dst) & mask
        elif op == 0x9:  # MOD/SMOD
            if src == 0:
                result = dst if is_alu64 else (dst & 0xFFFFFFFF00000000)
            else:
                if src_bit == 0 or not is_alu64:
                    result = (dst % src) & mask
                else:
                    sdst = dst if dst < (1 << 63) else dst - (1 << 64)
                    ssrc = src if src < (1 << 63) else src - (1 << 64)
                    if ssrc == -1 and sdst == -(1 << 63):
                        result = 0
                    else:
                        result = (sdst % ssrc) & mask
        elif op == 0xA:  # XOR
            result = (dst ^ src) & mask
        elif op == 0xB:  # MOV/MOVSX
            if src_bit == 0:
                result = src & mask
            else:
                result = src & mask
        elif op == 0xC:  # ARSH
            shift = src & (0x3F if is_alu64 else 0x1F)
            if is_alu64:
                sdst = dst if dst < (1 << 63) else dst - (1 << 64)
                result = (sdst >> shift) & mask
            else:
                sdst = dst if dst < (1 << 31) else dst - (1 << 32)
                result = (sdst >> shift) & mask
        elif op == 0xD:  # END (byte swap)
            width = imm
            if width == 16:
                result = int.from_bytes(dst.to_bytes(8, 'little')[:2][::-1], 'little')
            elif width == 32:
                result = int.from_bytes(dst.to_bytes(8, 'little')[:4][::-1], 'little')
            elif width == 64:
                result = int.from_bytes(dst.to_bytes(8, 'little')[::-1], 'little')
            else:
                raise BPFExecutionError(f"Invalid byte swap width: {width}")
        else:
            raise BPFExecutionError(f"Unknown ALU/ALU64 op: {op}")
        self.registers[dst_reg] = result

    def _execute_jmp(self, instr_class, alu_jmp_op, src_bit, dst_reg, src_reg, offset, imm, instruction):
        # Implements JMP/JMP32 operations as per BPF ISA
        if dst_reg >= len(self.registers):
            raise BPFExecutionError(f"Invalid destination register: {dst_reg}")
        is_jmp32 = (instr_class == 0x6)
        mask = 0xFFFFFFFF if is_jmp32 else 0xFFFFFFFFFFFFFFFF
        def get_src():
            if src_bit == 0:
                return imm
            else:
                if src_reg >= len(self.registers):
                    raise BPFExecutionError(f"Invalid source register: {src_reg}")
                return self.registers[src_reg]
        src = get_src() & mask
        dst = self.registers[dst_reg] & mask
        op = alu_jmp_op
        pc_inc = 1
        # JMP/JMP32 operation codes
        if op == 0x0:  # JA (unconditional jump)
            self.program_counter += offset - 1  # -1 because main loop will +1
            return
        elif op == 0x1:  # JEQ
            if dst == src:
                self.program_counter += offset - 1
                return
        elif op == 0x2:  # JGT (unsigned)
            if dst > src:
                self.program_counter += offset - 1
                return
        elif op == 0x3:  # JGE (unsigned)
            if dst >= src:
                self.program_counter += offset - 1
                return
        elif op == 0x4:  # JSET
            if (dst & src) != 0:
                self.program_counter += offset - 1
                return
        elif op == 0x5:  # JNE
            if dst != src:
                self.program_counter += offset - 1
                return
        elif op == 0x6:  # JSGT (signed)
            sdst = dst if dst < (1 << (32 if is_jmp32 else 64) - 1) else dst - (1 << (32 if is_jmp32 else 64))
            ssrc = src if src < (1 << (32 if is_jmp32 else 64) - 1) else src - (1 << (32 if is_jmp32 else 64))
            if sdst > ssrc:
                self.program_counter += offset - 1
                return
        elif op == 0x7:  # JSGE (signed)
            sdst = dst if dst < (1 << (32 if is_jmp32 else 64) - 1) else dst - (1 << (32 if is_jmp32 else 64))
            ssrc = src if src < (1 << (32 if is_jmp32 else 64) - 1) else src - (1 << (32 if is_jmp32 else 64))
            if sdst >= ssrc:
                self.program_counter += offset - 1
                return
        elif op == 0x8:  # CALL (helper, not implemented)
            raise BPFExecutionError("Helper CALL not implemented")
        elif op == 0x9:  # EXIT
            self.is_running = False
            return
        elif op == 0xA:  # JLT (unsigned)
            if dst < src:
                self.program_counter += offset - 1
                return
        elif op == 0xB:  # JLE (unsigned)
            if dst <= src:
                self.program_counter += offset - 1
                return
        elif op == 0xC:  # JSLT (signed)
            sdst = dst if dst < (1 << (32 if is_jmp32 else 64) - 1) else dst - (1 << (32 if is_jmp32 else 64))
            ssrc = src if src < (1 << (32 if is_jmp32 else 64) - 1) else src - (1 << (32 if is_jmp32 else 64))
            if sdst < ssrc:
                self.program_counter += offset - 1
                return
        elif op == 0xD:  # JSLE (signed)
            sdst = dst if dst < (1 << (32 if is_jmp32 else 64) - 1) else dst - (1 << (32 if is_jmp32 else 64))
            ssrc = src if src < (1 << (32 if is_jmp32 else 64) - 1) else src - (1 << (32 if is_jmp32 else 64))
            if sdst <= ssrc:
                self.program_counter += offset - 1
                return
        # If no jump taken, just continue
        return
    
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
    
    def execute(self, bytecode: bytes, input_data: Optional[bytes] = None, 
                evm_mode: bool = False) -> int:
        """
        Execute BPF program or EVM bytecode with security controls
        
        Args:
            bytecode: BPF bytecode or EVM bytecode to execute
            input_data: Input data for the program
            evm_mode: Whether to execute as EVM bytecode
            
        Returns:
            Exit code from program or EVM execution result
        """
        if len(bytecode) == 0:
            raise BPFExecutionError("Empty bytecode")
        
        # Check if this is EVM bytecode execution
        if evm_mode:
            return self._execute_evm(bytecode, input_data or b'')
        
        # Original BPF execution
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
    
    def _execute_evm(self, bytecode: bytes, input_data: bytes) -> int:
        """Execute EVM bytecode using compatibility layer"""
        # Lazy import to avoid circular dependencies
        from .evm_compat import EVMCompatibilityLayer
        
        if not self.evm_compat:
            self.evm_compat = EVMCompatibilityLayer(self)
        
        try:
            return_data, gas_used = self.evm_compat.execute_evm_bytecode(bytecode, input_data)
            self.gas_used = gas_used
            return 0  # Success
        except Exception as e:
            raise BPFExecutionError(f"EVM execution failed: {e}")
    
    def get_evm_return_data(self) -> bytes:
        """Get return data from EVM execution"""
        if self.evm_compat:
            return self.evm_compat.return_data
        return b''
    
    def get_evm_storage(self) -> Dict[int, int]:
        """Get EVM storage state"""
        if self.evm_compat:
            return self.evm_compat.evm_storage
        return {}
    
    def reset(self):
        """Reset VM state"""
        self.gas_used = 0
        self.memory = bytearray(self.MAX_MEMORY)
        self.registers = [0] * 11
        self.stack = []
        self.program_counter = 0
        self.instructions_executed = 0
        self.is_running = False