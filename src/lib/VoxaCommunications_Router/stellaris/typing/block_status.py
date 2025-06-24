from enum import Enum

class BlockStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ORPHANED = "orphaned"