/**
 * ERC-20 Token Interaction Script for Stellaris
 * 
 * This script demonstrates advanced ERC-20 token interactions
 * including transfers, approvals, multi-transfers, and more.
 */

const Web3 = require('web3');
const { TOKEN_ABI } = require('./deploy-erc20');
require('dotenv').config();

class TokenInteractor {
    constructor(contractAddress) {
        this.web3 = new Web3(process.env.STELLARIS_RPC_URL || 'http://localhost:3006');
        this.contractAddress = contractAddress;
        this.contract = new this.web3.eth.Contract(TOKEN_ABI, contractAddress);
        this.account = null;
        
        if (process.env.PRIVATE_KEY) {
            this.account = this.web3.eth.accounts.privateKeyToAccount(process.env.PRIVATE_KEY);
            this.web3.eth.accounts.wallet.add(this.account);
        }
    }

    async getTokenInfo() {
        console.log('📋 Getting token information...');
        
        try {
            const tokenInfo = await this.contract.methods.getTokenInfo().call();
            
            console.log('Token Details:');
            console.log('  Name:', tokenInfo._name);
            console.log('  Symbol:', tokenInfo._symbol);
            console.log('  Decimals:', tokenInfo._decimals);
            console.log('  Total Supply:', this.web3.utils.fromWei(tokenInfo._totalSupply, 'ether'));
            console.log('  Owner:', tokenInfo._owner);
            console.log('  Paused:', tokenInfo._paused);
            
            return tokenInfo;
        } catch (error) {
            console.error('❌ Error getting token info:', error.message);
        }
    }

    async checkBalances(addresses) {
        console.log('💰 Checking balances...');
        
        const balances = {};
        
        for (const address of addresses) {
            try {
                const balance = await this.contract.methods.balanceOf(address).call();
                balances[address] = this.web3.utils.fromWei(balance, 'ether');
                console.log(`  ${address}: ${balances[address]} tokens`);
            } catch (error) {
                console.error(`❌ Error checking balance for ${address}:`, error.message);
            }
        }
        
        return balances;
    }

    async transferTokens(to, amount) {
        if (!this.account) {
            throw new Error('No account configured for transfers');
        }

        console.log(`💸 Transferring ${amount} tokens to ${to}...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.transfer(to, amountWei).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Transfer successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            console.log('Gas Used:', tx.gasUsed);
            
            return tx;
        } catch (error) {
            console.error('❌ Transfer failed:', error.message);
            throw error;
        }
    }

    async approveSpending(spender, amount) {
        if (!this.account) {
            throw new Error('No account configured for approvals');
        }

        console.log(`✅ Approving ${amount} tokens for ${spender}...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.approve(spender, amountWei).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Approval successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Approval failed:', error.message);
            throw error;
        }
    }

    async checkAllowance(owner, spender) {
        console.log(`📋 Checking allowance from ${owner} to ${spender}...`);
        
        try {
            const allowance = await this.contract.methods.allowance(owner, spender).call();
            const allowanceTokens = this.web3.utils.fromWei(allowance, 'ether');
            
            console.log(`  Allowance: ${allowanceTokens} tokens`);
            return allowanceTokens;
        } catch (error) {
            console.error('❌ Error checking allowance:', error.message);
        }
    }

    async transferFrom(from, to, amount) {
        if (!this.account) {
            throw new Error('No account configured for transferFrom');
        }

        console.log(`🔄 Transferring ${amount} tokens from ${from} to ${to}...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.transferFrom(from, to, amountWei).send({
                from: this.account.address,
                gas: '150000'
            });
            
            console.log('✅ TransferFrom successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ TransferFrom failed:', error.message);
            throw error;
        }
    }

    async increaseAllowance(spender, amount) {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log(`📈 Increasing allowance for ${spender} by ${amount} tokens...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.increaseAllowance(spender, amountWei).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Allowance increased successfully!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Increase allowance failed:', error.message);
            throw error;
        }
    }

    async decreaseAllowance(spender, amount) {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log(`📉 Decreasing allowance for ${spender} by ${amount} tokens...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.decreaseAllowance(spender, amountWei).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Allowance decreased successfully!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Decrease allowance failed:', error.message);
            throw error;
        }
    }

    async multiTransfer(recipients, amounts) {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log(`🎯 Multi-transferring to ${recipients.length} recipients...`);
        
        try {
            const amountsWei = amounts.map(amount => this.web3.utils.toWei(amount.toString(), 'ether'));
            
            const tx = await this.contract.methods.multiTransfer(recipients, amountsWei).send({
                from: this.account.address,
                gas: '500000'
            });
            
            console.log('✅ Multi-transfer successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            console.log('Gas Used:', tx.gasUsed);
            
            return tx;
        } catch (error) {
            console.error('❌ Multi-transfer failed:', error.message);
            throw error;
        }
    }

    async mintTokens(to, amount) {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log(`🎯 Minting ${amount} tokens to ${to}...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.mint(to, amountWei).send({
                from: this.account.address,
                gas: '150000'
            });
            
            console.log('✅ Minting successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Minting failed:', error.message);
            throw error;
        }
    }

    async burnTokens(amount) {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log(`🔥 Burning ${amount} tokens...`);
        
        try {
            const amountWei = this.web3.utils.toWei(amount.toString(), 'ether');
            
            const tx = await this.contract.methods.burn(amountWei).send({
                from: this.account.address,
                gas: '150000'
            });
            
            console.log('✅ Burning successful!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Burning failed:', error.message);
            throw error;
        }
    }

    async pauseToken() {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log('⏸️  Pausing token transfers...');
        
        try {
            const tx = await this.contract.methods.pause().send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Token paused successfully!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Pause failed:', error.message);
            throw error;
        }
    }

    async unpauseToken() {
        if (!this.account) {
            throw new Error('No account configured');
        }

        console.log('▶️  Unpausing token transfers...');
        
        try {
            const tx = await this.contract.methods.unpause().send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Token unpaused successfully!');
            console.log('Transaction Hash:', tx.transactionHash);
            
            return tx;
        } catch (error) {
            console.error('❌ Unpause failed:', error.message);
            throw error;
        }
    }

    async batchOperations() {
        console.log('🔄 Executing batch operations...');
        
        try {
            const batch = new this.web3.BatchRequest();
            
            // Add multiple read operations to batch
            const balanceCall = this.contract.methods.balanceOf(this.account.address).call.request();
            const totalSupplyCall = this.contract.methods.totalSupply().call.request();
            const tokenInfoCall = this.contract.methods.getTokenInfo().call.request();
            
            batch.add(balanceCall);
            batch.add(totalSupplyCall);
            batch.add(tokenInfoCall);
            
            const results = await batch.execute();
            
            console.log('✅ Batch operations completed!');
            console.log('Balance:', this.web3.utils.fromWei(results[0], 'ether'));
            console.log('Total Supply:', this.web3.utils.fromWei(results[1], 'ether'));
            console.log('Token Name:', results[2]._name);
            
            return results;
        } catch (error) {
            console.error('❌ Batch operations failed:', error.message);
            throw error;
        }
    }

    async monitorEvents(duration = 30000) {
        console.log(`👂 Monitoring events for ${duration/1000} seconds...`);
        
        const events = [];
        
        // Monitor Transfer events
        const transferSubscription = this.contract.events.Transfer()
            .on('data', (event) => {
                const eventData = {
                    type: 'Transfer',
                    from: event.returnValues.from,
                    to: event.returnValues.to,
                    value: this.web3.utils.fromWei(event.returnValues.value, 'ether'),
                    txHash: event.transactionHash
                };
                events.push(eventData);
                console.log('🔄 Transfer:', eventData);
            })
            .on('error', console.error);
        
        // Monitor Approval events
        const approvalSubscription = this.contract.events.Approval()
            .on('data', (event) => {
                const eventData = {
                    type: 'Approval',
                    owner: event.returnValues.owner,
                    spender: event.returnValues.spender,
                    value: this.web3.utils.fromWei(event.returnValues.value, 'ether'),
                    txHash: event.transactionHash
                };
                events.push(eventData);
                console.log('✅ Approval:', eventData);
            })
            .on('error', console.error);
        
        // Monitor Mint events
        const mintSubscription = this.contract.events.Mint()
            .on('data', (event) => {
                const eventData = {
                    type: 'Mint',
                    to: event.returnValues.to,
                    amount: this.web3.utils.fromWei(event.returnValues.amount, 'ether'),
                    txHash: event.transactionHash
                };
                events.push(eventData);
                console.log('🎯 Mint:', eventData);
            })
            .on('error', console.error);
        
        // Monitor Burn events
        const burnSubscription = this.contract.events.Burn()
            .on('data', (event) => {
                const eventData = {
                    type: 'Burn',
                    from: event.returnValues.from,
                    amount: this.web3.utils.fromWei(event.returnValues.amount, 'ether'),
                    txHash: event.transactionHash
                };
                events.push(eventData);
                console.log('🔥 Burn:', eventData);
            })
            .on('error', console.error);
        
        // Stop monitoring after duration
        setTimeout(() => {
            transferSubscription.unsubscribe();
            approvalSubscription.unsubscribe();
            mintSubscription.unsubscribe();
            burnSubscription.unsubscribe();
            console.log('⏹️  Stopped monitoring events');
            console.log(`📊 Total events captured: ${events.length}`);
        }, duration);
        
        return events;
    }
}

async function demonstrateTokenInteractions() {
    console.log('🚀 Stellaris ERC-20 Token Interactions');
    console.log('=' * 50);
    
    // You need to provide a contract address here
    const contractAddress = process.env.CONTRACT_ADDRESS || '0x1234567890123456789012345678901234567890';
    
    if (!contractAddress || contractAddress === '0x1234567890123456789012345678901234567890') {
        console.log('❌ Please set CONTRACT_ADDRESS in .env or deploy a token first');
        console.log('   Run: npm run deploy');
        return;
    }
    
    const interactor = new TokenInteractor(contractAddress);
    
    try {
        // Get token information
        await interactor.getTokenInfo();
        
        // Check balances
        const addresses = [
            interactor.account?.address || '0x0000000000000000000000000000000000000000',
            '0x1234567890123456789012345678901234567890',
            '0x9876543210987654321098765432109876543210'
        ];
        
        await interactor.checkBalances(addresses);
        
        if (interactor.account) {
            // Demonstrate transfers
            console.log('\n📤 Transfer Operations:');
            await interactor.transferTokens('0x1234567890123456789012345678901234567890', 100);
            
            // Demonstrate approvals
            console.log('\n✅ Approval Operations:');
            await interactor.approveSpending('0x9876543210987654321098765432109876543210', 50);
            await interactor.checkAllowance(interactor.account.address, '0x9876543210987654321098765432109876543210');
            
            // Demonstrate allowance modifications
            console.log('\n📊 Allowance Modifications:');
            await interactor.increaseAllowance('0x9876543210987654321098765432109876543210', 25);
            await interactor.checkAllowance(interactor.account.address, '0x9876543210987654321098765432109876543210');
            
            // Demonstrate multi-transfer
            console.log('\n🎯 Multi-Transfer Operations:');
            const recipients = [
                '0x1111111111111111111111111111111111111111',
                '0x2222222222222222222222222222222222222222',
                '0x3333333333333333333333333333333333333333'
            ];
            const amounts = [10, 20, 30];
            
            await interactor.multiTransfer(recipients, amounts);
            
            // Demonstrate minting (owner only)
            console.log('\n🎯 Minting Operations:');
            await interactor.mintTokens(interactor.account.address, 1000);
            
            // Demonstrate burning
            console.log('\n🔥 Burning Operations:');
            await interactor.burnTokens(100);
            
            // Demonstrate batch operations
            console.log('\n🔄 Batch Operations:');
            await interactor.batchOperations();
            
            // Check final balances
            console.log('\n💰 Final Balances:');
            await interactor.checkBalances([interactor.account.address, ...recipients]);
            
            // Monitor events
            console.log('\n👂 Event Monitoring:');
            interactor.monitorEvents(30000);
            
            // Perform some operations to generate events
            setTimeout(async () => {
                await interactor.transferTokens('0x1234567890123456789012345678901234567890', 10);
                await interactor.mintTokens(interactor.account.address, 50);
            }, 5000);
        }
        
        console.log('\n🎉 Token interactions demonstration completed!');
        
    } catch (error) {
        console.error('❌ Demonstration failed:', error.message);
    }
}

// Run demonstration if this file is executed directly
if (require.main === module) {
    demonstrateTokenInteractions();
}

module.exports = TokenInteractor;