"""
Example demonstrating RestrictedPython integration with Stellaris VM
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stellaris.svm.restricted_vm import RestrictedStellarisVM
from decimal import Decimal

def demonstrate_restricted_vm():
    """Demonstrate the RestrictedPython-enhanced VM"""
    
    # Create the restricted VM
    vm = RestrictedStellarisVM()
    
    # Set up some initial balances
    vm.balances["deployer"] = Decimal('1000')
    vm.balances["user1"] = Decimal('100')
    vm.balances["user2"] = Decimal('50')
    
    print("=== RestrictedPython VM Demo ===\n")
    
    # Example 1: Simple token contract
    token_contract_code = '''
class TokenContract(SmartContract):
    def constructor(self, sender, name, symbol, total_supply):
        self.set_storage("name", name)
        self.set_storage("symbol", symbol)
        self.set_storage("total_supply", int(total_supply))
        self.set_storage(f"balance_{sender}", int(total_supply))
    
    def transfer(self, sender, to, amount):
        amount = int(amount)
        sender_balance = self.get_storage(f"balance_{sender}", 0)
        
        if sender_balance < amount:
            raise ValueError("Insufficient balance")
        
        # Update balances
        self.set_storage(f"balance_{sender}", sender_balance - amount)
        to_balance = self.get_storage(f"balance_{to}", 0)
        self.set_storage(f"balance_{to}", to_balance + amount)
        
        return True
    
    def get_balance(self, sender, address):
        return self.get_storage(f"balance_{address}", 0)
    
    def get_info(self, sender):
        return {
            "name": self.get_storage("name"),
            "symbol": self.get_storage("symbol"),
            "total_supply": self.get_storage("total_supply")
        }
'''
    
    try:
        # Deploy the token contract
        print("1. Deploying token contract...")
        token_address = vm.deploy_contract(
            token_contract_code, 
            "deployer", 
            constructor_args=["MyToken", "MTK", 1000000]
        )
        print(f"   Contract deployed at: {token_address}")
        
        # Test contract calls
        print("\n2. Testing contract calls...")
        
        # Get contract info
        info = vm.call_contract(token_address, "get_info")
        print(f"   Token info: {info}")
        
        # Check initial balance
        balance = vm.call_contract(token_address, "get_balance", "deployer")
        print(f"   Deployer balance: {balance}")
        
        # Transfer tokens
        print("\n3. Transferring tokens...")
        vm.execution_context.sender = "deployer"  # Set sender context
        result = vm.call_contract(token_address, "transfer", "user1", 100)
        print(f"   Transfer result: {result}")
        
        # Check balances after transfer
        deployer_balance = vm.call_contract(token_address, "get_balance", "deployer")
        user1_balance = vm.call_contract(token_address, "get_balance", "user1")
        print(f"   Deployer balance after transfer: {deployer_balance}")
        print(f"   User1 balance after transfer: {user1_balance}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*50)
    
    # Example 2: Demonstrate security restrictions
    print("\n4. Testing security restrictions...")
    
    malicious_contract_code = '''
class MaliciousContract(SmartContract):
    def evil_function(self, sender):
        # This should be blocked by RestrictedPython
        import os
        return os.listdir("/")
    
    def another_evil_function(self, sender):
        # This should also be blocked
        return __import__("subprocess").call(["ls"])
'''
    
    try:
        print("   Attempting to deploy malicious contract...")
        malicious_address = vm.deploy_contract(malicious_contract_code, "deployer")
        print(f"   Malicious contract deployed at: {malicious_address}")
        
        # Try to call the evil function
        print("   Attempting to call evil function...")
        result = vm.call_contract(malicious_address, "evil_function")
        print(f"   Evil function result: {result}")
        
    except Exception as e:
        print(f"   ✓ Security restriction worked: {e}")
    
    # Example 3: Contract with loops (should be allowed but monitored)
    loop_contract_code = '''
class LoopContract(SmartContract):
    def safe_loop(self, sender, count):
        total = 0
        for i in range(min(int(count), 1000)):  # Limit iterations
            total += i
        return total
    
    def factorial(self, sender, n):
        n = int(n)
        if n > 20:  # Prevent huge calculations
            raise ValueError("Number too large")
        
        result = 1
        for i in range(1, n + 1):
            result *= i
        return result
'''
    
    try:
        print("\n5. Testing loop contract...")
        loop_address = vm.deploy_contract(loop_contract_code, "deployer")
        print(f"   Loop contract deployed at: {loop_address}")
        
        # Test safe operations
        result1 = vm.call_contract(loop_address, "safe_loop", 100)
        print(f"   Safe loop result (sum 0-99): {result1}")
        
        result2 = vm.call_contract(loop_address, "factorial", 5)
        print(f"   Factorial of 5: {result2}")
        
    except Exception as e:
        print(f"   Error in loop contract: {e}")

if __name__ == "__main__":
    demonstrate_restricted_vm()
