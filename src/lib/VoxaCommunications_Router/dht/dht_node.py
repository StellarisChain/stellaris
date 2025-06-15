from dataclasses import dataclass, field, asdict

@dataclass
class DHTNode:
    """Represents a node in the DHT."""
    node_id: str
    address: str
    last_seen: float
    distance: int = 0
    
    def __post_init__(self):
        if isinstance(self.node_id, str):
            self.node_id_bytes = bytes.fromhex(self.node_id)
        else:
            self.node_id_bytes = self.node_id