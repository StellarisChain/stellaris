# Web3.js Examples for Stellaris

This directory contains comprehensive examples showing how to use Web3.js with the Stellaris blockchain for smart contract development and interaction.

## 🚀 Quick Start

### Prerequisites
- Node.js v14+ installed
- Stellaris node running on `http://localhost:3006`

### Installation
```bash
npm install
```

### Running Examples

1. **Basic Web3.js Example**
   ```bash
   npm run basic
   ```
   Shows basic Web3.js operations like connecting to the network, checking balance, and sending transactions.

2. **ERC-20 Token Deployment**
   ```bash
   npm run deploy
   ```
   Deploys a complete ERC-20 token contract to Stellaris.

3. **ERC-20 Token Interaction**
   ```bash
   npm run interact
   ```
   Demonstrates token transfers, approvals, and balance checking.

4. **Complete Example Suite**
   ```bash
   npm start
   ```
   Runs all examples in sequence.

## 📁 Files Overview

- `basic-example.js` - Basic Web3.js operations
- `deploy-erc20.js` - ERC-20 token deployment
- `interact-erc20.js` - ERC-20 token interactions
- `contracts/` - Solidity contract source files
- `index.js` - Main example runner
- `.env.example` - Environment configuration template

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```env
STELLARIS_RPC_URL=http://localhost:3006
PRIVATE_KEY=your_private_key_here
```

## 🌟 Features Demonstrated

### Basic Operations
- ✅ Connect to Stellaris network
- ✅ Check account balance
- ✅ Send transactions
- ✅ Query blockchain state

### Smart Contract Operations
- ✅ Deploy contracts using Web3.js
- ✅ Call contract functions
- ✅ Handle events and logs
- ✅ Estimate gas usage

### ERC-20 Token Operations
- ✅ Deploy ERC-20 tokens
- ✅ Transfer tokens
- ✅ Approve spending
- ✅ Check allowances
- ✅ Query token metadata

## 📖 Usage Guide

### 1. Basic Web3.js Connection

```javascript
const Web3 = require('web3');

const web3 = new Web3('http://localhost:3006');

// Check connection
const isConnected = await web3.eth.net.isListening();
console.log('Connected to Stellaris:', isConnected);
```

### 2. Deploy ERC-20 Token

```javascript
// Deploy token contract
const contract = new web3.eth.Contract(TOKEN_ABI);
const deployTx = contract.deploy({
    data: TOKEN_BYTECODE,
    arguments: ['MyToken', 'MTK', 18, web3.utils.toWei('1000000', 'ether')]
});

const tokenContract = await deployTx.send({
    from: account.address,
    gas: '2000000'
});

console.log('Token deployed at:', tokenContract.options.address);
```

### 3. Token Transfers

```javascript
// Transfer tokens
const transferTx = await tokenContract.methods.transfer(
    recipientAddress,
    web3.utils.toWei('100', 'ether')
).send({
    from: account.address,
    gas: '100000'
});

console.log('Transfer successful:', transferTx.transactionHash);
```

## 🛠️ Advanced Examples

### Event Listening
```javascript
// Listen for Transfer events
tokenContract.events.Transfer()
    .on('data', (event) => {
        console.log('Transfer event:', event.returnValues);
    })
    .on('error', console.error);
```

### Batch Operations
```javascript
// Batch multiple operations
const batch = new web3.BatchRequest();

batch.add(tokenContract.methods.balanceOf(address1).call.request());
batch.add(tokenContract.methods.balanceOf(address2).call.request());

const results = await batch.execute();
```

## 🚨 Security Notes

- Never commit private keys to version control
- Use environment variables for sensitive data
- Validate all inputs before sending transactions
- Test on local network before mainnet deployment

## 📚 Additional Resources

- [Web3.js Documentation](https://web3js.readthedocs.io/)
- [Stellaris Documentation](../docs/BPF_VM_GUIDE.md)
- [ERC-20 Standard](https://eips.ethereum.org/EIPS/eip-20)

## 🤝 Contributing

Found an issue or want to add more examples? Please contribute by:
1. Creating an issue
2. Submitting a pull request
3. Improving documentation

## 📄 License

MIT License - see LICENSE file for details