"""
Smart Contract Transaction Builder for Stellaris
Professional-grade transaction creation and validation
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import json
import hashlib
import time

from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
from stellaris.transactions import TransactionInput, TransactionOutput
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256


class SmartContractTransactionBuilder:
    """
    Professional transaction builder for smart contracts
    Provides validation, fee calculation, and proper formatting
    """
    
    def __init__(self, gas_price: Decimal = None):
        """
        Initialize transaction builder
        
        Args:
            gas_price: Gas price in tokens per gas unit
        """
        self.gas_price = gas_price or Decimal('0.000001')  # Default gas price
        self.version = 4  # Smart contract transaction version
        
    def create_deployment_transaction(self,
                                    contract_code: str,
                                    constructor_args: List[Any] = None,
                                    input_utxos: List[Tuple[str, int, Decimal]] = None,
                                    sender_private_key: str = None,
                                    gas_limit: int = 2000000,
                                    funding_amount: Decimal = Decimal('0'),
                                    change_address: str = None) -> SmartContractTransaction:
        """
        Create a contract deployment transaction with proper wallet inputs
        
        Args:
            contract_code: The smart contract source code
            constructor_args: Arguments for contract constructor
            input_utxos: List of (tx_hash, output_index, amount) UTXOs to spend
            sender_private_key: Private key for signing (required)
            gas_limit: Maximum gas to use
            funding_amount: Amount to send with deployment
            change_address: Address to send change back to
            
        Returns:
            SmartContractTransaction ready for deployment
        """
        
        # Validate inputs
        if not contract_code or not contract_code.strip():
            raise ValueError("Contract code cannot be empty")
        
        if not input_utxos:
            raise ValueError("Input UTXOs are required for smart contract transactions")
        
        if not sender_private_key:
            raise ValueError("Private key is required to sign smart contract transactions")
        
        if gas_limit <= 0:
            raise ValueError("Gas limit must be positive")
        
        if gas_limit > 10_000_000:
            raise ValueError("Gas limit too high (max: 10,000,000)")
        
        if funding_amount < 0:
            raise ValueError("Funding amount cannot be negative")
        
        # Estimate gas and calculate fees
        estimated_gas = self._estimate_deployment_gas(contract_code)
        if gas_limit < estimated_gas:
            raise ValueError(f"Gas limit {gas_limit} too low, estimated: {estimated_gas}")
        
        estimated_gas_fee = Decimal(str(estimated_gas)) * self.gas_price
        max_gas_fee = Decimal(str(gas_limit)) * self.gas_price
        
        # Calculate total input amount
        total_input = sum(amount for _, _, amount in input_utxos)
        
        # Calculate required amount for transaction
        required_amount = funding_amount + max_gas_fee
        
        if total_input < required_amount:
            raise ValueError(f"Insufficient funds: have {total_input}, need {required_amount}")
        
        # Create transaction inputs from UTXOs
        inputs = []
        for tx_hash, output_index, amount in input_utxos:
            from stellaris.transactions.transaction_input import TransactionInput
            tx_input = TransactionInput(
                input_tx_hash=tx_hash,
                index=output_index,
                private_key=int(sender_private_key, 16) if isinstance(sender_private_key, str) else sender_private_key,
                amount=amount
            )
            inputs.append(tx_input)
        
        # Create transaction outputs
        outputs = []
        
        # Add funding output if specified
        if funding_amount > 0:
            # Contract will receive funding at deployment address
            deployment_address = self._calculate_deployment_address(
                inputs[0].get_address() if inputs else "0x0", contract_code
            )
            outputs.append(TransactionOutput(
                amount=funding_amount,
                address=deployment_address
            ))
        
        # Add change output if needed
        change_amount = total_input - funding_amount - max_gas_fee
        if change_amount > 0:
            if not change_address:
                # Use sender's address for change
                change_address = inputs[0].get_address() if inputs else None
                if not change_address:
                    raise ValueError("Change address required when there is leftover amount")
            
            outputs.append(TransactionOutput(
                amount=change_amount,
                address=change_address
            ))
        
        # Create the transaction
        transaction = SmartContractTransaction(
            inputs=inputs,
            outputs=outputs,
            operation_type=SmartContractTransaction.OPERATION_DEPLOY,
            contract_code=contract_code,
            method_args=constructor_args or [],
            gas_limit=gas_limit,
            version=self.version
        )
        
        # Sign the transaction
        transaction.sign([sender_private_key])
        
        # Add metadata
        transaction.estimated_gas = estimated_gas
        transaction.max_fee = max_gas_fee
        
        return transaction
    
    def create_call_transaction(self,
                              contract_address: str,
                              method_name: str,
                              method_args: List[Any] = None,
                              input_utxos: List[Tuple[str, int, Decimal]] = None,
                              sender_private_key: str = None,
                              value: Decimal = Decimal('0'),
                              gas_limit: int = 200000,
                              change_address: str = None) -> SmartContractTransaction:
        """
        Create a contract method call transaction with proper wallet inputs
        
        Args:
            contract_address: Address of the contract to call
            method_name: Name of the method to call
            method_args: Arguments for the method call
            input_utxos: List of (tx_hash, output_index, amount) UTXOs to spend
            sender_private_key: Private key for signing (required)
            value: Amount to send with the call
            gas_limit: Maximum gas to use
            change_address: Address to send change back to
            
        Returns:
            SmartContractTransaction ready for execution
        """
        
        # Validate inputs
        if not contract_address or len(contract_address) != 40:
            raise ValueError("Invalid contract address")
        
        if not method_name or not method_name.strip():
            raise ValueError("Method name cannot be empty")
        
        if not input_utxos:
            raise ValueError("Input UTXOs are required for smart contract transactions")
        
        if not sender_private_key:
            raise ValueError("Private key is required to sign smart contract transactions")
        
        if gas_limit <= 0:
            raise ValueError("Gas limit must be positive")
        
        if gas_limit > 5_000_000:
            raise ValueError("Gas limit too high for calls (max: 5,000,000)")
        
        if value < 0:
            raise ValueError("Value cannot be negative")
        
        # Estimate gas and calculate fees
        estimated_gas = self._estimate_call_gas(method_name, method_args or [])
        if gas_limit < estimated_gas:
            raise ValueError(f"Gas limit {gas_limit} too low, estimated: {estimated_gas}")
        
        estimated_gas_fee = Decimal(str(estimated_gas)) * self.gas_price
        max_gas_fee = Decimal(str(gas_limit)) * self.gas_price
        
        # Calculate total input amount
        total_input = sum(amount for _, _, amount in input_utxos)
        
        # Calculate required amount for transaction
        required_amount = value + max_gas_fee
        
        if total_input < required_amount:
            raise ValueError(f"Insufficient funds: have {total_input}, need {required_amount}")
        
        # Create transaction inputs from UTXOs
        inputs = []
        for tx_hash, output_index, amount in input_utxos:
            from stellaris.transactions.transaction_input import TransactionInput
            tx_input = TransactionInput(
                input_tx_hash=tx_hash,
                index=output_index,
                private_key=int(sender_private_key, 16) if isinstance(sender_private_key, str) else sender_private_key,
                amount=amount
            )
            inputs.append(tx_input)
        
        # Create transaction outputs
        outputs = []
        
        # Add value transfer if specified
        if value > 0:
            outputs.append(TransactionOutput(
                amount=value,
                address=contract_address
            ))
        
        # Add change output if needed
        change_amount = total_input - value - max_gas_fee
        if change_amount > 0:
            if not change_address:
                # Use sender's address for change
                change_address = inputs[0].get_address() if inputs else None
                if not change_address:
                    raise ValueError("Change address required when there is leftover amount")
            
            outputs.append(TransactionOutput(
                amount=change_amount,
                address=change_address
            ))
        
        # Create the transaction
        transaction = SmartContractTransaction(
            inputs=inputs,
            outputs=outputs,
            operation_type=SmartContractTransaction.OPERATION_CALL,
            contract_address=contract_address,
            method_name=method_name,
            method_args=method_args or [],
            gas_limit=gas_limit,
            version=self.version
        )
        
        # Sign the transaction
        transaction.sign([sender_private_key])
        
        # Add metadata
        transaction.estimated_gas = estimated_gas
        transaction.max_fee = max_gas_fee
        
        return transaction
    
    def _estimate_deployment_gas(self, contract_code: str) -> int:
        """Estimate gas needed for contract deployment"""
        base_gas = 32000  # Base deployment cost
        code_size = len(contract_code.encode('utf-8'))
        code_gas = code_size * 200  # Per byte cost
        
        # Additional costs for complexity
        if 'class' in contract_code:
            code_gas += 10000  # Class definition cost
        
        if 'def ' in contract_code:
            method_count = contract_code.count('def ')
            code_gas += method_count * 2000  # Per method cost
        
        return base_gas + code_gas
    
    def _estimate_call_gas(self, method_name: str, args: List[Any]) -> int:
        """Estimate gas needed for contract call"""
        base_gas = 9000  # Base call cost
        
        # Argument processing cost
        arg_gas = len(args) * 1000
        
        # Method-specific estimates
        if method_name.startswith('get_') or method_name.startswith('view_'):
            # Read-only operations
            return base_gas + arg_gas
        else:
            # State-changing operations
            return base_gas + arg_gas + 20000
    
    def _calculate_deployment_address(self, sender: str, code: str) -> str:
        """Calculate deterministic deployment address"""
        return hashlib.sha256(f"{sender}{code}{int(time.time())}".encode()).hexdigest()[:40]
    
    def _calculate_max_fee(self, gas_limit: int) -> Decimal:
        """Calculate maximum possible fee"""
        return Decimal(str(gas_limit)) * self.gas_price
    
    def validate_transaction(self, transaction: SmartContractTransaction) -> Tuple[bool, str]:
        """
        Validate a smart contract transaction
        
        Args:
            transaction: Transaction to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation
            if transaction.version != self.version:
                return False, f"Invalid version: {transaction.version}"
            
            if transaction.gas_limit <= 0:
                return False, "Gas limit must be positive"
            
            # Deployment validation
            if transaction.is_deployment():
                if not transaction.contract_code:
                    return False, "Contract code cannot be empty"
                
                if len(transaction.contract_code) > 1_000_000:  # 1MB limit
                    return False, "Contract code too large (max: 1MB)"
                
                # Basic syntax check
                try:
                    compile(transaction.contract_code, '<contract>', 'exec')
                except SyntaxError as e:
                    return False, f"Contract syntax error: {e}"
            
            # Call validation
            elif transaction.is_call():
                if not transaction.contract_address:
                    return False, "Contract address required for calls"
                
                if len(transaction.contract_address) != 40:
                    return False, "Invalid contract address format"
                
                if not transaction.method_name:
                    return False, "Method name required for calls"
                
                # Method name validation
                if not transaction.method_name.isidentifier():
                    return False, "Invalid method name format"
            
            else:
                return False, "Invalid operation type"
            
            # Gas validation
            max_gas = 10_000_000 if transaction.is_deployment() else 5_000_000
            if transaction.gas_limit > max_gas:
                return False, f"Gas limit too high (max: {max_gas:,})"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def estimate_total_cost(self, transaction: SmartContractTransaction) -> Dict[str, Decimal]:
        """
        Estimate total cost of transaction execution
        
        Args:
            transaction: Transaction to estimate
            
        Returns:
            Dictionary with cost breakdown
        """
        estimated_gas = getattr(transaction, 'estimated_gas', transaction.gas_limit)
        max_gas_fee = self._calculate_max_fee(transaction.gas_limit)
        estimated_gas_fee = Decimal(str(estimated_gas)) * self.gas_price
        
        # Value transfer cost
        value_transfer = sum(output.amount for output in transaction.outputs)
        
        return {
            'estimated_gas': Decimal(str(estimated_gas)),
            'max_gas': Decimal(str(transaction.gas_limit)),
            'gas_price': self.gas_price,
            'estimated_gas_fee': estimated_gas_fee,
            'max_gas_fee': max_gas_fee,
            'value_transfer': value_transfer,
            'estimated_total': estimated_gas_fee + value_transfer,
            'max_total': max_gas_fee + value_transfer
        }
    
    def to_hex(self, transaction: SmartContractTransaction) -> str:
        """
        Convert transaction to hex format for network transmission
        
        Args:
            transaction: Transaction to convert
            
        Returns:
            Hex string representation
        """
        return transaction.hex()
    
    def from_hex(self, hex_data: str) -> SmartContractTransaction:
        """
        Parse transaction from hex format
        
        Args:
            hex_data: Hex string to parse
            
        Returns:
            SmartContractTransaction object
        """
        import asyncio
        
        # This is a sync wrapper around the async method
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(SmartContractTransaction.from_hex(hex_data))
        except RuntimeError:
            # No event loop running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(SmartContractTransaction.from_hex(hex_data))
            finally:
                loop.close()
    
    def get_deployment_address(self, transaction: SmartContractTransaction, sender: str) -> str:
        """
        Get the address where a contract will be deployed
        
        Args:
            transaction: Deployment transaction
            sender: Deployer address
            
        Returns:
            Contract deployment address
        """
        if not transaction.is_deployment():
            raise ValueError("Transaction is not a deployment")
        
        return self._calculate_deployment_address(sender, transaction.contract_code)
