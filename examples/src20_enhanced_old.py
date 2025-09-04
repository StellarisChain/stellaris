"""
SRC20 Token Contract - Enhanced ERC20-compatible token for Stellaris blockchain

This is a comprehensive token contract that implements the ERC20 standard
with additional features like minting, burning, pausing, and access control.
"""

from decimal import Decimal
from typing import Dict, Optional, List
import hashlib
import json
import time
import sys
import os

# Add the stellaris package to path if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stellaris.svm.vm import SmartContract

class SRC20Token(SmartContract):
    """
    SRC20 Token Contract - Enhanced ERC20-compatible implementation
    
    Features:
    - Standard ERC20 functionality (transfer, approve, transferFrom)
    - Minting and burning capabilities
    - Pausable functionality for emergency stops
    - Access control with owner and minter roles
    - Event logging
    - Supply cap management
    - Blacklist functionality
    """
    
    def __init__(self, vm, address):
        super().__init__(vm, address)
        
        # Initialize storage keys if not exists
        if not self.get_storage('initialized'):
            self.set_storage('initialized', True)
            self.set_storage('balances', {})
            self.set_storage('allowances', {})
            self.set_storage('total_supply', Decimal('0'))
            self.set_storage('paused', False)
            self.set_storage('blacklist', {})
            self.set_storage('events', [])
    
    def export(self, func):
        """Decorator to mark functions as contract exports"""
        self._exports[func.__name__] = func
        return func

    def constructor(self, sender: str, name: str, symbol: str, decimals: int = 18, 
                   max_supply: Optional[Decimal] = None):
        """
        Initialize the token contract
        
        Args:
            sender: Address of the deployer (becomes owner)
            name: Token name (e.g., "Stellaris Token")
            symbol: Token symbol (e.g., "STAR")
            decimals: Number of decimal places
            max_supply: Maximum supply cap (optional)
        """
        # Validate inputs
        if not name or len(name) > 50:
            raise Exception("Invalid token name")
        if not symbol or len(symbol) > 10:
            raise Exception("Invalid token symbol")
        if decimals < 0 or decimals > 18:
            raise Exception("Invalid decimals")
        if max_supply and max_supply <= 0:
            raise Exception("Invalid max supply")
        
        # Set token metadata
        self.set_storage('name', name)
        self.set_storage('symbol', symbol)
        self.set_storage('decimals', decimals)
        self.set_storage('owner', sender)
        self.set_storage('minters', {sender: True})
        
        if max_supply:
            self.set_storage('max_supply', max_supply)
        
        # Emit Transfer event for contract creation
        self._emit_event('Transfer', {
            'from': '0x0',
            'to': sender,
            'value': Decimal('0')
        })
        
        # Emit deployment event
        self._emit_event('TokenDeployed', {
            'name': name,
            'symbol': symbol,
            'decimals': decimals,
            'owner': sender,
            'max_supply': str(max_supply) if max_supply else None
        })
    
    @self.export
    def name(self, sender: str) -> str:
        """Get token name"""
        return self.get_storage('name') or ""
    
    @self.export
    def symbol(self, sender: str) -> str:
        """Get token symbol"""
        return self.get_storage('symbol') or ""
    
    @self.export
    def decimals(self, sender: str) -> int:
        """Get token decimals"""
        return self.get_storage('decimals') or 18
    
    @self.export
    def total_supply(self, sender: str) -> Decimal:
        """Get total token supply"""
        return self.get_storage('total_supply') or Decimal('0')
    
    @self.export
    def balance_of(self, sender: str, account: str) -> Decimal:
        """Get balance of an account"""
        balances = self.get_storage('balances') or {}
        return balances.get(account, Decimal('0'))
    
    @self.export
    def allowance(self, sender: str, owner: str, spender: str) -> Decimal:
        """Get allowance amount"""
        allowances = self.get_storage('allowances') or {}
        owner_allowances = allowances.get(owner, {})
        return owner_allowances.get(spender, Decimal('0'))
    
    @self.export
    def transfer(self, sender: str, to: str, amount: Decimal) -> bool:
        """
        Transfer tokens from sender to recipient
        
        Args:
            sender: Address sending tokens
            to: Address receiving tokens
            amount: Amount to transfer
            
        Returns:
            bool: True if successful
        """
        self._require_not_paused()
        self._require_not_blacklisted(sender)
        self._require_not_blacklisted(to)
        
        if amount <= 0:
            raise Exception("Transfer amount must be positive")
        
        if sender == to:
            raise Exception("Cannot transfer to self")
        
        balances = self.get_storage('balances') or {}
        sender_balance = balances.get(sender, Decimal('0'))
        
        if sender_balance < amount:
            raise Exception(f"Insufficient balance: {sender_balance} < {amount}")
        
        # Update balances
        balances[sender] = sender_balance - amount
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        # Emit Transfer event
        self._emit_event('Transfer', {
            'from': sender,
            'to': to,
            'value': amount
        })
        
        return True
    
    @self.export
    def approve(self, sender: str, spender: str, amount: Decimal) -> bool:
        """
        Approve spender to spend tokens on behalf of sender
        
        Args:
            sender: Address approving the spending
            spender: Address being approved to spend
            amount: Amount to approve
            
        Returns:
            bool: True if successful
        """
        self._require_not_paused()
        self._require_not_blacklisted(sender)
        self._require_not_blacklisted(spender)
        
        if amount < 0:
            raise Exception("Approve amount cannot be negative")
        
        if sender == spender:
            raise Exception("Cannot approve self")
        
        allowances = self.get_storage('allowances') or {}
        if sender not in allowances:
            allowances[sender] = {}
        
        allowances[sender][spender] = amount
        self.set_storage('allowances', allowances)
        
        # Emit Approval event
        self._emit_event('Approval', {
            'owner': sender,
            'spender': spender,
            'value': amount
        })
        
        return True
    
    @self.export
    def transfer_from(self, sender: str, from_addr: str, to: str, amount: Decimal) -> bool:
        """
        Transfer tokens from one address to another using allowance
        
        Args:
            sender: Address executing the transfer
            from_addr: Address tokens are transferred from
            to: Address tokens are transferred to
            amount: Amount to transfer
            
        Returns:
            bool: True if successful
        """
        self._require_not_paused()
        self._require_not_blacklisted(sender)
        self._require_not_blacklisted(from_addr)
        self._require_not_blacklisted(to)
        
        if amount <= 0:
            raise Exception("Transfer amount must be positive")
        
        # Check allowance
        allowances = self.get_storage('allowances') or {}
        from_allowances = allowances.get(from_addr, {})
        allowed_amount = from_allowances.get(sender, Decimal('0'))
        
        if allowed_amount < amount:
            raise Exception(f"Insufficient allowance: {allowed_amount} < {amount}")
        
        # Check balance
        balances = self.get_storage('balances') or {}
        from_balance = balances.get(from_addr, Decimal('0'))
        
        if from_balance < amount:
            raise Exception(f"Insufficient balance: {from_balance} < {amount}")
        
        # Update balances
        balances[from_addr] = from_balance - amount
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        
        # Update allowance
        from_allowances[sender] = allowed_amount - amount
        allowances[from_addr] = from_allowances
        self.set_storage('allowances', allowances)
        
        # Emit Transfer event
        self._emit_event('Transfer', {
            'from': from_addr,
            'to': to,
            'value': amount
        })
        
        return True
    
    @self.export
    def mint(self, sender: str, to: str, amount: Decimal) -> bool:
        """
        Mint new tokens (only minters)
        
        Args:
            sender: Address requesting the mint
            to: Address receiving new tokens
            amount: Amount to mint
            
        Returns:
            bool: True if successful
        """
        self._require_minter(sender)
        self._require_not_paused()
        self._require_not_blacklisted(to)
        
        if amount <= 0:
            raise Exception("Mint amount must be positive")
        
        # Check max supply
        max_supply = self.get_storage('max_supply')
        current_supply = self.get_storage('total_supply') or Decimal('0')
        
        if max_supply and current_supply + amount > max_supply:
            raise Exception(f"Would exceed max supply: {current_supply + amount} > {max_supply}")
        
        # Update balances and supply
        balances = self.get_storage('balances') or {}
        balances[to] = balances.get(to, Decimal('0')) + amount
        self.set_storage('balances', balances)
        self.set_storage('total_supply', current_supply + amount)
        
        # Emit Transfer event
        self._emit_event('Transfer', {
            'from': '0x0',
            'to': to,
            'value': amount
        })
        
        # Emit Mint event
        self._emit_event('Mint', {
            'to': to,
            'value': amount,
            'minter': sender
        })
        
        return True
    
    @self.export
    def burn(self, sender: str, amount: Decimal) -> bool:
        """
        Burn tokens from sender's balance
        
        Args:
            sender: Address burning tokens
            amount: Amount to burn
            
        Returns:
            bool: True if successful
        """
        self._require_not_paused()
        
        if amount <= 0:
            raise Exception("Burn amount must be positive")
        
        balances = self.get_storage('balances') or {}
        sender_balance = balances.get(sender, Decimal('0'))
        
        if sender_balance < amount:
            raise Exception(f"Insufficient balance to burn: {sender_balance} < {amount}")
        
        # Update balance and supply
        balances[sender] = sender_balance - amount
        self.set_storage('balances', balances)
        
        current_supply = self.get_storage('total_supply') or Decimal('0')
        self.set_storage('total_supply', current_supply - amount)
        
        # Emit Transfer event
        self._emit_event('Transfer', {
            'from': sender,
            'to': '0x0',
            'value': amount
        })
        
        # Emit Burn event
        self._emit_event('Burn', {
            'from': sender,
            'value': amount
        })
        
        return True
    
    @self.export
    def pause(self, sender: str):
        """Pause all token operations (only owner)"""
        self._require_owner(sender)
        self.set_storage('paused', True)
        
        self._emit_event('Paused', {'by': sender})
    
    @self.export
    def unpause(self, sender: str):
        """Unpause token operations (only owner)"""
        self._require_owner(sender)
        self.set_storage('paused', False)
        
        self._emit_event('Unpaused', {'by': sender})
    
    @self.export
    def is_paused(self, sender: str) -> bool:
        """Check if contract is paused"""
        return self.get_storage('paused') or False
    
    @self.export
    def add_minter(self, sender: str, minter: str):
        """Add a new minter (only owner)"""
        self._require_owner(sender)
        
        minters = self.get_storage('minters') or {}
        minters[minter] = True
        self.set_storage('minters', minters)
        
        self._emit_event('MinterAdded', {'minter': minter, 'by': sender})
    
    @self.export
    def remove_minter(self, sender: str, minter: str):
        """Remove a minter (only owner)"""
        self._require_owner(sender)
        
        minters = self.get_storage('minters') or {}
        if minter in minters:
            del minters[minter]
            self.set_storage('minters', minters)
        
        self._emit_event('MinterRemoved', {'minter': minter, 'by': sender})
    
    @self.export
    def is_minter(self, sender: str, account: str) -> bool:
        """Check if account is a minter"""
        minters = self.get_storage('minters') or {}
        return minters.get(account, False)
    
    @self.export
    def blacklist(self, sender: str, account: str):
        """Blacklist an account (only owner)"""
        self._require_owner(sender)
        
        blacklisted = self.get_storage('blacklist') or {}
        blacklisted[account] = True
        self.set_storage('blacklist', blacklisted)
        
        self._emit_event('Blacklisted', {'account': account, 'by': sender})
    
    @self.export
    def unblacklist(self, sender: str, account: str):
        """Remove account from blacklist (only owner)"""
        self._require_owner(sender)
        
        blacklisted = self.get_storage('blacklist') or {}
        if account in blacklisted:
            del blacklisted[account]
            self.set_storage('blacklist', blacklisted)
        
        self._emit_event('Unblacklisted', {'account': account, 'by': sender})
    
    @self.export
    def is_blacklisted(self, sender: str, account: str) -> bool:
        """Check if account is blacklisted"""
        blacklisted = self.get_storage('blacklist') or {}
        return blacklisted.get(account, False)
    
    @self.export
    def transfer_ownership(self, sender: str, new_owner: str):
        """Transfer contract ownership (only current owner)"""
        self._require_owner(sender)
        
        if not new_owner:
            raise Exception("New owner cannot be empty")
        
        old_owner = self.get_storage('owner')
        self.set_storage('owner', new_owner)
        
        # Remove old owner from minters and add new owner
        minters = self.get_storage('minters') or {}
        if old_owner in minters:
            del minters[old_owner]
        minters[new_owner] = True
        self.set_storage('minters', minters)
        
        self._emit_event('OwnershipTransferred', {
            'previous_owner': old_owner,
            'new_owner': new_owner
        })
    
    @self.export
    def get_events(self, sender: str, event_type: Optional[str] = None) -> List[Dict]:
        """Get contract events"""
        events = self.get_storage('events') or []
        
        if event_type:
            return [event for event in events if event.get('type') == event_type]
        
        return events
    
    @self.export
    def get_info(self, sender: str) -> Dict:
        """Get comprehensive token information"""
        return {
            'name': self.get_storage('name'),
            'symbol': self.get_storage('symbol'),
            'decimals': self.get_storage('decimals'),
            'total_supply': str(self.get_storage('total_supply') or Decimal('0')),
            'max_supply': str(self.get_storage('max_supply')) if self.get_storage('max_supply') else None,
            'owner': self.get_storage('owner'),
            'paused': self.get_storage('paused') or False,
            'contract_address': self.address
        }
    
    # Internal helper methods
    def _require_owner(self, sender: str):
        """Require sender to be the contract owner"""
        owner = self.get_storage('owner')
        if sender != owner:
            raise Exception(f"Only owner can perform this action. Owner: {owner}, Sender: {sender}")
    
    def _require_minter(self, sender: str):
        """Require sender to be a minter"""
        minters = self.get_storage('minters') or {}
        if not minters.get(sender, False):
            raise Exception("Only minters can perform this action")
    
    def _require_not_paused(self):
        """Require contract to not be paused"""
        if self.get_storage('paused'):
            raise Exception("Contract is paused")
    
    def _require_not_blacklisted(self, account: str):
        """Require account to not be blacklisted"""
        blacklisted = self.get_storage('blacklist') or {}
        if blacklisted.get(account, False):
            raise Exception(f"Account {account} is blacklisted")
    
    def _emit_event(self, event_type: str, data: Dict):
        """Emit an event by storing it in contract storage"""
        events = self.get_storage('events') or []
        
        event = {
            'type': event_type,
            'data': data,
            'block_number': 1,  # TODO: Get from blockchain context
            'timestamp': int(time.time()),
            'transaction_hash': 'mock_hash'  # TODO: Get from execution context
        }
        
        events.append(event)
        
        # Keep only last 1000 events to prevent storage bloat
        if len(events) > 1000:
            events = events[-1000:]
        
        self.set_storage('events', events)
