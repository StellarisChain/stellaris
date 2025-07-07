# Hardhat Example for Stellaris

This example shows how to use Hardhat with Stellaris blockchain for Solidity development.

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure your private keys**:
   Edit `hardhat.config.js` and add your private keys to the `accounts` array.

3. **Start Stellaris node**:
   ```bash
   # From the main stellaris directory
   python run_node.py
   ```

## Usage

### Compile contracts
```bash
npm run compile
```

### Run tests
```bash
npm run test
```

### Deploy contracts
```bash
npm run deploy
```

## Files

- `contracts/SimpleStorage.sol`: Example Solidity contract
- `scripts/deploy.js`: Deployment script
- `test/SimpleStorage.test.js`: Test suite
- `hardhat.config.js`: Hardhat configuration for Stellaris

## Features Demonstrated

- ✅ Contract deployment to Stellaris
- ✅ Function calls and transactions
- ✅ Event emission and listening
- ✅ Test suite with Chai assertions
- ✅ Web3 compatibility

## Next Steps

1. Write your own Solidity contracts
2. Add more comprehensive tests
3. Deploy to Stellaris testnet
4. Build a frontend with Web3.js or ethers.js