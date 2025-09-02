"""
Stellaris Virtual Machine exceptions for secure smart contract execution
"""

class SVMError(Exception):
    """Base exception for SVM execution errors"""
    pass

class SVMSecurityError(SVMError):
    """Exception for security violations in smart contract execution"""
    pass

class SVMResourceError(SVMError):
    """Exception for resource limit violations"""
    pass

class SVMTimeoutError(SVMResourceError):
    """Exception for execution timeout"""
    pass

class SVMMemoryError(SVMResourceError):
    """Exception for memory limit violations"""
    pass

class SVMGasError(SVMResourceError):
    """Exception for gas limit violations"""
    pass

class SVMValidationError(SVMError):
    """Exception for smart contract validation errors"""
    pass

class SVMContractError(SVMError):
    """Exception for contract-specific errors"""
    pass

class SVMInvalidCallError(SVMError):
    """Exception for invalid contract calls"""
    pass

class SVMInsufficientBalanceError(SVMError):
    """Exception for insufficient balance operations"""
    pass