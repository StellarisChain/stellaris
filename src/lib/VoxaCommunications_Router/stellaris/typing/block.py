import hashlib
import json
import time
import rsa
import base64
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from lib.VoxaCommunications_Router.stellaris.typing.block_header import BlockHeader
from lib.VoxaCommunications_Router.stellaris.typing.transactions import Transaction
from lib.VoxaCommunications_Router.stellaris.typing.block_status import BlockStatus

@dataclass
class Block:
    """Represents a single block in the Stellaris blockchain"""
    header: BlockHeader
    transactions: List[Transaction]
    hash: str = ""
    status: BlockStatus = BlockStatus.PENDING
    confirmations: int = 0
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate the hash of the entire block"""
        return self.header.calculate_hash()
    
    def calculate_merkle_root(self) -> str:
        """Calculate the Merkle root of all transactions in the block"""
        if not self.transactions:
            return hashlib.sha256(b'').hexdigest()
        
        # Create list of transaction hashes
        tx_hashes = [tx.tx_id for tx in self.transactions]
        
        # Calculate Merkle root
        while len(tx_hashes) > 1:
            next_level = []
            for i in range(0, len(tx_hashes), 2):
                left = tx_hashes[i]
                right = tx_hashes[i + 1] if i + 1 < len(tx_hashes) else left
                combined = left + right
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            tx_hashes = next_level
        
        return tx_hashes[0]
    
    def validate_block(self, previous_block: Optional['Block'] = None) -> bool:
        """Validate the block structure and transactions"""
        # Validate block hash
        if self.hash != self.calculate_hash():
            return False
        
        # Validate merkle root
        if self.header.merkle_root != self.calculate_merkle_root():
            return False
        
        # Validate previous hash reference
        if previous_block and self.header.previous_hash != previous_block.hash:
            return False
        
        # Validate timestamp (should be within reasonable bounds)
        current_time = int(time.time())
        if self.header.timestamp > current_time + 7200:  # 2 hours in future
            return False
        
        # Validate all transactions
        for tx in self.transactions:
            if not self.validate_transaction(tx):
                return False
        
        return True
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate a single transaction"""
        # Validate transaction hash
        if transaction.tx_id != transaction.calculate_hash():
            return False
        
        # Basic validation checks
        if transaction.fee < 0:
            return False
        
        if not transaction.inputs and not transaction.outputs:
            return False
        
        # Validate digital signature
        if not self.verify_transaction_signature(transaction):
            return False
        
        # TODO: Implement UTXO validation
        
        return True
    
    def verify_transaction_signature(self, transaction: Transaction) -> bool:
        """Verify the digital signature of a transaction"""
        try:
            # Reconstruct the message that was signed (transaction data without signature)
            tx_data = {
                'inputs': transaction.inputs,
                'outputs': transaction.outputs,
                'fee': transaction.fee,
                'timestamp': transaction.timestamp,
                'public_key': transaction.public_key,
                'nonce': transaction.nonce
            }
            message = json.dumps(tx_data, sort_keys=True).encode('utf-8')
            
            # Decode the signature from base64
            signature_bytes = base64.b64decode(transaction.signature)
            
            # Load the public key
            public_key = rsa.PublicKey.load_pkcs1(transaction.public_key.encode('utf-8'), format='PEM')
            
            # Verify the signature
            try:
                rsa.verify(message, signature_bytes, public_key)
                return True
            except rsa.VerificationError:
                return False
                
        except (ValueError, TypeError, Exception):
            # Invalid signature format or other errors
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': asdict(self.header),
            'transactions': [tx.to_dict() for tx in self.transactions],
            'hash': self.hash,
            'status': self.status.value,
            'confirmations': self.confirmations
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        header = BlockHeader(**data['header'])
        transactions = [Transaction.from_dict(tx_data) for tx_data in data['transactions']]
        return cls(
            header=header,
            transactions=transactions,
            hash=data['hash'],
            status=BlockStatus(data['status']),
            confirmations=data['confirmations']
        )