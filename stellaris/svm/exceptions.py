"""
BPF VM exceptions for secure error handling
"""

class BPFExecutionError(Exception):
    """Base exception for BPF execution errors"""
    pass

class BPFSecurityError(BPFExecutionError):
    """Exception for security violations in BPF execution"""
    pass

class BPFResourceError(BPFExecutionError):
    """Exception for resource limit violations"""
    pass

class BPFTimeoutError(BPFResourceError):
    """Exception for execution timeout"""
    pass

class BPFMemoryError(BPFResourceError):
    """Exception for memory limit violations"""
    pass

class BPFGasError(BPFResourceError):
    """Exception for gas limit violations"""
    pass

class BPFValidationError(BPFExecutionError):
    """Exception for BPF program validation errors"""
    pass