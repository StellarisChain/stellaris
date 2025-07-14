# Solidity and Hardhat Integration Guide

This guide shows how to use Solidity smart contracts and Hardhat development framework with the Stellaris blockchain.

## Overview

The Stellaris BPF VM now supports EVM-compatible smart contracts, allowing developers to:

- Write smart contracts in Solidity
- Use Hardhat for development and testing
- Deploy contracts using familiar Web3 tools
- Interact with contracts using Web3.js or ethers.js

## Key Features

### 🔧 **EVM Compatibility Layer**
- Executes EVM bytecode within the secure BPF VM
- Supports standard EVM opcodes and operations
- Maintains security boundaries and gas limits

### 📋 **Solidity ABI Support**
- Encodes/decodes function calls using Solidity ABI
- Supports standard data types (uint256, address, bool, etc.)
- Handles both view and state-changing functions

### 🌐 **Web3-Compatible API**
- Standard JSON-RPC endpoints for Web3 integration
- Compatible with Hardhat, Truffle, and other tools
- Maintains Stellaris' unique transaction model

## Setup Instructions

### 1. Configure Hardhat

Create a `hardhat.config.js` file:

```javascript
require("@nomiclabs/hardhat-waffle");

module.exports = {
  solidity: "0.8.4",
  networks: {
    stellaris: {
      url: "http://localhost:3006",
      chainId: 1337,
      accounts: [
        // Add your private keys here
        "0x1234567890123456789012345678901234567890123456789012345678901234"
      ]
    }
  }
};
```

### 2. Write Solidity Contracts

Example contract (`contracts/SimpleStorage.sol`):

```solidity
pragma solidity ^0.8.0;

contract SimpleStorage {
    uint256 public value;
    
    function setValue(uint256 _value) public {
        value = _value;
    }
    
    function getValue() public view returns (uint256) {
        return value;
    }
}
```

### 3. Deploy with Hardhat

```bash
npx hardhat compile
npx hardhat run scripts/deploy.js --network stellaris
```

## API Endpoints

### Stellaris Native Endpoints

#### Deploy Contract
```http
POST /deploy_contract
Content-Type: application/json

{
  "bytecode": "0x608060405234801561001057600080fd5b50...",
  "abi": [...],
  "inputs": [{"tx_hash": "0x...", "index": 0}],
  "outputs": [{"address": "0x...", "amount": "0"}],
  "gas_limit": 1000000,
  "contract_type": "evm"
}
```

#### Call Contract
```http
POST /call_contract
Content-Type: application/json

{
  "contract_address": "0x...",
  "function_name": "setValue",
  "args": [42],
  "inputs": [{"tx_hash": "0x...", "index": 0}],
  "outputs": [{"address": "0x...", "amount": "0"}],
  "gas_limit": 100000
}
```

### Web3-Compatible Endpoints

#### Send Transaction
```http
POST /eth_sendTransaction
Content-Type: application/json

{
  "data": "0x608060405234801561001057600080fd5b50...",
  "gas": "0xF4240"
}
```

#### Call Contract (View)
```http
POST /eth_call
Content-Type: application/json

{
  "to": "0x...",
  "data": "0x3fa4f245"
}
```

#### Get Transaction Receipt
```http
POST /eth_getTransactionReceipt
Content-Type: application/json

"0x1234567890123456789012345678901234567890123456789012345678901234"
```

## JavaScript Integration

### Using Web3.js

```javascript
const Web3 = require('web3');
const web3 = new Web3('http://localhost:3006');

// Deploy contract
const contract = new web3.eth.Contract(abi);
const deployTx = contract.deploy({
    data: bytecode,
    arguments: []
});

// Call contract function
const result = await contract.methods.getValue().call();
```

### Using ethers.js

```javascript
const { ethers } = require('ethers');

const provider = new ethers.providers.JsonRpcProvider('http://localhost:3006');
const wallet = new ethers.Wallet(privateKey, provider);

// Deploy contract
const factory = new ethers.ContractFactory(abi, bytecode, wallet);
const contract = await factory.deploy();

// Call contract function
const result = await contract.getValue();
```

## Example Usage

Run the included example:

```bash
python examples/solidity_example.py
```

This example demonstrates:
- Deploying a SimpleStorage contract
- Calling contract functions
- Using Web3-compatible endpoints
- Testing with different interfaces

## Development Workflow

### 1. Local Development

```bash
# Start Stellaris node
python run_node.py

# In another terminal, run your Hardhat project
npx hardhat test --network stellaris
```

### 2. Contract Testing

```javascript
// test/SimpleStorage.js
const { expect } = require("chai");

describe("SimpleStorage", function () {
  it("Should set and get value", async function () {
    const SimpleStorage = await ethers.getContractFactory("SimpleStorage");
    const storage = await SimpleStorage.deploy();
    
    await storage.setValue(42);
    expect(await storage.getValue()).to.equal(42);
  });
});
```

### 3. Migration Scripts

```javascript
// scripts/deploy.js
async function main() {
  const SimpleStorage = await ethers.getContractFactory("SimpleStorage");
  const storage = await SimpleStorage.deploy();
  
  console.log("SimpleStorage deployed to:", storage.address);
}

main().catch(console.error);
```

## Security Considerations

### Gas Limits
- All contracts execute within BPF VM gas limits
- Default gas limit is 100,000 units
- Configurable per contract and transaction

### Memory Safety
- EVM memory operations are bounded
- Stack overflow protection
- Execution timeout enforcement

### State Isolation
- Contract states are properly isolated
- Atomic updates with rollback on failure
- Secure inter-contract communication

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure Stellaris node is running on port 3006
   - Check firewall and network settings

2. **Invalid Bytecode**
   - Verify Solidity compiler version compatibility
   - Check bytecode format and length

3. **Gas Limit Exceeded**
   - Increase gas limit in deployment/call
   - Optimize contract code for efficiency

4. **Function Not Found**
   - Verify ABI matches deployed contract
   - Check function name spelling and signature

### Debug Mode

Enable debug logging for detailed execution traces:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Limitations

### Current Limitations

1. **EVM Precompiles**: Not all EVM precompiled contracts are supported
2. **Block Properties**: Some block-specific properties return mock values
3. **Events**: Contract events are not fully implemented
4. **CREATE2**: Advanced deployment patterns not yet supported

### Planned Improvements

- Full EVM precompile support
- Event logging and filtering
- Advanced debugging tools
- Performance optimizations

## Contributing

The Solidity integration is actively developed. To contribute:

1. Test with your Solidity contracts
2. Report issues and compatibility problems
3. Submit pull requests for improvements
4. Help with documentation and examples

## Support

For help with Solidity integration:

- Check the troubleshooting section
- Review example contracts and tests
- Open GitHub issues for bugs
- Join the Stellaris community discussions