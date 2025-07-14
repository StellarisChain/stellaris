# BPF VM Support for Stellaris Blockchain

This document describes the BPF (Berkeley Packet Filter) VM implementation for the Stellaris blockchain, providing secure smart contract functionality with full **Solidity and Hardhat compatibility**.

## Overview

The BPF VM implementation adds smart contract capabilities to Stellaris while maintaining strict security standards. It provides:

- **Secure Execution Environment**: Sandboxed BPF virtual machine with resource limits
- **EVM Compatibility**: Full support for Solidity contracts and EVM bytecode
- **Gas-based Economics**: Resource consumption tracking to prevent DoS attacks
- **Transaction Integration**: Seamless integration with existing transaction system
- **State Management**: Persistent contract state with atomicity guarantees
- **Web3 API**: RESTful and JSON-RPC endpoints for Hardhat/Web3.js integration
- **Development Tools**: Compatible with Hardhat, Truffle, and other Ethereum tools

## Quick Start with Solidity

### 1. Deploy a Solidity Contract

```bash
# Configure Hardhat for Stellaris
npx hardhat init

# Edit hardhat.config.js to point to http://localhost:3006
# Deploy your contracts
npx hardhat run scripts/deploy.js --network stellaris
```

### 2. Interact with Web3.js

```javascript
const Web3 = require('web3');
const web3 = new Web3('http://localhost:3006');

// Deploy and interact with contracts as usual
const contract = new web3.eth.Contract(abi, address);
const result = await contract.methods.myFunction().call();
```

For detailed Solidity integration, see [SOLIDITY_INTEGRATION.md](SOLIDITY_INTEGRATION.md)

## Architecture

### Components

1. **BPF Virtual Machine** (`stellaris/bpf_vm/vm.py`)
   - Secure bytecode execution environment
   - Resource limit enforcement (gas, memory, time)
   - Instruction validation and execution
   - Security boundary enforcement

2. **Contract Management** (`stellaris/bpf_vm/contract.py`)
   - Contract representation and validation
   - ABI (Application Binary Interface) management
   - State serialization and persistence
   - Address generation and verification

3. **Executor** (`stellaris/bpf_vm/executor.py`)
   - Contract deployment coordination
   - Function call execution
   - Gas estimation capabilities
   - Transaction context management

4. **Transaction Extension** (`stellaris/transactions/bpf_contract_transaction.py`)
   - New transaction type for BPF contracts
   - Deploy and call operation support
   - Integrated validation pipeline
   - Gas limit enforcement

## Security Features

### Resource Management

- **Gas Limits**: Configurable gas limits prevent infinite loops and resource exhaustion
- **Memory Bounds**: 1MB memory limit with bounds checking on all accesses
- **Execution Time**: 5-second timeout prevents long-running operations
- **Instruction Limits**: Maximum 10,000 instructions per execution
- **Stack Protection**: 256-level stack depth limit prevents overflow

### Input Validation

- **Bytecode Validation**: Size limits and format verification
- **ABI Verification**: Function signature and type validation
- **Argument Checking**: Type and range validation for function arguments
- **Address Validation**: Proper address format enforcement

### Isolation

- **Sandboxed Execution**: Contracts run in isolated environment
- **State Isolation**: Contract states are independent and protected
- **Controlled Syscalls**: Limited set of allowed system operations
- **Error Containment**: Failures are contained and don't affect other contracts

## Usage

### Contract Deployment

Deploy a new BPF contract using the REST API:

```bash
curl -X POST http://localhost:3006/deploy_contract \
  -H "Content-Type: application/json" \
  -d '{
    "bytecode": "950000002A000000",
    "abi": {
      "functions": {
        "getValue": {
          "inputs": [],
          "outputs": [{"type": "uint256"}]
        }
      }
    },
    "inputs": [{
      "tx_hash": "previous_transaction_hash",
      "index": 0
    }],
    "outputs": [{
      "address": "recipient_address",
      "amount": "1.0"
    }],
    "gas_limit": 100000
  }'
```

### Contract Execution

Call a deployed contract function:

```bash
curl -X POST http://localhost:3006/call_contract \
  -H "Content-Type: application/json" \
  -d '{
    "contract_address": "contract_address_here",
    "function_name": "getValue",
    "args": [],
    "inputs": [{
      "tx_hash": "previous_transaction_hash",
      "index": 0
    }],
    "outputs": [{
      "address": "recipient_address", 
      "amount": "1.0"
    }],
    "gas_limit": 50000
  }'
```

### Contract Information

Retrieve contract details:

```bash
curl http://localhost:3006/get_contract?address=contract_address_here
```

### Gas Estimation

Estimate gas needed for contract execution:

```bash
curl -X POST http://localhost:3006/estimate_gas \
  -H "Content-Type: application/json" \
  -d '{
    "contract_address": "contract_address_here",
    "function_name": "getValue",
    "args": [],
    "caller": "caller_address"
  }'
```

## Development

### Running Tests

```bash
cd stellaris
python tests/run_tests.py
```

### Example Usage

```bash
python examples/bpf_vm_example.py
```

### Creating Custom Contracts

1. Write BPF bytecode (or compile from higher-level language)
2. Define ABI specifying function signatures
3. Deploy using the deployment API
4. Interact using the call API

## BPF Bytecode Format

The VM supports a subset of BPF instructions:

- **Load/Store**: Memory access operations
- **ALU**: Arithmetic and logical operations  
- **Jump**: Control flow operations
- **Return**: Function return

### Instruction Encoding

Instructions are 8 bytes with the following format:
- Opcode (8 bits): Instruction type
- Destination register (4 bits)
- Source register (4 bits)
- Offset (16 bits): Memory offset or jump target
- Immediate value (32 bits): Constant operand

### Registers

The VM provides 11 registers (r0-r10):
- r0: Return value register
- r1-r5: Function argument registers
- r6-r9: General purpose registers
- r10: Stack frame pointer

## Gas Costs

Different operations consume different amounts of gas:

- Basic instructions: 1 gas
- Memory operations: 1 gas + memory access cost
- Function calls: Base cost + argument processing
- Storage operations: Higher cost for persistence

## Error Handling

The VM provides comprehensive error handling:

- `BPFExecutionError`: General execution failures
- `BPFSecurityError`: Security violations
- `BPFResourceError`: Resource limit exceeded
- `BPFGasError`: Gas limit exceeded
- `BPFTimeoutError`: Execution timeout
- `BPFMemoryError`: Memory access violation

## Integration with Blockchain

BPF contracts are fully integrated with the Stellaris blockchain:

1. **Transaction Processing**: Contracts execute during block validation
2. **State Persistence**: Contract state is stored in the blockchain database
3. **Fee System**: Gas costs are converted to transaction fees
4. **Consensus**: Contract execution results must be deterministic across nodes

## Performance Considerations

- **Bytecode Size**: Keep contracts small for faster deployment and execution
- **Gas Optimization**: Optimize algorithms to minimize gas consumption
- **State Access**: Minimize state reads/writes for better performance
- **Memory Usage**: Use memory efficiently within the 1MB limit

## Security Best Practices

1. **Input Validation**: Always validate inputs in contract functions
2. **Gas Limits**: Set appropriate gas limits for contract operations
3. **Error Handling**: Handle all possible error conditions gracefully
4. **State Management**: Ensure atomic state updates
5. **Testing**: Thoroughly test contracts before deployment

## Future Enhancements

Potential future improvements:

- **Higher-level Languages**: Compilers for Rust, C, or domain-specific languages
- **Debugging Tools**: Enhanced debugging and profiling capabilities
- **Optimizations**: JIT compilation for improved performance
- **Advanced Features**: Inter-contract calls, events, and upgradeable contracts
- **Formal Verification**: Mathematical proofs of contract correctness

## Conclusion

The BPF VM implementation provides Stellaris with secure, efficient smart contract capabilities while maintaining the blockchain's security and performance characteristics. The security-first design ensures safe execution of untrusted code while the gas system prevents resource abuse.

For questions or contributions, please refer to the project's GitHub repository.