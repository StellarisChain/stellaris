"""
peer_reputation.py - Node reputation management system for Stellaris

This module implements a comprehensive peer reputation management system
to track peer behavior, assign scores, and manage peer bans.
"""

import asyncio
import time
from asyncio import Lock
from collections import deque, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set, Deque, Optional


class ViolationSeverity(Enum):
    """Severity levels for violations"""
    LOW = 1     # Minor issues like occasional timeouts
    MEDIUM = 2  # Protocol deviations, non-critical issues
    HIGH = 5    # Significant problems like invalid data
    CRITICAL = 10  # Serious violations like invalid blocks or spam attacks


@dataclass
class Violation:
    """Record of a peer violation"""
    timestamp: float
    severity: ViolationSeverity
    details: str


class PeerReputationManager:
    """
    Manages peer reputation with violation tracking and ban mechanisms.
    
    Reputation scores range from 0-100:
    - New peers start with a default score (usually 50)
    - Good behavior increases score
    - Violations decrease score
    - Peers with scores below threshold are banned
    """
    
    def __init__(self, 
                 default_score: int = 50,
                 ban_threshold: int = 10, 
                 violation_ttl: int = 86400):
        """
        Initialize the reputation manager.
        
        Args:
            default_score: Default score for new peers (0-100)
            ban_threshold: Score threshold below which peers are banned
            violation_ttl: Time in seconds violations remain active
        """
        self._peer_scores: Dict[str, int] = defaultdict(lambda: default_score)
        self._violations: Dict[str, Deque[Violation]] = defaultdict(deque)
        self._banned_peers: Set[str] = set()
        self._lock = Lock()
        
        self.default_score = default_score
        self.ban_threshold = ban_threshold
        self.violation_ttl = violation_ttl
        
        # Background task reference
        self._cleanup_task = None
    
    async def start(self):
        """Start background tasks"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self):
        """Stop background tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
    
    async def _periodic_cleanup(self):
        """Periodically clean up old violations"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly
                await self.cleanup_old_violations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Retry after a minute on error
    
    async def record_violation(self, 
                               peer_id: str, 
                               severity: ViolationSeverity, 
                               details: str = ""):
        """
        Record a violation by a peer.
        
        Args:
            peer_id: Unique identifier for the peer
            severity: Severity of the violation
            details: Description of the violation
        """
        violation = Violation(
            timestamp=time.time(),
            severity=severity,
            details=details
        )
        
        async with self._lock:
            # Add violation to history
            self._violations[peer_id].append(violation)
            
            # Apply score penalty based on severity
            score_penalty = severity.value * 10
            self._peer_scores[peer_id] -= score_penalty
            
            # Check if should ban
            if self._peer_scores[peer_id] <= self.ban_threshold:
                self._banned_peers.add(peer_id)
                print(f"Peer {peer_id} banned after violation: {details}")
    
    async def record_good_behavior(self, peer_id: str, points: int = 1):
        """
        Reward good behavior.
        
        Args:
            peer_id: Unique identifier for the peer
            points: Number of points to award (positive integer)
        """
        async with self._lock:
            # Cap score at 100
            self._peer_scores[peer_id] = min(100, self._peer_scores[peer_id] + points)
    
    async def is_banned(self, peer_id: str) -> bool:
        """
        Check if peer is banned.
        
        Args:
            peer_id: Unique identifier for the peer
        
        Returns:
            True if peer is banned, False otherwise
        """
        async with self._lock:
            return peer_id in self._banned_peers
    
    async def get_score(self, peer_id: str) -> int:
        """
        Get current peer score.
        
        Args:
            peer_id: Unique identifier for the peer
        
        Returns:
            Current reputation score (0-100)
        """
        async with self._lock:
            return self._peer_scores.get(peer_id, self.default_score)
    
    async def get_recent_violations(self, peer_id: str) -> list:
        """
        Get recent violations for a peer.
        
        Args:
            peer_id: Unique identifier for the peer
        
        Returns:
            List of recent violations
        """
        async with self._lock:
            return list(self._violations.get(peer_id, []))
    
    async def cleanup_old_violations(self):
        """Remove old violations"""
        async with self._lock:
            current_time = time.time()
            
            for peer_id, violations in list(self._violations.items()):
                # Remove old violations
                while violations and current_time - violations[0].timestamp > self.violation_ttl:
                    violations.popleft()
                
                # Remove peer data if no violations
                if not violations and peer_id not in self._banned_peers:
                    del self._violations[peer_id]
                    if peer_id in self._peer_scores and self._peer_scores[peer_id] >= 0:
                        del self._peer_scores[peer_id]
    
    async def get_banned_peers(self) -> Set[str]:
        """
        Get set of banned peer IDs.
        
        Returns:
            Set of banned peer IDs
        """
        async with self._lock:
            return set(self._banned_peers)
    
    async def unban_peer(self, peer_id: str) -> bool:
        """
        Unban a peer and reset their score.
        
        Args:
            peer_id: Unique identifier for the peer
        
        Returns:
            True if peer was unbanned, False if peer wasn't banned
        """
        async with self._lock:
            if peer_id in self._banned_peers:
                self._banned_peers.remove(peer_id)
                self._peer_scores[peer_id] = self.default_score
                return True
            return False


# Singleton instance
_peer_reputation_manager: Optional[PeerReputationManager] = None

def get_reputation_manager() -> PeerReputationManager:
    """Get the singleton instance of PeerReputationManager"""
    global _peer_reputation_manager
    
    if _peer_reputation_manager is None:
        _peer_reputation_manager = PeerReputationManager()
    
    return _peer_reputation_manager