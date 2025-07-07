"""
BPF VM module for Stellaris blockchain
Provides secure execution environment for BPF programs and EVM/Solidity compatibility
"""

from .vm import BPFVirtualMachine
from .executor import BPFExecutor
from .contract import BPFContract
from .exceptions import BPFExecutionError, BPFSecurityError, BPFResourceError
from .evm_compat import EVMCompatibilityLayer
from .solidity_abi import SolidityABI

__all__ = [
    'BPFVirtualMachine',
    'BPFExecutor', 
    'BPFContract',
    'BPFExecutionError',
    'BPFSecurityError',
    'BPFResourceError',
    'EVMCompatibilityLayer',
    'SolidityABI'
]