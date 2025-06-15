import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from lib.VoxaCommunications_Router.dht.dht_node import DHTNode
from lib.VoxaCommunications_Router.dht.dht_record import DHTRecord

class KBucket:
    """K-bucket for storing nodes at a specific distance."""
    
    def __init__(self, k: int = 20):
        self.k = k
        self.nodes: List[DHTNode] = []
        self.last_updated = time.time()
    
    def add_node(self, node: DHTNode) -> bool:
        """Add a node to the k-bucket."""
        # Remove if already exists
        self.nodes = [n for n in self.nodes if n.node_id != node.node_id]
        
        if len(self.nodes) < self.k:
            self.nodes.append(node)
            self.last_updated = time.time()
            return True
        else:
            # K-bucket is full, implement replacement strategy
            # For now, replace the oldest node
            oldest_node = min(self.nodes, key=lambda n: n.last_seen)
            if node.last_seen > oldest_node.last_seen:
                self.nodes.remove(oldest_node)
                self.nodes.append(node)
                self.last_updated = time.time()
                return True
        
        return False
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the k-bucket."""
        original_length = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        return len(self.nodes) < original_length
    
    def get_nodes(self) -> List[DHTNode]:
        """Get all nodes in the k-bucket."""
        return self.nodes.copy()