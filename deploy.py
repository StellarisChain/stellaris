#!/usr/bin/env python3
"""
Smart Contract Management Script for Stellaris Blockchain

This script provides an interactive interface for:
- Deploying smart contracts to the Stellaris blockchain
- Calling methods on deployed contracts (both view and state-changing calls)
- Listing previously deployed contracts
- Managing contract interactions with wallet integration

Features:
- Deploy new smart contracts with customizable parameters
- Call contract methods with automatic method detection
- View-only calls for reading contract state
- State-changing calls that create transactions
- Track deployment history in deployments.json
- Integration with Stellaris wallet system

SETUP: you need to have stellaris-wallet cloned in the root directory, then renamed to stellaris_wallet
and install its dependencies with pip install -r stellaris_wallet/requirements.txt
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
import traceback
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
    """Main class for contract deployment and interaction operations"""
    
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
        """Display the main menu"""
        print("\n" + "="*60)
        print("🚀 STELLARIS SMART CONTRACT MANAGER")
        print("="*60)
        print("\nChoose an action:")
        print("-" * 40)
        print("D. Deploy a new contract")
        print("C. Call existing contract")
        print("L. List deployed contracts")
        print("0. Exit")
        print("-" * 40)
    
    def display_deploy_menu(self):
        """Display the contract deployment menu"""
        print("\n" + "="*50)
        print("📜 CONTRACT DEPLOYMENT")
        print("="*50)
        print("\nAvailable Smart Contracts:")
        print("-" * 40)
        
        for key, contract in self.contracts.items():
            print(f"{key}. {contract['name']}")
            print(f"   📝 {contract['description']}")
            print(f"   📁 {contract['file']}")
            print()
        
        print("0. Back to main menu")
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
            # Initialize database if not already done
            from stellaris.database import Database
            if not Database.instance:
                Database.instance = await Database.create()
            
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
                if contract_info['class_name'] == 'SRC20Token':  # Enhanced SRC20
                    constructor_args = [
                        params['name'],  # name: str
                        params['symbol'],  # symbol: str  
                        18,  # decimals: int (standard 18 decimals)
                        params['initial_supply']  # max_supply: Decimal (the sender parameter is auto-provided by VM)
                    ]
                else:  # Simple SRC20
                    constructor_args = [
                        params['name'],  # name: str
                        params['symbol'],  # symbol: str  
                        18,  # decimals: int (standard 18 decimals)
                        params['initial_supply']  # max_supply: Decimal
                    ]
            
            # Create deployment transaction
            print("📝 Creating deployment transaction...")
            
            # Calculate fees (simplified)
            fee_amount = Decimal('0.001')  # Basic fee
            
            # Create transaction inputs - collect enough to cover fees
            inputs = []
            input_amount = Decimal('0')
            
            # Use available outputs as inputs - API returns dictionaries
            for output in spendable_outputs:
                # Collect inputs until we have enough to cover fees
                if input_amount < fee_amount * 2:  # Collect a bit more than just the fee amount
                    # Derive public key from private key for verification
                    from fastecdsa import keys
                    from stellaris.constants import CURVE
                    public_key = keys.get_public_key(private_key, CURVE)
                    
                    print(f"  Using UTXO: {output['tx_hash'][:16]}..., index: {output['index']}, amount: {output['amount']}")
                    
                    tx_input = TransactionInput(
                        input_tx_hash=output['tx_hash'],
                        index=int(output['index']),  # Convert to int
                        private_key=private_key,  # Set the private key directly
                        amount=Decimal(output['amount']),
                        public_key=public_key
                    )
                    inputs.append(tx_input)
                    input_amount += Decimal(output['amount'])
                    
                    print(f"  Input amount so far: {input_amount}")
                else:
                    break
            
            # Check if we have enough inputs to cover fees
            if input_amount < fee_amount:
                print("❌ Insufficient balance for fees")
                return False
            
            # Calculate change amount based on actual collected inputs
            change_amount = input_amount - fee_amount
            
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

            # Test Hex - commented out as it's not necessary and might cause type issues
            # from_hex = await SmartContractTransaction.from_hex(sc_transaction.hex())
            # print(f"Code length: {len(from_hex.contract_code)}")
            
            # Sign the transaction
            sc_transaction.sign([private_key])
            
            print("✅ Transaction created and signed")
            print(f"📊 Transaction details:")
            print(f"   - Inputs: {len(sc_transaction.inputs)}")
            print(f"   - Outputs: {len(sc_transaction.outputs)}")
            print(f"   - Total input amount: {sum(inp.amount for inp in sc_transaction.inputs)}")
            print(f"   - Total output amount: {sum(out.amount for out in sc_transaction.outputs)}")
            print(f"   - Implied fee: {sum(inp.amount for inp in sc_transaction.inputs) - sum(out.amount for out in sc_transaction.outputs)}")
            
            # Test transaction verification before submitting
            try:
                print("🔍 Testing transaction verification...")
                verification_result = await sc_transaction.verify(check_double_spend=True)
                print(f"   - Verification result: {verification_result}")
                if not verification_result:
                    print("❌ Transaction failed local verification!")
                    return False
            except Exception as e:
                print(f"❌ Transaction verification failed: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # Get deployment address
            deployment_address = self.builder.get_deployment_address(sc_transaction, address)
            print(f"📍 Contract will be deployed at: {deployment_address}")
            
            # Submit to network via API
            print("📡 Submitting to network...")
            
            # Submit transaction via deploy_contract API
            tx_hex = sc_transaction.hex()
            print(f"🔍 Debug info before submission:")
            print(f"   - Transaction hex length: {len(tx_hex)}")
            print(f"   - Transaction hash: {sc_transaction.hash()}")
            print(f"   - Input signatures: {[inp.signed is not None for inp in sc_transaction.inputs]}")
            print(f"   - Hex preview: {tx_hex[:100]}...")
            
            deploy_data = {
                "transaction_hex": tx_hex
            }
            
            async with self.session.post(f"{self.node_url}/deploy_contract", 
                                       json=deploy_data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('ok'):
                        print("✅ Contract deployment submitted successfully!")
                        print(f"📍 Contract Address: {result.get("result").get("contract_address")}")
                        print(f"🔗 Transaction Hash: {sc_transaction.hash()}")
                        
                        # Save deployment info
                        self._save_deployment_info(contract_info, result.get("result").get("contract_address"), sc_transaction.hash(), params)
                        return True
                    else:
                        print(f"❌ Contract Deployment failed: {result.get('error', 'Unknown error')}")
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
                "parameters": params,
                "source_file": contract_info['file']
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
    
    def load_deployed_contracts(self) -> List[Dict]:
        """Load list of deployed contracts from deployments.json"""
        try:
            deployments_file = Path("deployments.json")
            if not deployments_file.exists():
                return []
            
            with open(deployments_file, 'r') as f:
                deployments = json.load(f)
            
            return deployments
            
        except Exception as e:
            print(f"❌ Error loading deployed contracts: {e}")
            return []
    
    def display_deployed_contracts(self, deployments: List[Dict]):
        """Display list of deployed contracts"""
        if not deployments:
            print("📭 No deployed contracts found")
            print("💡 Deploy a contract first using the 'D' option")
            return
        
        print("\n" + "="*60)
        print("📋 DEPLOYED CONTRACTS")
        print("="*60)
        
        for i, deployment in enumerate(deployments, 1):
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deployment['timestamp']))
            print(f"\n{i}. {deployment['contract_name']} ({deployment['contract_class']})")
            print(f"   📍 Address: {deployment['contract_address']}")
            print(f"   🔗 TX Hash: {deployment['transaction_hash']}")
            print(f"   📅 Deployed: {timestamp}")
            if 'parameters' in deployment:
                params = deployment['parameters']
                if params:
                    print(f"   ⚙️  Parameters: {params}")
    
    def select_deployed_contract(self, deployments: List[Dict]) -> Optional[Dict]:
        """Let user select a deployed contract"""
        if not deployments:
            return None
        
        self.display_deployed_contracts(deployments)
        
        try:
            choice = input(f"\nSelect contract (1-{len(deployments)}) or 0 to cancel: ").strip()
            if choice == "0":
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(deployments):
                return deployments[index]
            else:
                print("❌ Invalid selection")
                return None
                
        except ValueError:
            print("❌ Invalid input")
            return None
    
    def get_contract_methods(self, contract_file: str) -> List[str]:
        """Extract available methods from contract source code"""
        try:
            if not Path(contract_file).exists():
                print(f"⚠️  Contract source file not found: {contract_file}")
                return []
            
            with open(contract_file, 'r') as f:
                content = f.read()
            
            # Simple method extraction - look for def methods
            methods = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('def ') and not line.startswith('def __'):
                    # Extract method name
                    method_name = line.split('(')[0].replace('def ', '').strip()
                    if method_name not in ['constructor']:  # Skip constructor
                        methods.append(method_name)
            
            return methods
            
        except Exception as e:
            print(f"❌ Error extracting methods: {e}")
            return []
    
    def get_call_parameters(self, method_name: str) -> Tuple[List[str], bool]:
        """Get parameters for contract method call"""
        print(f"\n⚙️  CALLING METHOD: {method_name}")
        print("-" * 40)
        
        # Ask if this is a view call or state-changing call
        call_type = input("Is this a view call (read-only)? (y/n): ").lower().strip()
        is_view = call_type == 'y'
        
        # Get method arguments
        args = []
        print("\nEnter method arguments (press Enter with no input to finish):")
        
        arg_index = 0
        while True:
            arg_value = input(f"Argument {arg_index + 1}: ").strip()
            if not arg_value:
                break
            args.append(arg_value)
            arg_index += 1
        
        return args, is_view
    
    async def call_contract_method(self, contract_address: str, method_name: str, 
                                 method_args: List[str], is_view: bool,
                                 sender_address: str, private_key: int) -> bool:
        """Call a method on a deployed contract"""
        try:
            print(f"\n📞 CALLING CONTRACT METHOD")
            print("-" * 30)
            print(f"Contract: {contract_address}")
            print(f"Method: {method_name}")
            print(f"Arguments: {method_args}")
            print(f"View call: {is_view}")
            
            if is_view:
                # For view calls, use the call_contract API endpoint
                call_data = {
                    "contract_address": contract_address,
                    "method_name": method_name,
                    "method_args": method_args,
                    "sender_address": sender_address
                }
                
                async with self.session.post(f"{self.node_url}/call_contract", 
                                           json=call_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('ok'):
                            print("✅ View call successful!")
                            print(f"📤 Result: {result.get('result', 'No return value')}")
                            return True
                        else:
                            print(f"❌ View call failed: {result.get('error', 'Unknown error')}")
                            return False
                    else:
                        print(f"❌ HTTP error: {response.status}")
                        return False
            else:
                # For state-changing calls, create and submit a transaction
                return await self._create_call_transaction(
                    contract_address, method_name, method_args, 
                    sender_address, private_key
                )
                
        except Exception as e:
            print(f"❌ Contract call failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _create_call_transaction(self, contract_address: str, method_name: str,
                                     method_args: List[str], sender_address: str, 
                                     private_key: int) -> bool:
        """Create and submit a state-changing contract call transaction"""
        try:
            # Initialize database if not already done
            from stellaris.database import Database
            if not Database.instance:
                Database.instance = await Database.create()
            
            # Check balance and get spendable outputs
            balance = await self.check_balance(sender_address)
            print(f"💰 Account balance: {balance} STE")
            
            if balance <= 0:
                print("❌ Insufficient balance for transaction")
                return False
            
            spendable_outputs = await self.get_spendable_outputs(sender_address)
            if not spendable_outputs:
                print("❌ No spendable outputs found")
                return False
            
            total_available = sum(Decimal(output['amount']) for output in spendable_outputs)
            print(f"💰 Total spendable: {total_available} STE")
            
            # Calculate fees
            fee_amount = Decimal('0.001')
            
            # Create transaction inputs - collect enough to cover fees
            inputs = []
            input_amount = Decimal('0')
            
            for output in spendable_outputs:
                # Collect inputs until we have enough to cover fees 
                if input_amount < fee_amount * 2:  # Collect a bit more than just the fee amount
                    # Derive public key from private key for verification
                    from fastecdsa import keys
                    from stellaris.constants import CURVE
                    public_key = keys.get_public_key(private_key, CURVE)
                    
                    tx_input = TransactionInput(
                        input_tx_hash=output['tx_hash'],
                        index=int(output['index']),  # Convert to int
                        private_key=private_key,  # Set the private key directly
                        amount=Decimal(output['amount']),
                        public_key=public_key
                    )
                    inputs.append(tx_input)
                    input_amount += Decimal(output['amount'])
                else:
                    break
            
            # Check if we have enough inputs to cover fees
            if input_amount < fee_amount:
                print("❌ Insufficient balance for fees")
                return False
            
            # Calculate change amount based on actual collected inputs
            change_amount = input_amount - fee_amount
            
            # Create change output
            outputs = []
            if change_amount > 0:
                change_output = TransactionOutput(sender_address, change_amount)
                outputs.append(change_output)
            
            # Get gas limit
            gas_limit = input("Gas limit (press Enter for default 100000): ").strip()
            gas_limit = int(gas_limit) if gas_limit else 100000
            
            # Create smart contract call transaction
            sc_transaction = SmartContractTransaction(
                inputs=inputs,
                outputs=outputs,
                operation_type=SmartContractTransaction.OPERATION_CALL,
                contract_address=contract_address,
                method_name=method_name,
                method_args=method_args,
                gas_limit=gas_limit
            )
            
            # Sign the transaction
            sc_transaction.sign([private_key])
            
            print("✅ Transaction created and signed")
            
            # Submit to network
            print("📡 Submitting to network...")
            
            call_data = {
                "transaction_hex": sc_transaction.hex()
            }
            
            async with self.session.post(f"{self.node_url}/call_contract", 
                                       json=call_data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('ok'):
                        print("✅ Contract call submitted successfully!")
                        print(f"🔗 Transaction Hash: {sc_transaction.hash()}")
                        if result.get('result'):
                            print(f"📤 Result: {result['result']}")
                        return True
                    else:
                        print(f"❌ Contract call failed: {result.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"❌ HTTP error: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Transaction creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run(self):
        """Main execution loop"""
        print("Initializing Stellaris Contract Manager...")
        
        if not await self.initialize():
            return
        
        try:
            while True:
                self.display_menu()
                
                choice = input("\nSelect action (D/C/L/0): ").strip().upper()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                elif choice == "D":
                    await self.handle_deployment()
                elif choice == "C":
                    await self.handle_contract_call()
                elif choice == "L":
                    self.handle_list_contracts()
                else:
                    print("❌ Invalid selection. Please try again.")
                    continue
                    
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        finally:
            # Clean up resources
            await self.close()
    
    async def handle_deployment(self):
        """Handle contract deployment workflow"""
        while True:
            self.display_deploy_menu()
            
            choice = input("\nSelect contract to deploy (0 to back): ").strip()
            
            if choice == "0":
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
                break
                
            except Exception as e:
                print(f"\n❌ Deployment error: {e}")
                input("Press Enter to continue...")
                break
    
    async def handle_contract_call(self):
        """Handle contract call workflow"""
        # Load deployed contracts
        deployments = self.load_deployed_contracts()
        if not deployments:
            print("📭 No deployed contracts found")
            print("💡 Deploy a contract first using the 'D' option")
            input("Press Enter to continue...")
            return
        
        # Select contract
        selected_contract = self.select_deployed_contract(deployments)
        if not selected_contract:
            return
        
        contract_address = selected_contract['contract_address']
        contract_name = selected_contract['contract_name']
        source_file = selected_contract.get('source_file', '')
        
        print(f"\n🎯 Selected: {contract_name}")
        print(f"📍 Address: {contract_address}")
        
        # Get available methods
        available_methods = self.get_contract_methods(source_file)
        if available_methods:
            print(f"\n📋 Available methods: {', '.join(available_methods)}")
        else:
            print("⚠️  Could not auto-detect methods from source file")
        
        # Get method name
        method_name = input("\nEnter method name to call: ").strip()
        if not method_name:
            print("❌ Method name is required")
            return
        
        # Get method parameters
        method_args, is_view = self.get_call_parameters(method_name)
        
        # Get wallet credentials for calling
        credentials = self.get_wallet_credentials()
        if not credentials:
            print("❌ Could not get wallet credentials")
            return
        
        sender_address, private_key = credentials
        
        # Confirm call
        print(f"\n� CALL SUMMARY")
        print("-" * 25)
        print(f"Contract: {contract_name}")
        print(f"Address: {contract_address}")
        print(f"Method: {method_name}")
        print(f"Arguments: {method_args}")
        print(f"Sender: {sender_address}")
        print(f"Type: {'View (read-only)' if is_view else 'State-changing'}")
        
        confirm = input("\nProceed with call? (y/n): ").lower()
        if confirm != 'y':
            print("❌ Call cancelled")
            return
        
        try:
            # Call the contract method
            success = await self.call_contract_method(
                contract_address, method_name, method_args, is_view,
                sender_address, private_key
            )
            
            if success:
                print("\n🎉 Contract call completed successfully!")
            else:
                print("\n💥 Contract call failed!")
            
            input("\nPress Enter to continue...")
            
        except Exception as e:
            print(f"\n❌ Contract call error: {e}")
            input("Press Enter to continue...")
    
    def handle_list_contracts(self):
        """Handle listing deployed contracts"""
        deployments = self.load_deployed_contracts()
        self.display_deployed_contracts(deployments)
        input("\nPress Enter to continue...")


async def main():
    """Main entry point"""
    deployer = ContractDeployer()
    await deployer.run()


if __name__ == "__main__":
    print("🌟 Stellaris Smart Contract Manager")
    print("===================================")
    print(f"📡 Node URL: {os.getenv('NODE_HOST', 'localhost')}:{os.getenv('NODE_PORT', '3006')}")
    print("💡 Use NODE_HOST and NODE_PORT environment variables to change endpoint")
    print("🔧 Features: Deploy contracts | Call contract methods | List deployments")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
