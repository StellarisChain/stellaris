import hashlib
import json
from dataclasses import dataclass, asdict
from lib.VoxaCommunications_Router.stellaris import __version__ as stellaris_version

@dataclass
class BlockHeader:
    """Block header containing metadata"""
    index: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    nonce: int
    version: int = stellaris_version or "0.1.0"
    
    def calculate_hash(self) -> str:
        """Calculate the hash of the block header"""
        header_data = asdict(self)
        header_string = json.dumps(header_data, sort_keys=True)
        return hashlib.sha256(header_string.encode()).hexdigest()