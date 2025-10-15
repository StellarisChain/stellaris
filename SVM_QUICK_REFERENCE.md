# Stellaris SVM - Quick Reference Card

## Transaction Creation

### Deploy Contract
```python
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction

# Load contract code
with open('my_contract.py', 'r') as f:
    contract_code = f.read()

# Create transaction (code will be hex-encoded automatically)
tx = SmartContractTransaction(
    inputs=inputs,
    outputs=outputs,
    operation_type=SmartContractTransaction.OPERATION_DEPLOY,
    contract_code=contract_code,  # Plain text, will be hex-encoded
    method_args=["TokenName", "TKN", 1000000],  # Constructor args
    gas_limit=2000000
)

# Sign and submit
tx.sign([private_key])
```

### Call Contract
```python
tx = SmartContractTransaction(
    inputs=inputs,
    outputs=outputs,
    operation_type=SmartContractTransaction.OPERATION_CALL,
    contract_address="a3f8b2c1...",  # 40 hex chars
    method_name="transfer",
    method_args=["recipient_address", 1000],
    gas_limit=100000
)

tx.sign([private_key])
```

## Gas Limits

| Operation | Minimum | Recommended | Maximum |
|-----------|---------|-------------|---------|
| Simple Call | 21,000 | 50,000-100,000 | 5,000,000 |
| Complex Call | 21,000 | 200,000-500,000 | 5,000,000 |
| Deployment | 21,000 | 1,000,000-3,000,000 | 10,000,000 |

## Contract Structure

```python
from stellaris.svm.restricted_vm import SmartContract
from decimal import Decimal

class MyContract(SmartContract):
    """Contract description"""
    
    def constructor(self, sender, arg1, arg2):
        """Called once during deployment"""
        self.set_storage('key', value)
    
    def my_method(self, sender, arg1):
        """Public method - automatically exported"""
        value = self.get_storage('key')
        self.set_storage('key', new_value)
        return result
    
    def _internal_method(self, arg1):
        """Private method - NOT exported"""
        pass
```

## Storage Operations

```python
# Write (costs gas)
self.set_storage('key', value)

# Read (costs gas)
value = self.get_storage('key')

# With default
value = self.get_storage('key') or default_value

# Keys can be any string
balance_key = f'balance:{address}'
self.set_storage(balance_key, amount)
```

## Calling Other Contracts

```python
result = self.call_contract(
    address='contract_address',
    method='method_name',
    arg1, arg2, arg3
)
```

## Token Operations

```python
# Get balance
balance = self.get_balance(address)

# Send tokens FROM contract
self.send_tokens(recipient_address, amount)
```

## Common Patterns

### Access Control
```python
def my_method(self, sender, arg):
    owner = self.get_storage('owner')
    if sender != owner:
        raise ValueError("Only owner can call this")
    # ... protected code
```

### Balance Tracking
```python
def get_balance(self, sender, address):
    return self.get_storage(f'balance:{address}') or 0

def transfer(self, sender, to, amount):
    sender_balance = self.get_balance(sender, sender)
    if sender_balance < amount:
        raise ValueError("Insufficient balance")
    
    self.set_storage(f'balance:{sender}', sender_balance - amount)
    recipient_balance = self.get_balance(sender, to)
    self.set_storage(f'balance:{to}', recipient_balance + amount)
```

### Approval Pattern
```python
def approve(self, sender, spender, amount):
    key = f'allowance:{sender}:{spender}'
    self.set_storage(key, amount)
    return True

def transfer_from(self, sender, from_addr, to_addr, amount):
    allowance_key = f'allowance:{from_addr}:{sender}'
    allowance = self.get_storage(allowance_key) or 0
    
    if allowance < amount:
        raise ValueError("Insufficient allowance")
    
    # Update allowance
    self.set_storage(allowance_key, allowance - amount)
    
    # Do transfer...
```

## Validation

```python
def my_method(self, sender, amount):
    # Validate inputs
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    if amount > 1000000:
        raise ValueError("Amount too large")
    
    # ... process
```

## Error Handling

```python
def safe_method(self, sender, arg):
    try:
        result = risky_operation(arg)
        return result
    except ValueError as e:
        # Handle specific error
        return None
    except Exception as e:
        # Log and re-raise
        raise SVMError(f"Unexpected error: {e}")
```

## API Endpoints

### Deploy
```bash
curl -X POST http://localhost:3006/deploy_contract \
  -H "Content-Type: application/json" \
  -d '{"transaction_hex": "04..."}'
```

### Call
```bash
curl -X POST http://localhost:3006/call_contract \
  -H "Content-Type: application/json" \
  -d '{"transaction_hex": "04..."}'
```

### Query State
```bash
curl http://localhost:3006/contract_state?address=a3f8b2...
```

## Allowed Imports

```python
from decimal import Decimal
from datetime import datetime, date, time, timedelta
from hashlib import sha256, md5, sha1
import json
import math
import re
from typing import List, Dict, Optional, Union, Any
```

## Gas Costs (approximate)

```python
# Storage operations (most expensive)
self.set_storage(key, value)  # ~2000 gas
value = self.get_storage(key)  # ~1000 gas

# Computation (cheap)
result = a + b + c  # ~100 gas per operation

# Method call
self.my_method()  # ~1000 gas base cost

# Token transfer
self.send_tokens(to, amount)  # ~9000 gas
```

## Testing Pattern

```python
import pytest
from stellaris.svm.vm_manager import StellarisVMManager

@pytest.fixture
async def vm_manager():
    return StellarisVMManager()

async def test_deployment(vm_manager):
    tx = create_deployment_tx()
    result = await vm_manager.deploy_contract(tx, deployer)
    assert result.success
    assert result.gas_used < tx.gas_limit

async def test_method_call(vm_manager, contract_address):
    tx = create_call_tx(contract_address, "transfer", [recipient, 1000])
    result = await vm_manager.call_contract(tx, caller)
    assert result.success
    assert result.result == True
```

## Common Errors

| Error | Meaning | Fix |
|-------|---------|-----|
| Out of gas | Gas limit too low | Increase gas_limit |
| Method not exported | Private method or typo | Check method name, remove _ prefix |
| Invalid contract address | Wrong format | Must be 40 hex characters |
| Contract code too large | Code > 1MB | Split into multiple contracts |
| Insufficient balance | Not enough tokens | Check balance before operation |

## Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check execution result
if not result.success:
    print(f"Error: {result.error}")
    print(f"Gas used: {result.gas_used}")
```

## Best Practices

1. ✅ **Validate all inputs** in every method
2. ✅ **Check balances** before transfers
3. ✅ **Use explicit errors** with helpful messages
4. ✅ **Test thoroughly** before deployment
5. ✅ **Optimize gas** by minimizing storage ops
6. ✅ **Document your contract** with docstrings
7. ✅ **Handle edge cases** (zero amounts, etc.)
8. ✅ **Implement access control** for sensitive ops
9. ✅ **Keep it simple** - complexity = bugs
10. ✅ **Test with realistic gas limits**

## Resources

- **Full Documentation**: `/stellaris/svm/README.md`
- **Production Guide**: `/SVM_PRODUCTION_GUIDE.md`
- **Examples**: `/examples/` directory
- **API Docs**: `http://localhost:3006/docs`

---

**Version**: 1.0.0 | **License**: MIT | **Support**: GitHub Issues
