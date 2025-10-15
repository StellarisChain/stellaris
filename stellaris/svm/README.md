# Stellaris Virtual Machine (SVM) - Technical Reference

## Architecture Overview

The Stellaris Virtual Machine (SVM) is a production-grade smart contract execution environment built for the Stellaris blockchain. It provides secure, isolated execution of Python-based smart contracts with comprehensive resource management and gas metering.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Transaction Layer                         │
│  - SmartContractTransaction (hex-encoded code)              │
│  - Validation and serialization                             │
│  - Fee calculation                                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     VM Manager Layer                         │
│  - Transaction routing                                       │
│  - VM pool management                                        │
│  - State persistence                                         │
│  - Comprehensive validation                                  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  RestrictedPython VM Layer                   │
│  - Secure code compilation                                   │
│  - Sandboxed execution                                       │
│  - Gas metering                                              │
│  - Resource limits                                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Blockchain Interface                       │
│  - State queries                                             │
│  - Balance management                                        │
│  - Block data access                                         │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
stellaris/
├── svm/
│   ├── __init__.py
│   ├── restricted_vm.py          # Core VM with RestrictedPython
│   ├── vm.py                     # Alternative VM implementation
│   ├── vm_manager.py             # VM pooling and orchestration
│   ├── sc_processor.py           # Transaction processor
│   ├── transaction_builder.py   # Transaction creation utilities
│   ├── blockchain_interface.py  # Blockchain data access
│   ├── exceptions.py             # Custom exception types
│   └── scaler.py                 # Scaling utilities
├── transactions/
│   └── smart_contract_transaction.py  # Smart contract tx definition
└── node/
    └── routes/
        └── transactions.py       # API endpoints
```

## Key Classes

### SmartContractTransaction

Represents a smart contract operation (deployment or call).

**Key Features:**
- Hex-encoded contract code
- Automatic validation on initialization
- Deterministic address generation
- Gas limit enforcement
- JSON serialization support

**Usage:**
```python
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction

# Deployment transaction
tx = SmartContractTransaction(
    inputs=[...],
    outputs=[...],
    operation_type=SmartContractTransaction.OPERATION_DEPLOY,
    contract_code=hex_encoded_code,  # Already hex-encoded
    method_args=["TokenName", "TKN", 1000000],
    gas_limit=2000000
)

# Call transaction
tx = SmartContractTransaction(
    inputs=[...],
    outputs=[...],
    operation_type=SmartContractTransaction.OPERATION_CALL,
    contract_address="a3f8...",
    method_name="transfer",
    method_args=["recipient", 1000],
    gas_limit=100000
)
```

### StellarisVMManager

Manages VM instances, handles execution, and provides high-level API.

**Key Features:**
- VM pooling for efficiency
- Automatic validation
- State persistence
- Execution statistics
- Thread-safe operations

**Usage:**
```python
from stellaris.svm.vm_manager import StellarisVMManager

manager = StellarisVMManager(
    database=db,
    max_workers=4,
    vm_pool_size=8,
    enable_caching=True
)

# Deploy contract
result = await manager.deploy_contract(transaction, sender_address)
if result.success:
    print(f"Deployed at: {result.result}")
    print(f"Gas used: {result.gas_used}")

# Call contract
result = await manager.call_contract(transaction, sender_address)
if result.success:
    print(f"Result: {result.result}")
    print(f"Gas used: {result.gas_used}")
```

### RestrictedStellarisVM

The core VM that executes contract code securely.

**Key Features:**
- RestrictedPython compilation
- Whitelisted imports
- Resource limits
- Gas metering
- Execution context isolation

**Security Model:**
```python
# Allowed imports (whitelisted)
ALLOWED_MODULES = {
    'decimal': ['Decimal'],
    'datetime': ['datetime', 'date', 'time', 'timedelta'],
    'hashlib': ['sha256', 'md5', 'sha1'],
    'json': ['loads', 'dumps'],
    'math': ['sqrt', 'pow', 'abs', 'floor', 'ceil', 'round'],
}

# Forbidden attributes (blacklisted)
FORBIDDEN_ATTRS = {
    '__import__', '__builtins__', '__globals__', '__locals__',
    '__dict__', '__class__', '__bases__', '__mro__',
    'exec', 'eval', 'compile', 'open', 'file'
}
```

## Gas Model

### Gas Costs

| Operation | Cost (tokens) | Description |
|-----------|---------------|-------------|
| Base Call | 0.0001 | Fixed cost for any method invocation |
| Storage Write | 0.002 | Writing to persistent storage |
| Storage Read | 0.001 | Reading from persistent storage |
| Memory Word | 0.0003 | Per-word memory allocation |
| Computation | 0.0001 | General computation cost |
| Transfer | 0.9 | Transferring tokens between addresses |
| Contract Creation | 1.0 | Deploying a new contract |

### Gas Limits

| Transaction Type | Minimum | Maximum | Typical |
|-----------------|---------|---------|---------|
| Deployment | 21,000 | 10,000,000 | 1,000,000 - 3,000,000 |
| Call | 21,000 | 5,000,000 | 50,000 - 500,000 |

### Gas Calculation

```python
# Gas fee calculation
gas_price = Decimal('0.000001')  # 1 micro-token per gas unit
gas_used = 100000
gas_fee = gas_used * gas_price  # 0.1 tokens
```

## Contract Development

### Basic Contract Structure

```python
from stellaris.svm.restricted_vm import SmartContract
from decimal import Decimal

class MyToken(SmartContract):
    """
    Simple token contract
    
    All public methods (not starting with _) are automatically exported
    """
    
    def constructor(self, sender, name: str, symbol: str, total_supply: int):
        """
        Contract constructor - called once during deployment
        
        Args:
            sender: Deployer address
            name: Token name
            symbol: Token symbol
            total_supply: Initial token supply
        """
        # Store initial state
        self.set_storage('name', name)
        self.set_storage('symbol', symbol)
        self.set_storage('total_supply', total_supply)
        
        # Assign all tokens to deployer
        balance_key = f'balance:{sender}'
        self.set_storage(balance_key, total_supply)
        
    def get_balance(self, sender, address: str) -> int:
        """
        Get token balance of an address (view function)
        
        Args:
            sender: Caller address (unused in view functions)
            address: Address to query
            
        Returns:
            Token balance
        """
        balance_key = f'balance:{address}'
        return self.get_storage(balance_key) or 0
    
    def transfer(self, sender, to: str, amount: int) -> bool:
        """
        Transfer tokens from sender to recipient
        
        Args:
            sender: Caller address (sender of tokens)
            to: Recipient address
            amount: Amount to transfer
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If insufficient balance
        """
        # Validate
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Check balance
        sender_balance = self.get_balance(sender, sender)
        if sender_balance < amount:
            raise ValueError(f"Insufficient balance: {sender_balance} < {amount}")
        
        # Update balances
        sender_key = f'balance:{sender}'
        recipient_key = f'balance:{to}'
        
        self.set_storage(sender_key, sender_balance - amount)
        
        recipient_balance = self.get_balance(sender, to)
        self.set_storage(recipient_key, recipient_balance + amount)
        
        return True
```

### Storage Operations

```python
# Write to storage (costs gas)
self.set_storage('key', value)

# Read from storage (costs gas)
value = self.get_storage('key')

# Get with default
value = self.get_storage('key') or default_value
```

### Calling Other Contracts

```python
# Call another contract's method
result = self.call_contract(
    address='contract_address',
    method='method_name',
    arg1, arg2, arg3
)
```

### Getting Blockchain Data

```python
# Get address balance
balance = self.get_balance(address)

# Send tokens from contract
self.send_tokens(recipient, amount)
```

## API Integration

### Deploy Contract Endpoint

```bash
POST /deploy_contract
Content-Type: application/json

{
  "transaction_hex": "04..." # Hex-encoded SmartContractTransaction
}
```

**Response:**
```json
{
  "success": true,
  "transaction_hash": "abc123...",
  "contract_address": "a3f8b2...",
  "gas_used": 1500000,
  "deployment_address": "a3f8b2..."
}
```

### Call Contract Endpoint

```bash
POST /call_contract  
Content-Type: application/json

{
  "transaction_hex": "04..." # Hex-encoded SmartContractTransaction
}
```

**Response:**
```json
{
  "success": true,
  "transaction_hash": "def456...",
  "result": true,
  "gas_used": 75000,
  "return_value": {"success": true, "data": "..."}
}
```

### Query Contract State

```bash
GET /contract_state?address=<contract_address>
```

**Response:**
```json
{
  "address": "a3f8b2...",
  "storage": {
    "name": "MyToken",
    "symbol": "MTK",
    "total_supply": 1000000
  },
  "balance": "0.0",
  "deployed_by": "deployer_address",
  "deployment_block": 12345
}
```

## Error Handling

### Exception Types

```python
from stellaris.svm.exceptions import (
    SVMError,              # Base exception
    SVMSecurityError,      # Security policy violation
    SVMResourceError,      # Resource limit exceeded
    SVMTimeoutError,       # Execution timeout
    SVMMemoryError,        # Memory limit exceeded
    SVMGasError,           # Out of gas
    SVMValidationError,    # Validation failed
    SVMContractError,      # Contract execution error
    SVMInvalidCallError    # Invalid method call
)
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Out of gas | Gas limit too low | Increase gas limit or optimize contract |
| Contract code too large | Code exceeds 1MB | Split into multiple contracts or optimize |
| Method not exported | Method not public | Remove leading underscore from method name |
| Invalid contract address | Address format wrong | Verify 40 hex character address |
| Forbidden attribute access | Accessing private attributes | Use public API only |

## Performance Optimization

### Contract Code Optimization

```python
# BAD: Multiple storage reads in loop
def bad_sum(self, sender):
    total = 0
    for i in range(100):
        total += self.get_storage(f'value_{i}')  # 100 storage reads
    return total

# GOOD: Minimize storage operations
def good_sum(self, sender):
    values = []
    for i in range(100):
        values.append(self.get_storage(f'value_{i}'))
    return sum(values)  # Compute in memory
```

### Batch Operations

```python
# Process multiple operations in one transaction
def batch_transfer(self, sender, recipients: list, amounts: list):
    for recipient, amount in zip(recipients, amounts):
        self.transfer(sender, recipient, amount)
```

### Caching

```python
# Cache frequently accessed values
def get_cached_value(self, sender):
    # Check if we have it in memory first
    if not hasattr(self, '_cached_value'):
        self._cached_value = self.get_storage('expensive_to_compute')
    return self._cached_value
```

## Testing

### Unit Testing Contracts

```python
import pytest
from stellaris.svm.vm_manager import StellarisVMManager
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction

@pytest.fixture
async def vm_manager():
    return StellarisVMManager()

async def test_token_deployment(vm_manager):
    # Create deployment transaction
    tx = SmartContractTransaction(
        inputs=[...],
        outputs=[...],
        operation_type=SmartContractTransaction.OPERATION_DEPLOY,
        contract_code=token_code_hex,
        method_args=["TestToken", "TEST", 1000000],
        gas_limit=2000000
    )
    
    # Deploy
    result = await vm_manager.deploy_contract(tx, deployer_address)
    
    # Assertions
    assert result.success
    assert result.gas_used > 0
    assert result.gas_used <= 2000000
    assert len(result.result) == 40  # Contract address

async def test_token_transfer(vm_manager, contract_address):
    # Create call transaction
    tx = SmartContractTransaction(
        inputs=[...],
        outputs=[...],
        operation_type=SmartContractTransaction.OPERATION_CALL,
        contract_address=contract_address,
        method_name="transfer",
        method_args=[recipient, 1000],
        gas_limit=100000
    )
    
    # Execute
    result = await vm_manager.call_contract(tx, sender_address)
    
    # Assertions
    assert result.success
    assert result.result == True
    assert result.gas_used < 100000
```

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Monitor VM Statistics

```python
# Get VM pool stats
stats = vm_manager.get_stats()
print(f"Total VMs: {stats.total_vms}")
print(f"Active VMs: {stats.active_vms}")
print(f"Total executions: {stats.total_executions}")
print(f"Avg execution time: {stats.avg_execution_time}s")
print(f"Total gas used: {stats.total_gas_used}")
```

### Execution Traces

```python
# View detailed execution trace
logger.setLevel(logging.DEBUG)
result = await vm_manager.deploy_contract(tx, sender)
# Logs will show:
# - Validation steps
# - Code compilation
# - Gas consumption
# - State changes
# - Execution time
```

## Security Best Practices

### For Contract Developers

1. **Validate all inputs** in constructor and methods
2. **Use checks-effects-interactions pattern**
3. **Implement access control** for sensitive operations
4. **Handle edge cases** explicitly (zero amounts, etc.)
5. **Avoid reentrancy** by updating state before external calls
6. **Test thoroughly** with various inputs and scenarios

### For Node Operators

1. **Monitor gas usage** for anomalies
2. **Set appropriate rate limits** on API endpoints
3. **Configure resource limits** based on hardware
4. **Enable security logging** for audit trails
5. **Keep VM pool size** appropriate for load
6. **Regular security updates** to dependencies

## FAQ

**Q: What happens if a contract runs out of gas?**
A: Execution stops immediately, all state changes are reverted, and an `SVMGasError` is raised.

**Q: Can contracts import arbitrary Python modules?**
A: No, only whitelisted modules can be imported for security.

**Q: How is contract code stored?**
A: Contract code is hex-encoded and stored in the blockchain database.

**Q: Can contracts call other contracts?**
A: Yes, using the `call_contract()` method.

**Q: What's the maximum contract size?**
A: 1 MB of source code.

**Q: Are there any restrictions on Python features?**
A: Yes, certain features like `eval`, `exec`, `open`, and system access are forbidden.

**Q: How do I estimate gas for a transaction?**
A: Deploy to testnet first and observe gas usage, then add 20-30% buffer.

## Support

- **Documentation**: This file and `/docs` endpoint
- **Examples**: `/examples` directory  
- **Issues**: GitHub Issues
- **Community**: Discord/Telegram

---

**Version**: 1.0.0 (Production Ready)  
**Last Updated**: 2025-01-14
