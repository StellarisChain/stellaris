#!/usr/bin/env python3
"""
Smart Contract Deployment Script for Stellaris Blockchain

This script provides an interactive menu for selecting and deploying smart contracts
to the Stellaris blockchain. It integrates with the wallet system to handle credentials
and transaction signing.

SETUP: you need to have stellaris-wallet cloned in the root directory, then renamed to stellaris_wallet
and install its dependencies with pip install -r stellaris_wallet/requirements.txt
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "stellaris_wallet"))
sys.path.insert(0, str(project_root / "stellaris_wallet" / "stellaris" / "wallet" / "utils"))

# Core Stellaris imports
from stellaris.svm.transaction_builder import SmartContractTransactionBuilder
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
from stellaris.transactions.transaction import Transaction
from stellaris.transactions.transaction_input import TransactionInput
from stellaris.transactions.transaction_output import TransactionOutput
from stellaris.utils.general import point_to_string, string_to_point
from stellaris.constants import SMALLEST

# Wallet-related imports (simplified approach)
try:
    # First check if wallet utilities directory exists
    wallet_utils_path = project_root / "stellaris_wallet" / "stellaris" / "wallet" / "utils"
    if wallet_utils_path.exists():
        # Add the utils directory to path so data_manipulation_util can be found
        sys.path.insert(0, str(wallet_utils_path))
        from wallet_generation_util import generate_from_private_key, string_to_point as wallet_string_to_point
        WALLET_AVAILABLE = True
    else:
        raise ImportError("Wallet utilities directory not found")
except ImportError as e:
    WALLET_AVAILABLE = False
    print("⚠️  Wallet utilities not available. You'll need to provide credentials manually.")
    print(f"Error: {e}")
    print("Try: git clone https://github.com/StellarisChain/stellaris-wallet.git stellaris_wallet")
    print("Then: pip install -r stellaris_wallet/requirements.txt")


class ContractDeployer:
    """Main class for contract deployment operations"""
    
    def __init__(self, node_url: str = None):
        # Use environment variable or default to localhost:3006
        if node_url is None:
            node_host = os.getenv("NODE_HOST", "localhost")
            node_port = os.getenv("NODE_PORT", "3006")
            node_url = f"http://{node_host}:{node_port}"
        
        self.node_url = node_url.rstrip('/')
        self.builder = SmartContractTransactionBuilder()
        self.session = None
        
        # Available contracts
        self.contracts = {
            "1": {
                "name": "Simple SRC20 Token",
                "description": "Basic ERC20-compatible token implementation",
                "file": "examples/src20.py",
                "class_name": "SimpleSRC20"
            },
            "2": {
                "name": "Enhanced SRC20 Token",
                "description": "Full-featured ERC20 token with minting, burning, and access control",
                "file": "examples/src20_enhanced.py",
                "class_name": "SRC20Token"
            },
            "3": {
                "name": "Simple Test Contract",
                "description": "Basic test contract for VM validation",
                "file": "examples/simple_test.py",
                "class_name": "SimpleToken"
            }
        }
    
    async def initialize(self):
        """Initialize HTTP session and test connection to node"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Test connection to node
            async with self.session.get(f"{self.node_url}/docs") as response:
                if response.status == 200:
                    print("✅ Connected to Stellaris node")
                    return True
                else:
                    print(f"❌ Failed to connect to Stellaris node: HTTP {response.status}")
                    await self.session.close()
                    self.session = None
                    return False
        except Exception as e:
            print(f"❌ Failed to connect to Stellaris node: {e}")
            print("\n💡 To start the local Stellaris node:")
            print("   1. Make sure you're in the project directory")
            print("   2. Run: python run_node.py")
            print("   3. Or run: ./run.sh")
            print("\n💡 The node will be available at:")
            print(f"   - Local: http://localhost:{os.getenv('NODE_PORT', '3006')}")
            print("   - Production: https://stellaris-node.connor33341.dev")
            print("\n💡 You can also set NODE_HOST and NODE_PORT environment variables")
            print("   to connect to different endpoints.")
            if self.session:
                await self.session.close()
                self.session = None
            return False
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def display_menu(self):
        """Display the contract selection menu"""
        print("\n" + "="*60)
        print("🚀 STELLARIS SMART CONTRACT DEPLOYER")
        print("="*60)
        print("\nAvailable Smart Contracts:")
        print("-" * 40)
        
        for key, contract in self.contracts.items():
            print(f"{key}. {contract['name']}")
            print(f"   📝 {contract['description']}")
            print(f"   📁 {contract['file']}")
            print()
        
        print("0. Exit")
        print("-" * 40)
    
    def get_wallet_credentials(self) -> Optional[Tuple[str, int]]:
        """Get wallet credentials (address and private key)"""
        print("\n🔐 WALLET CREDENTIALS")
        print("-" * 30)
        
        # Option 1: Load from wallet file (if available)
        if WALLET_AVAILABLE:
            wallet_choice = input("Do you want to load from a wallet file? (y/n): ").lower()
            if wallet_choice == 'y':
                return self._load_from_wallet_file()
        
        # Option 2: Manual entry
        return self._manual_credential_entry()
    
    def _load_from_wallet_file(self) -> Optional[Tuple[str, int]]:
        """Load credentials from a wallet file"""
        try:
            wallet_dir = Path("./stellaris-wallet/wallets")
            if not wallet_dir.exists():
                print("❌ Wallet directory not found")
                return self._manual_credential_entry()
            
            # List available wallet files
            wallet_files = list(wallet_dir.glob("*.json"))
            if not wallet_files:
                print("❌ No wallet files found")
                return self._manual_credential_entry()
            
            print("\nAvailable wallet files:")
            for i, wallet_file in enumerate(wallet_files, 1):
                print(f"{i}. {wallet_file.name}")
            
            try:
                choice = int(input("\nSelect wallet file (number): ")) - 1
                if 0 <= choice < len(wallet_files):
                    return self._decrypt_wallet_file(wallet_files[choice])
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
            
        except Exception as e:
            print(f"❌ Error loading wallet file: {e}")
        
        return self._manual_credential_entry()
    
    def _decrypt_wallet_file(self, wallet_file: Path) -> Optional[Tuple[str, int]]:
        """Decrypt and extract credentials from wallet file"""
        try:
            with open(wallet_file, 'r') as f:
                wallet_data = json.load(f)
            
            # Check if wallet is encrypted
            if 'wallet_data' in wallet_data and 'verifier' in wallet_data['wallet_data']:
                password = input("Enter wallet password: ")
                # Note: This is a simplified approach. In a real implementation,
                # you would need to properly decrypt the wallet using the wallet utilities
                print("⚠️  Encrypted wallet decryption not fully implemented in this demo")
                print("Please use manual entry option")
                return None
            else:
                # Unencrypted wallet (not recommended for production)
                if 'addresses' in wallet_data:
                    addresses = wallet_data['addresses']
                    if addresses:
                        # Use the first address
                        first_addr = list(addresses.keys())[0]
                        if 'private_key' in addresses[first_addr]:
                            private_key = int(addresses[first_addr]['private_key'])
                            return first_addr, private_key
                
                print("❌ Could not extract credentials from wallet file")
                return None
                
        except Exception as e:
            print(f"❌ Error reading wallet file: {e}")
            return None
    
    def _manual_credential_entry(self) -> Optional[Tuple[str, int]]:
        """Manual entry of wallet credentials"""
        print("\n📝 Manual Credential Entry")
        print("You can either:")
        print("1. Enter your private key (we'll derive the address)")
        print("2. Enter both address and private key")
        
        choice = input("\nChoose option (1 or 2): ").strip()
        
        try:
            if choice == "1":
                private_key_hex = input("Enter private key (hex): ").strip()
                if private_key_hex.startswith("0x"):
                    private_key_hex = private_key_hex[2:]
                
                # Validate hex format
                int(private_key_hex, 16)  # This will raise ValueError if not valid hex
                
                # Derive address from private key
                if WALLET_AVAILABLE:
                    result = generate_from_private_key(private_key_hex)
                    address = result['address']
                    private_key = int(private_key_hex, 16)
                    print(f"✅ Derived address: {address}")
                    return address, private_key
                else:
                    print("❌ Cannot derive address without wallet utilities")
                    return None
                    
            elif choice == "2":
                address = input("Enter address: ").strip()
                private_key_hex = input("Enter private key (hex): ").strip()
                
                if private_key_hex.startswith("0x"):
                    private_key_hex = private_key_hex[2:]
                
                private_key = int(private_key_hex, 16)
                return address, private_key
            else:
                print("❌ Invalid choice")
                return None
                
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
            return None
        except Exception as e:
            print(f"❌ Error processing credentials: {e}")
            return None
    
    def load_contract_code(self, contract_info: Dict) -> Optional[str]:
        """Load contract source code from file"""
        try:
            contract_path = Path(contract_info['file'])
            if not contract_path.exists():
                print(f"❌ Contract file not found: {contract_path}")
                return None
            
            with open(contract_path, 'r') as f:
                code = f.read()
            
            print(f"✅ Loaded contract code from {contract_path}")
            return code
            
        except Exception as e:
            print(f"❌ Error loading contract code: {e}")
            return None
    
    def get_deployment_parameters(self, contract_info: Dict) -> Optional[Dict]:
        """Get deployment parameters from user"""
        print(f"\n⚙️  DEPLOYMENT PARAMETERS FOR {contract_info['name']}")
        print("-" * 50)
        
        params = {}
        
        # Common parameters for token contracts
        if "SRC20" in contract_info['class_name'] or "Token" in contract_info['class_name']:
            params['name'] = input("Token name (e.g., 'My Token'): ").strip()
            params['symbol'] = input("Token symbol (e.g., 'MTK'): ").strip()
            
            try:
                supply_str = input("Initial supply (e.g., '1000000'): ").strip()
                params['initial_supply'] = Decimal(supply_str)
            except ValueError:
                print("❌ Invalid supply amount")
                return None
        
        # Ask for gas limit
        try:
            gas_limit = input("Gas limit (press Enter for default 1000000): ").strip()
            params['gas_limit'] = int(gas_limit) if gas_limit else 1000000
        except ValueError:
            params['gas_limit'] = 1000000
        
        return params
    
    async def check_balance(self, address: str) -> Decimal:
        """Check account balance via API"""
        try:
            async with self.session.get(f"{self.node_url}/get_address_info", 
                                      params={"address": address, "transactions_count_limit": 0}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        balance_str = data['result']['balance']
                        return Decimal(balance_str)
                    else:
                        print(f"❌ API error: {data.get('error', 'Unknown error')}")
                        return Decimal('0')
                else:
                    print(f"❌ HTTP error: {response.status}")
                    return Decimal('0')
        except Exception as e:
            print(f"❌ Error checking balance: {e}")
            return Decimal('0')
    
    async def get_spendable_outputs(self, address: str) -> List[Dict]:
        """Get spendable outputs for the address via API"""
        try:
            async with self.session.get(f"{self.node_url}/get_address_info", 
                                      params={"address": address, "transactions_count_limit": 0}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        return data['result']['spendable_outputs']
                    else:
                        print(f"❌ API error: {data.get('error', 'Unknown error')}")
                        return []
                else:
                    print(f"❌ HTTP error: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Error getting spendable outputs: {e}")
            return []
    
    async def deploy_contract(self, contract_info: Dict, params: Dict, 
                            address: str, private_key: int) -> bool:
        """Deploy the smart contract"""
        try:
            print(f"\n🚀 DEPLOYING {contract_info['name']}")
            print("-" * 40)
            
            # Load contract code
            contract_code = self.load_contract_code(contract_info)
            print(f"📜 Contract code length {len(contract_code)}")
            if not contract_code:
                return False
            
            # Check balance
            balance = await self.check_balance(address)
            print(f"💰 Account balance: {balance} STE")
            
            if balance <= 0:
                print("❌ Insufficient balance for deployment")
                return False
            
            # Get spendable outputs
            spendable_outputs = await self.get_spendable_outputs(address)
            if not spendable_outputs:
                print("❌ No spendable outputs found")
                return False
            
            # Calculate total available - outputs from API are dictionaries
            total_available = sum(Decimal(output['amount']) for output in spendable_outputs)
            print(f"💰 Total spendable: {total_available} STE")
            
            # Prepare constructor arguments
            constructor_args = []
            if "SRC20" in contract_info['class_name'] or "Token" in contract_info['class_name']:
                constructor_args = [
                    address,  # sender/deployer
                    params['name'],
                    params['symbol'],
                    str(params['initial_supply'])  # Convert Decimal to string for JSON serialization
                ]
            
            # Create deployment transaction
            print("📝 Creating deployment transaction...")
            
            # Calculate fees (simplified)
            fee_amount = Decimal('0.001')  # Basic fee
            change_amount = total_available - fee_amount
            
            if change_amount <= 0:
                print("❌ Insufficient balance for fees")
                return False
            
            # Create transaction inputs and outputs
            inputs = []
            input_amount = Decimal('0')
            
            # Use available outputs as inputs - API returns dictionaries
            for output in spendable_outputs:
                if input_amount < fee_amount:
                    tx_input = TransactionInput(
                        input_tx_hash=output['tx_hash'],
                        index=output['index'],
                        private_key=private_key,
                        amount=Decimal(output['amount'])
                    )
                    inputs.append(tx_input)
                    input_amount += Decimal(output['amount'])
                else:
                    break
            
            # Create change output
            outputs = []
            if change_amount > 0:
                change_output = TransactionOutput(address, change_amount)
                outputs.append(change_output)
            
            # Create smart contract transaction
            sc_transaction = SmartContractTransaction(
                inputs=inputs,
                outputs=outputs,
                operation_type=SmartContractTransaction.OPERATION_DEPLOY,
                contract_code=contract_code,
                method_name="constructor",
                method_args=constructor_args,
                gas_limit=params['gas_limit']
            )

            # Test Hex
            from_hex = await SmartContractTransaction.from_hex(sc_transaction.hex())
            print(f"Code length: {len(from_hex.contract_code)}")
            
            # Sign the transaction
            sc_transaction.sign([private_key])
            
            print("✅ Transaction created and signed")
            
            # Get deployment address
            deployment_address = self.builder.get_deployment_address(sc_transaction, address)
            print(f"📍 Contract will be deployed at: {deployment_address}")
            
            # Submit to network via API
            print("📡 Submitting to network...")
            
            # Submit transaction via deploy_contract API
            tx_hex = sc_transaction.hex()
            deploy_data = {
                "transaction_hex": tx_hex
            }
            
            async with self.session.post(f"{self.node_url}/deploy_contract", 
                                       json=deploy_data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('ok'):
                        print("✅ Contract deployment submitted successfully!")
                        print(f"📍 Contract Address: {deployment_address}")
                        print(f"🔗 Transaction Hash: {sc_transaction.hash()}")
                        
                        # Save deployment info
                        self._save_deployment_info(contract_info, deployment_address, sc_transaction.hash(), params)
                        return True
                    else:
                        print(f"❌ Deployment failed: {result.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"❌ HTTP error: {response.status}")
                    return False
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _save_deployment_info(self, contract_info: Dict, contract_address: str, 
                            tx_hash: str, params: Dict):
        """Save deployment information to a file"""
        try:
            deployments_file = Path("deployments.json")
            
            deployment_info = {
                "timestamp": int(time.time()),
                "contract_name": contract_info['name'],
                "contract_class": contract_info['class_name'],
                "contract_address": contract_address,
                "transaction_hash": tx_hash,
                "parameters": params
            }
            
            # Load existing deployments
            deployments = []
            if deployments_file.exists():
                with open(deployments_file, 'r') as f:
                    deployments = json.load(f)
            
            # Add new deployment
            deployments.append(deployment_info)
            
            # Save updated list
            with open(deployments_file, 'w') as f:
                json.dump(deployments, f, indent=2, default=str)
            
            print(f"💾 Deployment info saved to {deployments_file}")
            
        except Exception as e:
            print(f"⚠️  Could not save deployment info: {e}")
    
    async def run(self):
        """Main execution loop"""
        print("Initializing Stellaris Contract Deployer...")
        
        if not await self.initialize():
            return
        
        try:
            while True:
                self.display_menu()
                
                choice = input("\nSelect contract to deploy (0 to exit): ").strip()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                
                if choice not in self.contracts:
                    print("❌ Invalid selection. Please try again.")
                    continue
                
                contract_info = self.contracts[choice]
                
                # Get wallet credentials
                credentials = self.get_wallet_credentials()
                if not credentials:
                    print("❌ Could not get wallet credentials")
                    continue
                
                address, private_key = credentials
                
                # Get deployment parameters
                params = self.get_deployment_parameters(contract_info)
                if not params:
                    continue
                
                # Confirm deployment
                print(f"\n📋 DEPLOYMENT SUMMARY")
                print("-" * 30)
                print(f"Contract: {contract_info['name']}")
                print(f"From Address: {address}")
                print(f"Parameters: {params}")
                
                confirm = input("\nProceed with deployment? (y/n): ").lower()
                if confirm != 'y':
                    print("❌ Deployment cancelled")
                    continue
                
                try:
                    # Deploy the contract
                    success = await self.deploy_contract(contract_info, params, address, private_key)
                    
                    if success:
                        print("\n🎉 Deployment completed successfully!")
                    else:
                        print("\n💥 Deployment failed!")
                    
                    input("\nPress Enter to continue...")
                    
                except Exception as e:
                    print(f"\n❌ Deployment error: {e}")
                    input("Press Enter to continue...")
                    
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        finally:
            # Clean up resources
            await self.close()


async def main():
    """Main entry point"""
    deployer = ContractDeployer()
    await deployer.run()


if __name__ == "__main__":
    print("🌟 Stellaris Smart Contract Deployer")
    print("====================================")
    print(f"📡 Node URL: {os.getenv('NODE_HOST', 'localhost')}:{os.getenv('NODE_PORT', '3006')}")
    print("💡 Use NODE_HOST and NODE_PORT environment variables to change endpoint")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
