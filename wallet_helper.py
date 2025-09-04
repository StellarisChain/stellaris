#!/usr/bin/env python3
"""
Wallet Credential Helper for Stellaris Contract Deployment

This script helps generate and manage wallet credentials for testing
smart contract deployments.
"""

import os
import sys
import json
from pathlib import Path
from typing import Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from stellaris.utils.general import point_to_string
from fastecdsa import keys, curve

def generate_test_wallet() -> Tuple[str, int]:
    """Generate a new test wallet with random private key"""
    # Generate random private key
    private_key = keys.gen_private_key(curve.secp256k1)
    
    # Generate public key and address
    public_key = keys.get_public_key(private_key, curve.secp256k1)
    address = point_to_string(public_key)
    
    return address, private_key

def save_test_wallet(address: str, private_key: int, name: str = "test_wallet"):
    """Save test wallet to file"""
    wallet_data = {
        "name": name,
        "address": address,
        "private_key": hex(private_key),
        "private_key_int": private_key,
        "created_at": "test_wallet_for_deployment",
        "note": "This is a test wallet for smart contract deployment. DO NOT use in production!"
    }
    
    # Create wallet directory if it doesn't exist
    wallet_dir = Path("test_wallets")
    wallet_dir.mkdir(exist_ok=True)
    
    # Save wallet file
    wallet_file = wallet_dir / f"{name}.json"
    with open(wallet_file, 'w') as f:
        json.dump(wallet_data, f, indent=2)
    
    print(f"✅ Test wallet saved to: {wallet_file}")
    return wallet_file

def load_test_wallet(name: str = "test_wallet") -> Tuple[str, int]:
    """Load test wallet from file"""
    wallet_file = Path("test_wallets") / f"{name}.json"
    
    if not wallet_file.exists():
        print(f"❌ Wallet file not found: {wallet_file}")
        return None, None
    
    try:
        with open(wallet_file, 'r') as f:
            wallet_data = json.load(f)
        
        address = wallet_data['address']
        private_key = wallet_data['private_key_int']
        
        return address, private_key
        
    except Exception as e:
        print(f"❌ Error loading wallet: {e}")
        return None, None

def main():
    """Main function"""
    print("🔑 Stellaris Wallet Credential Helper")
    print("====================================")
    
    print("\nOptions:")
    print("1. Generate new test wallet")
    print("2. Load existing test wallet")
    print("3. List test wallets")
    print("0. Exit")
    
    choice = input("\nSelect option: ").strip()
    
    if choice == "1":
        name = input("Enter wallet name (default: test_wallet): ").strip() or "test_wallet"
        
        print("🔄 Generating new test wallet...")
        address, private_key = generate_test_wallet()
        
        print(f"✅ Generated test wallet:")
        print(f"   Address: {address}")
        print(f"   Private Key: {hex(private_key)}")
        
        save_choice = input("\nSave this wallet? (y/n): ").lower()
        if save_choice == 'y':
            save_test_wallet(address, private_key, name)
            print("\n⚠️  IMPORTANT: This is a TEST wallet only!")
            print("   DO NOT use this in production or send real funds to this address!")
    
    elif choice == "2":
        name = input("Enter wallet name (default: test_wallet): ").strip() or "test_wallet"
        
        address, private_key = load_test_wallet(name)
        if address and private_key:
            print(f"✅ Loaded test wallet:")
            print(f"   Address: {address}")
            print(f"   Private Key: {hex(private_key)}")
    
    elif choice == "3":
        wallet_dir = Path("test_wallets")
        if wallet_dir.exists():
            wallet_files = list(wallet_dir.glob("*.json"))
            if wallet_files:
                print("📁 Available test wallets:")
                for wallet_file in wallet_files:
                    print(f"   - {wallet_file.stem}")
            else:
                print("📁 No test wallets found")
        else:
            print("📁 No test wallets directory found")
    
    elif choice == "0":
        print("👋 Goodbye!")
    
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
