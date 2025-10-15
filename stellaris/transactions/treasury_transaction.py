from decimal import Decimal

from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256
from stellaris.transactions import TransactionOutput


class TreasuryTransaction:
    """
    A special transaction type for distributing network tax to the treasury wallet.
    Similar to CoinbaseTransaction but for treasury distributions.
    """
    _hex: str = None

    def __init__(self, block_hash: str, treasury_address: str, amount: Decimal, start_block: int, end_block: int):
        self.block_hash = block_hash
        self.treasury_address = treasury_address
        self.amount = amount
        self.start_block = start_block  # Starting block for tax period
        self.end_block = end_block      # Ending block for tax period
        self.outputs = [TransactionOutput(treasury_address, amount)]

    async def verify(self):
        """Verify that the treasury transaction is valid"""
        from stellaris.database import Database
        from stellaris.constants import BLOCK_CONFIG
        
        db = await Database.get()
        block = await db.get_block(self.block_hash)
        
        if not block:
            return False
            
        # Check if this is a valid treasury block (multiple of tax interval)
        treasury_config = BLOCK_CONFIG.get('treasury', {})
        tax_interval = treasury_config.get('tax_interval', 25000)
        
        if block['id'] % tax_interval != 0:
            return False
            
        # Check if treasury address matches configuration
        expected_treasury = treasury_config.get('wallet_address')
        if self.treasury_address != expected_treasury:
            return False
            
        return True

    def hex(self):
        if self._hex is not None:
            return self._hex
            
        # Use a special identifier for treasury transactions (different from coinbase)
        hex_inputs = (bytes.fromhex(self.block_hash) + (2).to_bytes(1, ENDIAN)).hex()  # 2 = treasury type
        hex_outputs = ''.join(tx_output.tobytes().hex() for tx_output in self.outputs)

        if all(len(tx_output.address_bytes) == 64 for tx_output in self.outputs):
            version = 1
        elif all(len(tx_output.address_bytes) == 33 for tx_output in self.outputs):
            version = 2
        else:
            raise NotImplementedError()

        # Include period information in the transaction
        period_info = (
            self.start_block.to_bytes(4, ENDIAN) + 
            self.end_block.to_bytes(4, ENDIAN)
        ).hex()

        self._hex = ''.join([
            version.to_bytes(1, ENDIAN).hex(),
            (1).to_bytes(1, ENDIAN).hex(),
            hex_inputs,
            (1).to_bytes(1, ENDIAN).hex(),
            hex_outputs,
            (44).to_bytes(1, ENDIAN).hex(),  # 36 + 8 bytes for period info
            period_info
        ])

        return self._hex

    def hash(self):
        return sha256(self.hex())