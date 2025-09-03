"""
Stellaris Virtual Machine exceptions for secure smart contract execution
"""

class SVMError(Exception):
    """Base exception for SVM execution errors"""
    def __init__(self, message: str, contract_address: str = None, method_name: str = None):
        self.message = message
        self.contract_address = contract_address
        self.method_name = method_name
        super().__init__(self.message)
    
    def __str__(self):
        base_msg = self.message
        if self.contract_address:
            base_msg += f" (Contract: {self.contract_address})"
        if self.method_name:
            base_msg += f" (Method: {self.method_name})"
        return base_msg

class SVMSecurityError(SVMError):
    """Exception for security violations in smart contract execution"""
    def __init__(self, message: str, violation_type: str = None, **kwargs):
        self.violation_type = violation_type
        super().__init__(message, **kwargs)

class SVMResourceError(SVMError):
    """Exception for resource limit violations"""
    def __init__(self, message: str, resource_type: str = None, limit: int = None, current: int = None, **kwargs):
        self.resource_type = resource_type
        self.limit = limit
        self.current = current
        super().__init__(message, **kwargs)

class SVMTimeoutError(SVMResourceError):
    """Exception for execution timeout"""
    def __init__(self, message: str = "Execution timeout", timeout_seconds: float = None, **kwargs):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, resource_type="time", **kwargs)

class SVMMemoryError(SVMResourceError):
    """Exception for memory limit violations"""
    def __init__(self, message: str = "Memory limit exceeded", memory_used: int = None, memory_limit: int = None, **kwargs):
        self.memory_used = memory_used
        self.memory_limit = memory_limit
        super().__init__(message, resource_type="memory", limit=memory_limit, current=memory_used, **kwargs)

class SVMGasError(SVMResourceError):
    """Exception for gas limit violations"""
    def __init__(self, message: str = "Gas limit exceeded", gas_used: int = None, gas_limit: int = None, **kwargs):
        self.gas_used = gas_used
        self.gas_limit = gas_limit
        super().__init__(message, resource_type="gas", limit=gas_limit, current=gas_used, **kwargs)

class SVMValidationError(SVMError):
    """Exception for smart contract validation errors"""
    def __init__(self, message: str, validation_type: str = None, line_number: int = None, **kwargs):
        self.validation_type = validation_type
        self.line_number = line_number
        super().__init__(message, **kwargs)

class SVMContractError(SVMError):
    """Exception for contract-specific errors"""
    def __init__(self, message: str, error_type: str = None, **kwargs):
        self.error_type = error_type
        super().__init__(message, **kwargs)

class SVMInvalidCallError(SVMError):
    """Exception for invalid contract calls"""
    def __init__(self, message: str, call_type: str = None, available_methods: list = None, **kwargs):
        self.call_type = call_type
        self.available_methods = available_methods or []
        super().__init__(message, **kwargs)

class SVMInsufficientBalanceError(SVMError):
    """Exception for insufficient balance operations"""
    def __init__(self, message: str, required_balance: str = None, current_balance: str = None, address: str = None, **kwargs):
        self.required_balance = required_balance
        self.current_balance = current_balance
        self.address = address
        super().__init__(message, **kwargs)