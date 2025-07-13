# Stellaris Chain

A robust blockchain implementation written in Python with advanced features for decentralized applications and cryptocurrency operations.

[![PyPI version](https://badge.fury.io/py/stellaris-chain.svg)](https://pypi.org/project/stellaris-chain/1.0.284/)
[![Python Version](https://img.shields.io/pypi/pyversions/stellaris-chain.svg)](https://pypi.org/project/stellaris-chain/)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

## Links

- **PyPI**: https://pypi.org/project/stellaris-chain/1.0.284/
- **GitHub**: https://github.com/StellarisChain/stellaris/tree/dev

## Overview

Stellaris Chain is a python blockchain implementation that provides:

- **Proof-of-Work Mining**: Secure block mining with adjustable difficulty
- **Transaction Management**: Support for standard and coinbase transactions
- **P2P Networking**: Distributed node communication and synchronization
- **REST API**: Complete HTTP API for blockchain interaction
- **Database Management**: Efficient storage and retrieval of blockchain data
- **Wallet Operations**: Address generation, balance checking, and transaction creation

## Features

### 🔗 Blockchain Core
- **Block Management**: Create, validate, and manage blocks with merkle tree verification
- **Transaction Processing**: Handle inputs, outputs, signatures, and fees
- **Mining System**: Proof-of-work mining with dynamic difficulty adjustment
- **Chain Validation**: Full blockchain integrity verification

### 🌐 Network Layer
- **Node Discovery**: Automatic peer discovery and management
- **Block Propagation**: Efficient block and transaction broadcasting
- **Chain Synchronization**: Automatic sync with network consensus
- **Rate Limiting**: Built-in protection against spam and abuse

### 💾 Data Management
- **Persistent Storage**: JSON-based database with compression
- **UTXO Model**: Unspent transaction output tracking
- **Address Indexing**: Fast address-based transaction lookup
- **Pending Pool**: Transaction mempool management

### 🔐 Security Features
- **Digital Signatures**: ECDSA signature verification
- **Double-Spend Prevention**: Comprehensive UTXO validation
- **Address Formats**: Multiple address format support
- **Input Validation**: Strict transaction and block validation

## Installation

### From PyPI

```bash
pip install stellaris-chain
```

### From Source

```bash
git clone https://github.com/StellarisChain/stellaris.git
cd stellaris
pip install -r requirements.txt
pip install -e .
```

## Quick Start

### Running a Node

```bash
# Start a blockchain node
python run_node.py
```

The node will start on port 3006 by default. You can configure the port using the `NODE_PORT` environment variable.

### Mining Blocks

```bash
# Start mining (replace with your address and number of workers)
python miner.py <your_address> <num_workers> [node_url]

# Example:
python miner.py dbda85e237b90aa669da00f2859e0010b0a62e0fb6e55ba6ca3ce8a961a60c64410bcfb6a038310a3bb6f1a4aaa2de1192cc10e380a774bb6f9c6ca8547f11ab 4 http://localhost:3006
```

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up --build
```

## API Reference

The Stellaris Chain node provides a comprehensive REST API:

### Blockchain Information

```bash
# Get basic node information
GET /

# Get mining information
GET /get_mining_info

# Get specific block
GET /get_block?block=<block_hash_or_id>

# Get blocks range
GET /get_blocks?offset=<offset>&limit=<limit>
```

### Transaction Operations

```bash
# Submit transaction
POST /push_tx
{
    "tx_hex": "transaction_hex_string"
}

# Get transaction details
GET /get_transaction?tx_hash=<transaction_hash>

# Get pending transactions
GET /get_pending_transactions
```

### Address Operations

```bash
# Get address information
GET /get_address_info?address=<address>&transactions_count_limit=5&show_pending=false

# Parameters:
# - address: The wallet address to query
# - transactions_count_limit: Number of recent transactions (max 50)
# - page: Page number for pagination
# - show_pending: Include pending transactions
# - verify: Verify transaction signatures
```

### Block Operations

```bash
# Submit new block
POST /push_block
{
    "block_content": "block_hex_content",
    "txs": ["tx_hash1", "tx_hash2"],
    "block_no": 12345
}
```

### Network Operations

```bash
# Add peer node
GET /add_node?url=<node_url>

# Get known nodes
GET /get_nodes

# Sync blockchain
GET /sync_blockchain?node_url=<optional_node_url>
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Node configuration
NODE_PORT=3006

# Database configuration (optional)
STELLARIS_DATABASE_USER=stellaris
STELLARIS_DATABASE_PASSWORD=stellaris
STELLARIS_DATABASE_NAME=stellaris
STELLARIS_DATABASE_HOST=localhost
```

### Mining Configuration

The mining system supports:
- **Multi-threading**: Use multiple workers for increased hash rate
- **Difficulty Adjustment**: Automatic difficulty adjustment every 500 blocks
- **Block Time**: Target block time of 180 seconds
- **Reward System**: Decreasing block rewards over time

## Blockchain Specifications

### Technical Details

- **Algorithm**: SHA-256 Proof-of-Work
- **Block Time**: ~3 minutes (180 seconds)
- **Block Size**: Maximum 4MB (2MB raw bytes)
- **Address Format**: ECDSA P-256 curve
- **Transaction Format**: Custom binary format with ECDSA signatures
- **Difficulty Adjustment**: Every 500 blocks
- **Max Supply**: 1,062,005 coins

### Transaction Structure

```python
# Transaction components
{
    "inputs": [
        {
            "tx_hash": "previous_transaction_hash",
            "index": 0,
            "signature": "ecdsa_signature"
        }
    ],
    "outputs": [
        {
            "address": "recipient_address", 
            "amount": 1.5
        }
    ],
    "message": "optional_message",
    "fees": 0.001
}
```

## Development

### Project Structure

```
stellaris/
├── constants.py          # Blockchain constants
├── database.py          # Data storage management
├── manager.py           # Block and transaction management
├── node/               # P2P networking and API
│   ├── main.py         # FastAPI web server
│   ├── nodes_manager.py # Peer management
│   └── utils.py        # Node utilities
├── transactions/       # Transaction handling
│   ├── transaction.py  # Main transaction class
│   ├── transaction_input.py
│   ├── transaction_output.py
│   └── coinbase_transaction.py
└── utils/             # Utility functions
    ├── block_utils.py # Block validation utilities
    └── general.py     # General helper functions
```

### Running Tests

```bash
# Run the test suite (if available)
python -m pytest tests/

# Type checking
mypy stellaris/
```

### Building from Source

```bash
# Install development dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Build distribution packages
python -m build
```

## Mining Guide

### Hardware Requirements

- **CPU**: Multi-core processor recommended
- **RAM**: Minimum 4GB, 8GB+ recommended  
- **Storage**: At least 10GB free space for blockchain data
- **Network**: Stable internet connection

### Mining Performance

Hash rate depends on:
- CPU performance and core count
- Number of mining workers
- Network latency to nodes
- Block difficulty

### Mining Rewards

Block rewards decrease over time:
- Early blocks: Higher rewards
- Block reward halving at specific intervals
- Transaction fees supplement mining rewards

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
git clone https://github.com/StellarisChain/stellaris.git
cd stellaris
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## License

This project is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License - see the [LICENSE](LICENSE) file for details.

**Key License Points:**
- ✅ **Attribution**: You must give appropriate credit
- ❌ **NonCommercial**: No commercial use allowed
- 🔄 **ShareAlike**: Derivatives must use the same license
- 📖 Full license: https://creativecommons.org/licenses/by-nc-sa/4.0/

## Support

- **Issues**: Report bugs on [GitHub Issues](https://github.com/StellarisChain/stellaris/issues)
- **Documentation**: More detailed docs coming soon
- **Community**: Join our discussions and development

## Changelog

### Version 1.0.284
- Current stable release
- Full blockchain functionality
- REST API implementation
- Mining system
- P2P networking

---

*Stellaris Chain - Building the future of decentralized applications*