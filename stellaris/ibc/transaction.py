from typing import List, Optional
from decimal import Decimal
from stellaris.transactions.transaction import Transaction
from stellaris.transactions import TransactionInput, TransactionOutput
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256
from stellaris.ibc.messages import IBCMessage, create_message_from_dict
import json

class IBCTransaction(Transaction):
    """
    IBC Transaction class for handling Inter-Blockchain Communication messages.
    Extends the base Transaction class to support IBC-specific functionality.
    """
    
    def __init__(self, inputs: List[TransactionInput], outputs: List[TransactionOutput], 
                 ibc_message: IBCMessage, fee: Decimal = Decimal(0), version: int = 4):
        """
        Initialize IBC transaction.
        
        Args:
            inputs: Transaction inputs (for fees)
            outputs: Transaction outputs (for fees)
            ibc_message: The IBC message to include
            fee: Transaction fee
            version: Transaction version (4 for IBC)
        """
        # Convert IBC message to bytes for the message field
        message_bytes = ibc_message.to_bytes()
        
        # Call parent constructor with IBC message as the transaction message
        super().__init__(inputs, outputs, message_bytes, version)
        
        self.ibc_message = ibc_message
        self.fee = fee
        self.ibc_version = version
        
    @classmethod
    async def from_hex(cls, hex_string: str) -> 'IBCTransaction':
        """
        Create IBC transaction from hex string.
        Overrides parent method to handle IBC-specific deserialization.
        """
        # First create as regular transaction
        regular_tx = await Transaction.from_hex(hex_string)
        
        # Check if this is an IBC transaction (version 4)
        if regular_tx.version != 4:
            raise ValueError(f"Not an IBC transaction (version {regular_tx.version})")
        
        # Deserialize IBC message from transaction message
        if regular_tx.message is None:
            raise ValueError("IBC transaction missing message data")
        
        try:
            message_dict = json.loads(regular_tx.message.decode('utf-8'))
            ibc_message = create_message_from_dict(message_dict)
        except Exception as e:
            raise ValueError(f"Failed to deserialize IBC message: {e}")
        
        # Create IBC transaction
        ibc_tx = cls(
            inputs=regular_tx.inputs,
            outputs=regular_tx.outputs,
            ibc_message=ibc_message,
            version=regular_tx.version
        )
        
        # Copy over computed fields
        ibc_tx._hex = regular_tx._hex
        ibc_tx.fees = regular_tx.fees
        ibc_tx.tx_hash = regular_tx.tx_hash
        
        return ibc_tx
    
    def get_message_type(self) -> str:
        """Get the IBC message type"""
        return self.ibc_message.type
    
    def get_message_data(self) -> dict:
        """Get the IBC message data"""
        return self.ibc_message.data
    
    async def verify_ibc_specific(self) -> bool:
        """
        Verify IBC-specific constraints.
        This is called in addition to the regular transaction verification.
        """
        try:
            # Verify message structure
            if not self.ibc_message or not self.ibc_message.type:
                return False
            
            # Verify message type is supported
            from stellaris.ibc.messages import MESSAGE_TYPES
            if self.ibc_message.type not in MESSAGE_TYPES:
                return False
            
            # Verify message data is valid
            if not isinstance(self.ibc_message.data, dict):
                return False
            
            # Additional IBC-specific verifications can be added here
            return True
            
        except Exception as e:
            print(f"IBC verification error: {e}")
            return False
    
    async def verify(self, check_double_spend: bool = True) -> bool:
        """
        Verify the IBC transaction.
        Includes both regular transaction verification and IBC-specific checks.
        """
        # First verify as regular transaction
        if not await super().verify(check_double_spend):
            return False
        
        # Then verify IBC-specific constraints
        return await self.verify_ibc_specific()
    
    def hex(self, full: bool = True) -> str:
        """
        Override hex method to ensure proper IBC transaction serialization.
        """
        # Use parent implementation but ensure version is 4
        if self.version != 4:
            self.version = 4
        
        return super().hex(full)
    
    def __str__(self) -> str:
        return f"IBCTransaction(type={self.ibc_message.type}, hash={self.hash()[:16]}...)"
    
    def __repr__(self) -> str:
        return self.__str__()