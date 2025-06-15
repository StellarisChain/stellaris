from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict

@dataclass
class DHTRecord:
    """Represents a stored record in the DHT."""
    key: str
    value: Any
    timestamp: float
    ttl: int
    publisher: str
    signature: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + self.ttl)