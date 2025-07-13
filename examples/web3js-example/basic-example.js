/**
 * Basic Web3.js Example for Stellaris
 * 
 * This example demonstrates basic Web3.js operations with the Stellaris blockchain:
 * - Connecting to the network
 * - Checking account balance
 * - Sending transactions
 * - Querying network information
 */

const Web3 = require('web3');
require('dotenv').config();

class StellarisWeb3Basic {
    constructor() {
        // Initialize Web3 connection to Stellaris
        this.web3 = new Web3(process.env.STELLARIS_RPC_URL || 'http://localhost:3006');
        this.account = null;
        
        // Initialize account from private key
        if (process.env.PRIVATE_KEY) {
            this.account = this.web3.eth.accounts.privateKeyToAccount(process.env.PRIVATE_KEY);
            this.web3.eth.accounts.wallet.add(this.account);
        }
    }

    async checkConnection() {
        console.log('🔗 Checking connection to Stellaris...');
        try {
            const isListening = await this.web3.eth.net.isListening();
            console.log('✅ Connected to Stellaris:', isListening);
            
            // Get network information
            const networkId = await this.web3.eth.net.getId();
            console.log('🌐 Network ID:', networkId);
            
            const chainId = await this.web3.eth.getChainId();
            console.log('⛓️  Chain ID:', chainId);
            
            return true;
        } catch (error) {
            console.error('❌ Connection failed:', error.message);
            return false;
        }
    }

    async getAccountInfo() {
        if (!this.account) {
            console.log('⚠️  No account configured. Please set PRIVATE_KEY in .env');
            return;
        }

        console.log('\n👤 Account Information:');
        console.log('Address:', this.account.address);
        
        try {
            const balance = await this.web3.eth.getBalance(this.account.address);
            const balanceInEther = this.web3.utils.fromWei(balance, 'ether');
            console.log('Balance:', balanceInEther, 'STL');
            
            const nonce = await this.web3.eth.getTransactionCount(this.account.address);
            console.log('Nonce:', nonce);
        } catch (error) {
            console.error('❌ Error getting account info:', error.message);
        }
    }

    async getBlockInfo() {
        console.log('\n📦 Latest Block Information:');
        try {
            const blockNumber = await this.web3.eth.getBlockNumber();
            console.log('Block Number:', blockNumber);
            
            const block = await this.web3.eth.getBlock(blockNumber);
            console.log('Block Hash:', block.hash);
            console.log('Timestamp:', new Date(Number(block.timestamp) * 1000).toISOString());
            console.log('Transactions:', block.transactions.length);
        } catch (error) {
            console.error('❌ Error getting block info:', error.message);
        }
    }

    async sendTransaction(to, amount) {
        if (!this.account) {
            console.log('⚠️  No account configured for sending transactions');
            return;
        }

        console.log(`\n💸 Sending ${amount} STL to ${to}...`);
        
        try {
            const transaction = {
                from: this.account.address,
                to: to,
                value: this.web3.utils.toWei(amount, 'ether'),
                gas: '21000',
                gasPrice: process.env.GAS_PRICE || '20000000000'
            };

            const signedTx = await this.web3.eth.accounts.signTransaction(transaction, process.env.PRIVATE_KEY);
            const receipt = await this.web3.eth.sendSignedTransaction(signedTx.rawTransaction);
            
            console.log('✅ Transaction successful!');
            console.log('Transaction Hash:', receipt.transactionHash);
            console.log('Block Number:', receipt.blockNumber);
            console.log('Gas Used:', receipt.gasUsed);
            
            return receipt;
        } catch (error) {
            console.error('❌ Transaction failed:', error.message);
        }
    }

    async estimateGas(to, amount) {
        if (!this.account) {
            console.log('⚠️  No account configured for gas estimation');
            return;
        }

        console.log(`\n⛽ Estimating gas for ${amount} STL transfer...`);
        
        try {
            const transaction = {
                from: this.account.address,
                to: to,
                value: this.web3.utils.toWei(amount, 'ether')
            };

            const gasEstimate = await this.web3.eth.estimateGas(transaction);
            console.log('Gas Estimate:', gasEstimate);
            
            const gasPrice = await this.web3.eth.getGasPrice();
            console.log('Gas Price:', gasPrice);
            
            const cost = this.web3.utils.fromWei((BigInt(gasEstimate) * BigInt(gasPrice)).toString(), 'ether');
            console.log('Transaction Cost:', cost, 'STL');
            
            return { gasEstimate, gasPrice, cost };
        } catch (error) {
            console.error('❌ Gas estimation failed:', error.message);
        }
    }

    async watchTransactions() {
        console.log('\n👀 Watching for new transactions...');
        
        try {
            const subscription = await this.web3.eth.subscribe('newBlockHeaders');
            
            subscription.on('data', async (blockHeader) => {
                console.log('📦 New block:', blockHeader.number);
                
                const block = await this.web3.eth.getBlock(blockHeader.number, true);
                if (block.transactions.length > 0) {
                    console.log(`   📝 Contains ${block.transactions.length} transactions`);
                    
                    // Show first transaction details
                    const firstTx = block.transactions[0];
                    console.log(`   💸 First TX: ${firstTx.from} → ${firstTx.to} (${this.web3.utils.fromWei(firstTx.value, 'ether')} STL)`);
                }
            });
            
            subscription.on('error', console.error);
            
            // Watch for 30 seconds
            setTimeout(() => {
                subscription.unsubscribe();
                console.log('⏹️  Stopped watching transactions');
            }, 30000);
            
        } catch (error) {
            console.error('❌ Error watching transactions:', error.message);
        }
    }

    async demoUtilityFunctions() {
        console.log('\n🔧 Web3.js Utility Functions Demo:');
        
        // Unit conversions
        console.log('Unit Conversions:');
        console.log('  1 STL =', this.web3.utils.toWei('1', 'ether'), 'wei');
        console.log('  1000000000000000000 wei =', this.web3.utils.fromWei('1000000000000000000', 'ether'), 'STL');
        
        // Hash functions
        console.log('\nHash Functions:');
        const message = 'Hello Stellaris!';
        console.log('  Message:', message);
        console.log('  Keccak256:', this.web3.utils.keccak256(message));
        console.log('  SHA3:', this.web3.utils.sha3(message));
        
        // Address validation
        console.log('\nAddress Validation:');
        const address = '0x1234567890123456789012345678901234567890';
        console.log('  Address:', address);
        console.log('  Is valid:', this.web3.utils.isAddress(address));
        console.log('  Checksum:', this.web3.utils.toChecksumAddress(address));
        
        // Hex conversions
        console.log('\nHex Conversions:');
        const number = 42;
        console.log('  Number:', number);
        console.log('  To Hex:', this.web3.utils.toHex(number));
        console.log('  From Hex:', this.web3.utils.hexToNumber(this.web3.utils.toHex(number)));
    }
}

async function runBasicExample() {
    console.log('🚀 Stellaris Web3.js Basic Example');
    console.log('=' * 50);
    
    const stellaris = new StellarisWeb3Basic();
    
    // Check connection
    const connected = await stellaris.checkConnection();
    if (!connected) {
        console.log('❌ Cannot connect to Stellaris node. Please ensure it\'s running on http://localhost:3006');
        return;
    }
    
    // Get account information
    await stellaris.getAccountInfo();
    
    // Get block information
    await stellaris.getBlockInfo();
    
    // Demo utility functions
    await stellaris.demoUtilityFunctions();
    
    // Gas estimation example
    await stellaris.estimateGas('0x1234567890123456789012345678901234567890', '0.01');
    
    // Optional: Send a transaction (uncomment to test)
    // await stellaris.sendTransaction('0x1234567890123456789012345678901234567890', '0.01');
    
    // Optional: Watch transactions (uncomment to test)
    // await stellaris.watchTransactions();
    
    console.log('\n✅ Basic Web3.js example completed!');
    console.log('\nNext steps:');
    console.log('1. Try deploying a smart contract with: npm run deploy');
    console.log('2. Interact with tokens using: npm run interact');
    console.log('3. Check out the complete example suite with: npm start');
}

// Run the example if this file is executed directly
if (require.main === module) {
    runBasicExample().catch(console.error);
}

module.exports = StellarisWeb3Basic;