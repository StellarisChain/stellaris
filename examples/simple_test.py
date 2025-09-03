"""
Simple test for the Stellaris Virtual Machine
"""

import sys
import os
sys.path.append('.')

from decimal import Decimal
from stellaris.svm.vm import StellarisVM
from stellaris.svm.exceptions import *

def test_simple_contract():
    """Test a simple contract"""
    print("=== Testing Simple Contract ===")
    
    vm = StellarisVM()
    
    # Simple contract code
    contract_code = '''
class SimpleToken(SmartContract):
    def __init__(self, vm, address):
        super().__init__(vm, address)
    
    @self.export
    def constructor(self, sender: str, initial_supply: Decimal):
        self.set_storage('total_supply', initial_supply)
        balances = {sender: initial_supply}
        self.set_storage('balances', balances)
        self.set_storage('owner', sender)
    
    @self.export
    def balance_of(self, sender: str, account: str) -> Decimal:
        balances = self.get_storage('balances') or {}
        return balances.get(account, Decimal('0'))
    
    @self.export
    def transfer(self, sender: str, to: str, amount: Decimal) -> bool:
        if amount <= 0:
            raise Exception('Amount must be positive')
        
        balances = self.get_storage('balances') or {}
        sender_balance = balances.get(sender, Decimal('0'))
        
        if sender_balance < amount:
            raise Exception('Insufficient balance')
        
        balances[sender] = sender_balance - amount
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        return True
    
    @self.export
    def get_info(self, sender: str) -> dict:
        return {
            'total_supply': str(self.get_storage('total_supply')),
            'owner': self.get_storage('owner')
        }
'''
    
    # Deploy contract
    deployer = "0x1234"
    try:
        contract_address = vm.deploy_contract(
            code=contract_code,
            constructor_args=[Decimal('1000')],
            deployer=deployer,
            gas_limit=500000
        )
        print(f"✓ Contract deployed at: {contract_address}")
        
        # Test contract calls
        balance = vm.call_contract(contract_address, "balance_of", deployer, sender=deployer)
        print(f"✓ Deployer balance: {balance}")
        
        # Test transfer
        recipient = "0x5678"
        vm.call_contract(contract_address, "transfer", recipient, Decimal('100'), sender=deployer)
        
        deployer_balance = vm.call_contract(contract_address, "balance_of", deployer, sender=deployer)
        recipient_balance = vm.call_contract(contract_address, "balance_of", recipient, sender=recipient)
        
        print(f"✓ After transfer - Deployer: {deployer_balance}, Recipient: {recipient_balance}")
        
        # Test contract info
        info = vm.call_contract(contract_address, "get_info", sender=deployer)
        print(f"✓ Contract info: {info}")
        
        print("✅ Simple contract test passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Stellaris Virtual Machine - Simple Test")
    print("=" * 50)
    test_simple_contract()
