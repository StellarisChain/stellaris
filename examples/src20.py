"""
Simple SRC20 Token Contract - Basic ERC20-compatible token for Stellaris blockchain

This is a simplified version of the SRC20 token that demonstrates the basic
functionality of the Stellaris Virtual Machine.
"""

from decimal import Decimal

class SimpleSRC20(SmartContract):
    """
    Simple SRC20 Token Contract - Basic ERC20 implementation
    """
    
    def __init__(self, vm, address):
        super().__init__(vm, address)
    
    @self.export
    def constructor(self, sender: str, name: str, symbol: str, initial_supply: Decimal):
        """Initialize the token"""
        self.set_storage('name', name)
        self.set_storage('symbol', symbol)
        self.set_storage('decimals', 18)
        self.set_storage('total_supply', initial_supply)
        self.set_storage('owner', sender)
        
        # Give initial supply to deployer
        balances = {}
        balances[sender] = initial_supply
        self.set_storage('balances', balances)
        self.set_storage('allowances', {})
    
    @self.export
    def name(self, sender: str) -> str:
        """Get token name"""
        return self.get_storage('name')
    
    @self.export
    def symbol(self, sender: str) -> str:
        """Get token symbol"""
        return self.get_storage('symbol')
    
    @self.export
    def decimals(self, sender: str) -> int:
        """Get token decimals"""
        return self.get_storage('decimals')
    
    @self.export
    def total_supply(self, sender: str) -> Decimal:
        """Get total supply"""
        return self.get_storage('total_supply')
    
    @self.export
    def balance_of(self, sender: str, account: str) -> Decimal:
        """Get balance of account"""
        balances = self.get_storage('balances') or {}
        return balances.get(account, Decimal('0'))
    
    @self.export
    def transfer(self, sender: str, to: str, amount: Decimal) -> bool:
        """Transfer tokens"""
        if amount <= 0:
            raise Exception('Amount must be positive')
        
        if sender == to:
            raise Exception('Cannot transfer to self')
        
        balances = self.get_storage('balances') or {}
        sender_balance = balances.get(sender, Decimal('0'))
        
        if sender_balance < amount:
            raise Exception(f'Insufficient balance: {sender_balance} < {amount}')
        
        # Update balances
        balances[sender] = sender_balance - amount
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        return True
    
    @self.export
    def approve(self, sender: str, spender: str, amount: Decimal) -> bool:
        """Approve spender to spend tokens"""
        if amount < 0:
            raise Exception('Amount cannot be negative')
        
        allowances = self.get_storage('allowances') or {}
        if sender not in allowances:
            allowances[sender] = {}
        
        allowances[sender][spender] = amount
        self.set_storage('allowances', allowances)
        
        return True
    
    @self.export
    def allowance(self, sender: str, owner: str, spender: str) -> Decimal:
        """Get allowance amount"""
        allowances = self.get_storage('allowances') or {}
        owner_allowances = allowances.get(owner, {})
        return owner_allowances.get(spender, Decimal('0'))
    
    @self.export
    def transfer_from(self, sender: str, from_addr: str, to: str, amount: Decimal) -> bool:
        """Transfer tokens using allowance"""
        if amount <= 0:
            raise Exception('Amount must be positive')
        
        # Check allowance
        allowances = self.get_storage('allowances') or {}
        from_allowances = allowances.get(from_addr, {})
        allowed = from_allowances.get(sender, Decimal('0'))
        
        if allowed < amount:
            raise Exception(f'Insufficient allowance: {allowed} < {amount}')
        
        # Check balance
        balances = self.get_storage('balances') or {}
        from_balance = balances.get(from_addr, Decimal('0'))
        
        if from_balance < amount:
            raise Exception(f'Insufficient balance: {from_balance} < {amount}')
        
        # Update balances
        balances[from_addr] = from_balance - amount
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        # Update allowance
        from_allowances[sender] = allowed - amount
        allowances[from_addr] = from_allowances
        self.set_storage('allowances', allowances)
        
        return True
    
    @self.export
    def mint(self, sender: str, to: str, amount: Decimal) -> bool:
        """Mint new tokens (only owner)"""
        owner = self.get_storage('owner')
        if sender != owner:
            raise Exception('Only owner can mint')
        
        if amount <= 0:
            raise Exception('Amount must be positive')
        
        balances = self.get_storage('balances') or {}
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        # Update total supply
        total_supply = self.get_storage('total_supply')
        self.set_storage('total_supply', total_supply + amount)
        
        return True
    
    @self.export
    def get_balances(self, sender: str) -> dict:
        """Get all balances (for debugging)"""
        return self.get_storage('balances') or {}