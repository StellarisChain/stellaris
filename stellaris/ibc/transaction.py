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
        # Parse hex string manually to avoid recursion
        from io import BytesIO
        from stellaris.constants import ENDIAN
        from stellaris.transactions import TransactionInput, TransactionOutput
        from stellaris.utils.general import bytes_to_string
        from decimal import Decimal
        from stellaris.constants import SMALLEST
        import json
        
        tx_bytes = BytesIO(bytes.fromhex(hex_string))
        version = int.from_bytes(tx_bytes.read(1), ENDIAN)
        
        # Check if this is an IBC transaction (version 4)
        if version != 4:
            raise ValueError(f"Not an IBC transaction (version {version})")

        inputs_count = int.from_bytes(tx_bytes.read(1), ENDIAN)
        inputs = []

        for i in range(0, inputs_count):
            tx_hex = tx_bytes.read(32).hex()
            tx_index = int.from_bytes(tx_bytes.read(1), ENDIAN)
            inputs.append(TransactionInput(tx_hex, index=tx_index))

        outputs_count = int.from_bytes(tx_bytes.read(1), ENDIAN)
        outputs = []

        for i in range(0, outputs_count):
            pubkey = tx_bytes.read(33)  # Version 4 uses 33-byte keys
            amount_length = int.from_bytes(tx_bytes.read(1), ENDIAN)
            amount = int.from_bytes(tx_bytes.read(amount_length), ENDIAN) / Decimal(SMALLEST)
            outputs.append(TransactionOutput(bytes_to_string(pubkey), amount))

        specifier = int.from_bytes(tx_bytes.read(1), ENDIAN)
        if specifier == 1:
            message_length = int.from_bytes(tx_bytes.read(2), ENDIAN)  # Version 4 uses 2 bytes
            message = tx_bytes.read(message_length)
        else:
            raise ValueError("IBC transactions must have a message")

        # Deserialize IBC message from transaction message
        try:
            message_dict = json.loads(message.decode('utf-8'))
            ibc_message = create_message_from_dict(message_dict)
        except Exception as e:
            raise ValueError(f"Failed to deserialize IBC message: {e}")
        
        # Read signatures
        signatures = []
        while True:
            try:
                signed = (int.from_bytes(tx_bytes.read(32), ENDIAN), int.from_bytes(tx_bytes.read(32), ENDIAN))
                if signed[0] == 0:
                    break
                signatures.append(signed)
            except:
                break

        # Set signatures on inputs
        if len(signatures) == 1:
            for tx_input in inputs:
                tx_input.signed = signatures[0]
        elif len(inputs) == len(signatures):
            for i, tx_input in enumerate(inputs):
                tx_input.signed = signatures[i]
        
        # Create IBC transaction
        ibc_tx = cls(
            inputs=inputs,
            outputs=outputs,
            ibc_message=ibc_message,
            version=version
        )
        
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
            supported_types = [
                "client_create", "client_update",
                "connection_open_init", "connection_open_try", "connection_open_ack", "connection_open_confirm",
                "channel_open_init", "channel_open_try", "channel_open_ack", "channel_open_confirm",
                "packet_send", "packet_receive", "packet_ack", "packet_timeout"
            ]
            if self.ibc_message.type not in supported_types:
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