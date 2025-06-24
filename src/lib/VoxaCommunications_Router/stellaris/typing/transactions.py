import json
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class Transaction:
    """Represents a single transaction in the Stellaris blockchain"""
    tx_id: str
    inputs: List[Dict[str, Any]]  # UTXOs being spent
    outputs: List[Dict[str, Any]]  # New UTXOs being created
    fee: int  # Transaction fee in stellaris (smallest unit)
    timestamp: int
    signature: str
    public_key: str
    nonce: int = 0
    
    def __post_init__(self):
        if not self.tx_id:
            self.tx_id = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate the hash of the transaction"""
        tx_data = {
            'inputs': self.inputs,
            'outputs': self.outputs,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'public_key': self.public_key,
            'nonce': self.nonce
        }
        tx_string = json.dumps(tx_data, sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transaction':
        return cls(**data)