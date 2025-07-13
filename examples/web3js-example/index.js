/**
 * Complete Web3.js Example Suite for Stellaris
 * 
 * This is the main entry point that runs all examples in sequence,
 * demonstrating the full capabilities of Web3.js with Stellaris.
 */

const Web3 = require('web3');
const StellarisWeb3Basic = require('./basic-example');
const { TokenDeployer } = require('./deploy-erc20');
const TokenInteractor = require('./interact-erc20');
require('dotenv').config();

class StellarisWeb3Suite {
    constructor() {
        this.web3 = new Web3(process.env.STELLARIS_RPC_URL || 'http://localhost:3006');
        this.account = null;
        this.deployedContract = null;
        
        if (process.env.PRIVATE_KEY) {
            this.account = this.web3.eth.accounts.privateKeyToAccount(process.env.PRIVATE_KEY);
            this.web3.eth.accounts.wallet.add(this.account);
        }
    }

    async runCompleteSuite() {
        console.log('🚀 STELLARIS WEB3.JS COMPLETE EXAMPLE SUITE');
        console.log('=' * 60);
        console.log('This suite demonstrates all Web3.js capabilities with Stellaris');
        console.log('=' * 60);
        
        try {
            // Step 1: Basic Web3.js operations
            console.log('\n📋 STEP 1: Basic Web3.js Operations');
            console.log('-' * 40);
            await this.runBasicOperations();
            
            // Step 2: Deploy ERC-20 Token
            console.log('\n📋 STEP 2: ERC-20 Token Deployment');
            console.log('-' * 40);
            await this.deployERC20Token();
            
            // Step 3: Token Interactions
            console.log('\n📋 STEP 3: Advanced Token Interactions');
            console.log('-' * 40);
            await this.runTokenInteractions();
            
            // Step 4: Advanced Web3.js Features
            console.log('\n📋 STEP 4: Advanced Web3.js Features');
            console.log('-' * 40);
            await this.demonstrateAdvancedFeatures();
            
            // Step 5: Development Tools Integration
            console.log('\n📋 STEP 5: Development Tools Integration');
            console.log('-' * 40);
            await this.demonstrateDevTools();
            
            // Final Summary
            console.log('\n🎉 SUITE COMPLETION SUMMARY');
            console.log('=' * 60);
            this.printSummary();
            
        } catch (error) {
            console.error('❌ Suite execution failed:', error.message);
            process.exit(1);
        }
    }

    async runBasicOperations() {
        console.log('🔧 Running basic Web3.js operations...');
        
        const basicExample = new StellarisWeb3Basic();
        
        // Check connection
        const connected = await basicExample.checkConnection();
        if (!connected) {
            throw new Error('Cannot connect to Stellaris node');
        }
        
        // Get account and network info
        await basicExample.getAccountInfo();
        await basicExample.getBlockInfo();
        await basicExample.demoUtilityFunctions();
        
        console.log('✅ Basic operations completed successfully');
    }

    async deployERC20Token() {
        console.log('🚀 Deploying ERC-20 token...');
        
        if (!this.account) {
            console.log('⚠️  No account configured, skipping token deployment');
            return;
        }
        
        const deployer = new TokenDeployer();
        
        // Deploy token with custom configuration
        const tokenConfig = {
            name: 'Stellaris Demo Token',
            symbol: 'SDT',
            decimals: 18,
            initialSupply: 1000000 // 1 million tokens
        };
        
        this.deployedContract = await deployer.deployToken(tokenConfig);
        console.log('📄 Token deployed at:', this.deployedContract.options.address);
        
        // Verify deployment
        await deployer.verifyDeployment(this.deployedContract.options.address);
        
        console.log('✅ Token deployment completed successfully');
    }

    async runTokenInteractions() {
        if (!this.deployedContract) {
            console.log('⚠️  No token deployed, skipping token interactions');
            return;
        }
        
        console.log('🎯 Running advanced token interactions...');
        
        const interactor = new TokenInteractor(this.deployedContract.options.address);
        
        // Get token info
        await interactor.getTokenInfo();
        
        // Check balances
        const testAddresses = [
            this.account.address,
            '0x1234567890123456789012345678901234567890',
            '0x9876543210987654321098765432109876543210'
        ];
        
        await interactor.checkBalances(testAddresses);
        
        // Demonstrate various operations
        await interactor.transferTokens('0x1234567890123456789012345678901234567890', 100);
        await interactor.approveSpending('0x9876543210987654321098765432109876543210', 50);
        await interactor.checkAllowance(this.account.address, '0x9876543210987654321098765432109876543210');
        
        // Multi-transfer demonstration
        const recipients = [
            '0x1111111111111111111111111111111111111111',
            '0x2222222222222222222222222222222222222222',
            '0x3333333333333333333333333333333333333333'
        ];
        const amounts = [10, 20, 30];
        
        await interactor.multiTransfer(recipients, amounts);
        
        // Minting and burning
        await interactor.mintTokens(this.account.address, 1000);
        await interactor.burnTokens(100);
        
        console.log('✅ Token interactions completed successfully');
    }

    async demonstrateAdvancedFeatures() {
        console.log('🔬 Demonstrating advanced Web3.js features...');
        
        // Event filtering and historical data
        await this.demonstrateEventFiltering();
        
        // Gas optimization
        await this.demonstrateGasOptimization();
        
        // Transaction signing variations
        await this.demonstrateTransactionSigning();
        
        // Web3.js utilities
        await this.demonstrateUtilities();
        
        console.log('✅ Advanced features demonstration completed');
    }

    async demonstrateEventFiltering() {
        if (!this.deployedContract) return;
        
        console.log('📡 Demonstrating event filtering...');
        
        try {
            // Get past events
            const pastEvents = await this.deployedContract.getPastEvents('Transfer', {
                fromBlock: 0,
                toBlock: 'latest'
            });
            
            console.log(`📊 Found ${pastEvents.length} past Transfer events`);
            
            if (pastEvents.length > 0) {
                console.log('📋 Latest Transfer Event:');
                const latestEvent = pastEvents[pastEvents.length - 1];
                console.log('  From:', latestEvent.returnValues.from);
                console.log('  To:', latestEvent.returnValues.to);
                console.log('  Value:', this.web3.utils.fromWei(latestEvent.returnValues.value, 'ether'));
                console.log('  Block:', latestEvent.blockNumber);
            }
            
            // Set up real-time event filtering
            console.log('👂 Setting up real-time event listener...');
            
            const eventFilter = this.deployedContract.events.Transfer({
                filter: { from: this.account.address }
            });
            
            eventFilter.on('data', (event) => {
                console.log('🔄 New Transfer from your account:', {
                    to: event.returnValues.to,
                    value: this.web3.utils.fromWei(event.returnValues.value, 'ether'),
                    txHash: event.transactionHash
                });
            });
            
            // Generate an event
            await this.deployedContract.methods.transfer(
                '0x1234567890123456789012345678901234567890',
                this.web3.utils.toWei('10', 'ether')
            ).send({
                from: this.account.address,
                gas: '100000'
            });
            
            // Clean up
            setTimeout(() => {
                eventFilter.unsubscribe();
                console.log('🔇 Event listener stopped');
            }, 5000);
            
        } catch (error) {
            console.error('❌ Event filtering failed:', error.message);
        }
    }

    async demonstrateGasOptimization() {
        console.log('⛽ Demonstrating gas optimization techniques...');
        
        try {
            // Gas estimation comparison
            const recipient = '0x1234567890123456789012345678901234567890';
            const amount = this.web3.utils.toWei('1', 'ether');
            
            // Simple transfer
            const simpleTransferGas = await this.web3.eth.estimateGas({
                from: this.account.address,
                to: recipient,
                value: amount
            });
            
            console.log('💸 Simple transfer gas:', simpleTransferGas);
            
            if (this.deployedContract) {
                // Token transfer
                const tokenTransferGas = await this.deployedContract.methods.transfer(recipient, amount).estimateGas({
                    from: this.account.address
                });
                
                console.log('🪙 Token transfer gas:', tokenTransferGas);
                
                // Batch operation gas
                const batchGas = await this.deployedContract.methods.multiTransfer(
                    [recipient, recipient, recipient],
                    [amount, amount, amount]
                ).estimateGas({
                    from: this.account.address
                });
                
                console.log('🎯 Batch transfer gas:', batchGas);
                console.log('💡 Gas per transfer in batch:', Math.floor(batchGas / 3));
            }
            
            // Gas price analysis
            const gasPrice = await this.web3.eth.getGasPrice();
            console.log('⚡ Current gas price:', gasPrice);
            
            // Calculate transaction costs
            const costInWei = BigInt(simpleTransferGas) * BigInt(gasPrice);
            const costInEther = this.web3.utils.fromWei(costInWei.toString(), 'ether');
            console.log('💰 Simple transfer cost:', costInEther, 'STL');
            
        } catch (error) {
            console.error('❌ Gas optimization demo failed:', error.message);
        }
    }

    async demonstrateTransactionSigning() {
        console.log('✍️  Demonstrating transaction signing variations...');
        
        try {
            // Create transaction object
            const txObject = {
                from: this.account.address,
                to: '0x1234567890123456789012345678901234567890',
                value: this.web3.utils.toWei('0.01', 'ether'),
                gas: '21000',
                gasPrice: await this.web3.eth.getGasPrice(),
                nonce: await this.web3.eth.getTransactionCount(this.account.address)
            };
            
            console.log('📝 Transaction object created');
            
            // Sign transaction
            const signedTx = await this.web3.eth.accounts.signTransaction(txObject, process.env.PRIVATE_KEY);
            console.log('✅ Transaction signed');
            console.log('📋 Raw transaction:', signedTx.rawTransaction.substring(0, 50) + '...');
            
            // You could send the transaction here if needed
            // const receipt = await this.web3.eth.sendSignedTransaction(signedTx.rawTransaction);
            
            // Demonstrate message signing
            const message = 'Hello Stellaris!';
            const messageHash = this.web3.utils.keccak256(message);
            const signature = await this.web3.eth.accounts.sign(messageHash, process.env.PRIVATE_KEY);
            
            console.log('📝 Message signed');
            console.log('📋 Message:', message);
            console.log('📋 Signature:', signature.signature);
            
            // Verify signature
            const recoveredAddress = this.web3.eth.accounts.recover(messageHash, signature.signature);
            console.log('🔍 Signature verified:', recoveredAddress === this.account.address);
            
        } catch (error) {
            console.error('❌ Transaction signing demo failed:', error.message);
        }
    }

    async demonstrateUtilities() {
        console.log('🛠️  Demonstrating Web3.js utilities...');
        
        // Unit conversions
        console.log('📊 Unit Conversions:');
        const amounts = ['1', '0.5', '1000', '0.001'];
        amounts.forEach(amount => {
            const wei = this.web3.utils.toWei(amount, 'ether');
            const backToEther = this.web3.utils.fromWei(wei, 'ether');
            console.log(`  ${amount} STL = ${wei} wei = ${backToEther} STL`);
        });
        
        // Hash functions
        console.log('\n🔐 Hash Functions:');
        const data = 'Stellaris blockchain data';
        console.log('  Data:', data);
        console.log('  Keccak256:', this.web3.utils.keccak256(data));
        console.log('  SHA3:', this.web3.utils.sha3(data));
        
        // Random and crypto utilities
        console.log('\n🎲 Random and Crypto:');
        const randomHex = this.web3.utils.randomHex(32);
        console.log('  Random hex:', randomHex);
        
        // Address utilities
        console.log('\n📍 Address Utilities:');
        const addresses = [
            '0x1234567890123456789012345678901234567890',
            '0x0000000000000000000000000000000000000000',
            'not_an_address'
        ];
        
        addresses.forEach(addr => {
            console.log(`  ${addr}:`);
            console.log(`    Valid: ${this.web3.utils.isAddress(addr)}`);
            if (this.web3.utils.isAddress(addr)) {
                console.log(`    Checksum: ${this.web3.utils.toChecksumAddress(addr)}`);
            }
        });
        
        // Number and hex conversions
        console.log('\n🔢 Number and Hex Conversions:');
        const numbers = [42, 255, 1000, 0];
        numbers.forEach(num => {
            const hex = this.web3.utils.toHex(num);
            const backToNumber = this.web3.utils.hexToNumber(hex);
            console.log(`  ${num} = ${hex} = ${backToNumber}`);
        });
    }

    async demonstrateDevTools() {
        console.log('🔧 Demonstrating development tools integration...');
        
        // Hardhat integration example
        console.log('\n🏗️  Hardhat Integration:');
        console.log('  Hardhat can connect to Stellaris using:');
        console.log('  Network URL: http://localhost:3006');
        console.log('  Chain ID: 1337');
        console.log('  See examples/hardhat-example/ for complete setup');
        
        // Truffle integration
        console.log('\n🍯 Truffle Integration:');
        console.log('  Configure truffle-config.js with:');
        console.log('  host: "127.0.0.1"');
        console.log('  port: 3006');
        console.log('  network_id: 1337');
        
        // Web3.js provider configuration
        console.log('\n🌐 Web3.js Provider Configuration:');
        console.log('  HTTP Provider:', this.web3.currentProvider.host);
        console.log('  Connected:', await this.web3.eth.net.isListening());
        
        // Testing framework integration
        console.log('\n🧪 Testing Framework Integration:');
        console.log('  Mocha/Chai: Use Web3.js with assert statements');
        console.log('  Jest: Mock Web3 providers for unit tests');
        console.log('  Ganache: Replace with Stellaris node for testing');
        
        // Debug utilities
        console.log('\n🐛 Debug Utilities:');
        if (this.deployedContract) {
            try {
                const receipt = await this.web3.eth.getTransactionReceipt(this.deployedContract.transactionHash);
                console.log('  Transaction receipt available');
                console.log('  Gas used:', receipt.gasUsed);
                console.log('  Status:', receipt.status ? 'Success' : 'Failed');
                console.log('  Logs:', receipt.logs.length);
            } catch (error) {
                console.log('  Debug info not available');
            }
        }
    }

    printSummary() {
        console.log('📊 What was demonstrated:');
        console.log('  ✅ Basic Web3.js connection and operations');
        console.log('  ✅ ERC-20 token deployment and verification');
        console.log('  ✅ Advanced token interactions (transfers, approvals, etc.)');
        console.log('  ✅ Event filtering and real-time monitoring');
        console.log('  ✅ Gas optimization techniques');
        console.log('  ✅ Transaction signing variations');
        console.log('  ✅ Web3.js utility functions');
        console.log('  ✅ Development tools integration');
        
        console.log('\n🎯 Key takeaways:');
        console.log('  • Stellaris is fully compatible with Web3.js');
        console.log('  • ERC-20 tokens work seamlessly');
        console.log('  • All Web3.js features are supported');
        console.log('  • Integration with existing tools is straightforward');
        
        console.log('\n📚 Next steps:');
        console.log('  1. Explore the individual example files');
        console.log('  2. Check out the Hardhat integration');
        console.log('  3. Build your own DApp with Stellaris');
        console.log('  4. Join the Stellaris community');
        
        if (this.deployedContract) {
            console.log(`\n💾 Save this contract address: ${this.deployedContract.options.address}`);
            console.log('   Use it to continue interacting with your token');
        }
    }

    async pause(seconds) {
        console.log(`⏸️  Pausing for ${seconds} seconds...`);
        return new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }
}

async function runCompleteSuite() {
    const suite = new StellarisWeb3Suite();
    await suite.runCompleteSuite();
}

// Run the complete suite if this file is executed directly
if (require.main === module) {
    runCompleteSuite().catch(console.error);
}

module.exports = StellarisWeb3Suite;