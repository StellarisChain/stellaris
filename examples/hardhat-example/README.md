# Hardhat Example for Stellaris

This comprehensive example demonstrates how to use Hardhat with Stellaris blockchain for professional Solidity development, featuring complete ERC-20 token implementations with advanced features.

## 🚀 Quick Start

### Prerequisites
- Node.js v14+ installed
- Stellaris node running on `http://localhost:3006`

### Installation
```bash
npm install
```

### Configuration
Edit `hardhat.config.js` and add your private keys to the `accounts` array.

### Start Stellaris Node
```bash
# From the main stellaris directory
python run_node.py
```

## 📋 Available Scripts

### Basic Operations
```bash
npm run compile          # Compile all contracts
npm run test             # Run comprehensive test suite
npm run deploy           # Deploy SimpleStorage contract
npm run deploy:advanced  # Deploy complete ERC-20 suite
npm run deploy:erc20     # Deploy ERC-20 tokens (alias)
```

## 📁 Project Structure

```
contracts/
├── SimpleStorage.sol      # Basic contract example
├── StellarisToken.sol     # Full-featured ERC-20 token
└── AdvancedERC20.sol      # Advanced ERC-20 with extras

scripts/
├── deploy.js              # Basic deployment script
└── deploy-advanced.js     # Comprehensive deployment

test/
├── SimpleStorage.test.js  # Basic contract tests
└── ERC20.test.js         # Comprehensive ERC-20 tests
```

## 🪙 Smart Contract Features

### StellarisToken.sol
- ✅ Complete ERC-20 implementation
- ✅ Mintable and burnable tokens
- ✅ Pausable transfers
- ✅ Ownership controls
- ✅ Multi-transfer functionality
- ✅ Comprehensive event emission

### AdvancedERC20.sol
- ✅ All StellarisToken features
- ✅ Supply cap management
- ✅ Minter role system
- ✅ Blacklist functionality
- ✅ Batch operations
- ✅ Airdrop capabilities
- ✅ Vesting schedules
- ✅ Emergency controls

## 🧪 Testing Suite

The comprehensive test suite covers:

### Basic ERC-20 Tests
- Token initialization and metadata
- Transfer and approval mechanisms
- Balance and allowance tracking
- Event emission verification

### Advanced Feature Tests
- Minting and burning operations
- Pause/unpause functionality
- Multi-transfer operations
- Batch operations
- Blacklist management
- Vesting schedules
- Gas optimization verification

### Security Tests
- Zero address prevention
- Overflow protection
- Access control validation
- Edge case handling

## 🔧 Usage Examples

### 1. Deploy Simple Contract
```bash
npm run deploy
```

### 2. Deploy Complete ERC-20 Suite
```bash
npm run deploy:advanced
```

### 3. Run Tests
```bash
npm run test
```

### 4. Compile All Contracts
```bash
npm run compile
```

## 🌐 Integration with Web3.js

This example integrates seamlessly with the Web3.js examples:

```javascript
const { ethers } = require("hardhat");
const Web3 = require("web3");

// Connect to Stellaris
const web3 = new Web3("http://localhost:3006");

// Use deployed contract
const contract = new web3.eth.Contract(ABI, contractAddress);
```

## 📊 Deployment Output

The advanced deployment script provides:

```
🚀 Comprehensive ERC-20 Token Deployment to Stellaris
============================================================
📋 Deployment Details:
  Deployer address: 0x...
  Network: stellaris
  Chain ID: 1337
  Deployer balance: 1000.0 STL

📄 STEP 1: Deploying Simple Storage Contract
✅ SimpleStorage deployed to: 0x...

📄 STEP 2: Deploying Basic ERC-20 Token
✅ StellarisToken deployed to: 0x...

📄 STEP 3: Deploying Advanced ERC-20 Token
✅ AdvancedERC20 deployed to: 0x...

🎯 STEP 4: Demonstrating Token Operations
📤 Transferring tokens...
✅ Testing approvals...
...
```

## 🔐 Security Features

### Access Control
- Owner-only functions
- Minter role management
- Blacklist administration

### Safety Mechanisms
- Pausable transfers
- Supply cap enforcement
- Zero address protection
- Overflow prevention

### Audit Trail
- Comprehensive event logging
- Transaction tracking
- State change monitoring

## 📈 Gas Optimization

The contracts are optimized for gas efficiency:

- Batch operations reduce individual transaction costs
- Efficient storage patterns
- Minimal external calls
- Optimized loop structures

## 🛠️ Development Features

### Hot Reloading
```bash
# Watch for changes and auto-compile
npx hardhat watch compilation
```

### Advanced Testing
```bash
# Run specific test file
npx hardhat test test/ERC20.test.js

# Run with gas reporting
npx hardhat test --gas-report

# Run with coverage
npx hardhat coverage
```

### Contract Size Analysis
```bash
npx hardhat size-contracts
```

## 🔗 Integration Examples

### With Web3.js
```javascript
// examples/web3js-example/
const Web3 = require('web3');
const web3 = new Web3('http://localhost:3006');

// Use your deployed contract
const contract = new web3.eth.Contract(contractABI, contractAddress);
```

### With Frontend Frameworks
```javascript
// React/Vue/Angular integration
import { ethers } from 'ethers';

const provider = new ethers.providers.JsonRpcProvider('http://localhost:3006');
const contract = new ethers.Contract(contractAddress, contractABI, provider);
```

## 📚 Learning Resources

### Documentation
- [Hardhat Documentation](https://hardhat.org/getting-started/)
- [OpenZeppelin Contracts](https://docs.openzeppelin.com/contracts/)
- [Solidity Documentation](https://docs.soliditylang.org/)

### Related Examples
- `../web3js-example/` - Web3.js integration
- `../../docs/BPF_VM_GUIDE.md` - BPF VM documentation
- `../bpf_vm_example.py` - Python BPF VM examples

## 🚀 Production Deployment

### Mainnet Deployment
1. Configure mainnet network in `hardhat.config.js`
2. Set production private keys
3. Verify contracts on block explorer
4. Enable monitoring and alerts

### Security Checklist
- [ ] Audit smart contracts
- [ ] Test on testnet extensively
- [ ] Verify contract source code
- [ ] Set up monitoring
- [ ] Configure access controls
- [ ] Test emergency procedures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- [GitHub Issues](https://github.com/StellarisChain/stellaris/issues)
- [Discord Community](https://discord.gg/stellaris)
- [Documentation](https://docs.stellaris.org)

---

**Happy coding with Stellaris! 🌟**