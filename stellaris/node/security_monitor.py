"""
security_monitor.py - Security monitoring and metrics for Stellaris

This module provides security event monitoring, logging, and metrics collection
to help track security-related events across the network.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
from enum import Enum
import json
import logging
from dataclasses import dataclass


class SecurityEventType(Enum):
    """Types of security events that can be monitored"""
    FAILED_VALIDATION = "failed_validation"
    RATE_LIMIT_HIT = "rate_limit_hit"
    PEER_BANNED = "peer_banned"
    REPLAY_ATTEMPT = "replay_attempt"
    DNS_REBINDING_ATTEMPT = "dns_rebinding_attempt" 
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    INVALID_SIGNATURE = "invalid_signature"
    HANDSHAKE_FAILURE = "handshake_failure"
    MALFORMED_REQUEST = "malformed_request"
    SYNC_ANOMALY = "sync_anomaly"
    BLOCK_VALIDATION_FAILURE = "block_validation_failure"
    TX_VALIDATION_FAILURE = "tx_validation_failure"


@dataclass
class SecurityEvent:
    """Security event record"""
    event_type: SecurityEventType
    timestamp: float
    source_ip: Optional[str] = None
    node_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SecurityMonitor:
    """
    Monitor and log security events.
    
    This class collects security metrics and events to help identify
    potential attacks or issues in the network.
    """
    
    def __init__(self, max_events: int = 1000, metrics_window: int = 3600):
        """
        Initialize the security monitor.
        
        Args:
            max_events: Maximum number of events to keep in memory
            metrics_window: Time window in seconds for metrics collection
        """
        self._metrics = {
            'failed_validations': defaultdict(int),
            'rate_limit_hits': defaultdict(int),
            'banned_peers': 0,
            'replay_attempts': 0,
            'dns_rebinding_attempts': 0,
            'resource_exhaustion_attempts': 0,
            'invalid_signatures': 0,
            'handshake_failures': defaultdict(int),
            'malformed_requests': defaultdict(int),
            'sync_anomalies': 0,
            'block_validation_failures': 0,
            'tx_validation_failures': 0
        }
        
        # Keep security events in a deque with a max length
        self._recent_events = deque(maxlen=max_events)
        
        # Maps of counts by IP address and by node ID
        self._counts_by_ip = defaultdict(lambda: defaultdict(int))
        self._counts_by_node = defaultdict(lambda: defaultdict(int))
        
        # For cleanup
        self._metrics_start_time = time.time()
        self._metrics_window = metrics_window
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        
        # Configure logger
        self._logger = logging.getLogger("stellaris.security")
        handler = logging.FileHandler("security_events.log")
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)
    
    async def start(self):
        """Start background tasks"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self):
        """Stop background tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
    
    async def _periodic_cleanup(self):
        """Reset metrics periodically"""
        while True:
            try:
                await asyncio.sleep(self._metrics_window)
                await self._reset_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Retry after a minute on error
    
    async def _reset_metrics(self):
        """Reset all metrics counters"""
        async with self._lock:
            self._metrics = {
                'failed_validations': defaultdict(int),
                'rate_limit_hits': defaultdict(int),
                'banned_peers': 0,
                'replay_attempts': 0,
                'dns_rebinding_attempts': 0,
                'resource_exhaustion_attempts': 0,
                'invalid_signatures': 0,
                'handshake_failures': defaultdict(int),
                'malformed_requests': defaultdict(int),
                'sync_anomalies': 0,
                'block_validation_failures': 0,
                'tx_validation_failures': 0
            }
            self._counts_by_ip = defaultdict(lambda: defaultdict(int))
            self._counts_by_node = defaultdict(lambda: defaultdict(int))
            self._metrics_start_time = time.time()
    
    async def log_event(self, 
                        event_type: SecurityEventType, 
                        source_ip: Optional[str] = None,
                        node_id: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None):
        """
        Log a security event.
        
        Args:
            event_type: Type of security event
            source_ip: IP address source of the event (if applicable)
            node_id: Node ID associated with the event (if applicable)
            details: Additional details about the event
        """
        event = SecurityEvent(
            event_type=event_type,
            timestamp=time.time(),
            source_ip=source_ip,
            node_id=node_id,
            details=details
        )
        
        # Log to file
        log_message = f"{event_type.value}: "
        if source_ip:
            log_message += f"IP={source_ip} "
        if node_id:
            log_message += f"Node={node_id} "
        if details:
            log_message += json.dumps(details)
        
        self._logger.info(log_message)
        
        async with self._lock:
            # Add to recent events
            self._recent_events.append(event)
            
            # Update metrics based on event type
            if event_type == SecurityEventType.FAILED_VALIDATION:
                validation_type = details.get('type', 'unknown') if details else 'unknown'
                self._metrics['failed_validations'][validation_type] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['failed_validations'] += 1
                if node_id:
                    self._counts_by_node[node_id]['failed_validations'] += 1
            
            elif event_type == SecurityEventType.RATE_LIMIT_HIT:
                endpoint = details.get('endpoint', 'unknown') if details else 'unknown'
                self._metrics['rate_limit_hits'][endpoint] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['rate_limit_hits'] += 1
                if node_id:
                    self._counts_by_node[node_id]['rate_limit_hits'] += 1
            
            elif event_type == SecurityEventType.PEER_BANNED:
                self._metrics['banned_peers'] += 1
            
            elif event_type == SecurityEventType.REPLAY_ATTEMPT:
                self._metrics['replay_attempts'] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['replay_attempts'] += 1
                if node_id:
                    self._counts_by_node[node_id]['replay_attempts'] += 1
            
            elif event_type == SecurityEventType.DNS_REBINDING_ATTEMPT:
                self._metrics['dns_rebinding_attempts'] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['dns_rebinding_attempts'] += 1
            
            elif event_type == SecurityEventType.RESOURCE_EXHAUSTION:
                self._metrics['resource_exhaustion_attempts'] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['resource_exhaustion_attempts'] += 1
                if node_id:
                    self._counts_by_node[node_id]['resource_exhaustion_attempts'] += 1
            
            elif event_type == SecurityEventType.INVALID_SIGNATURE:
                self._metrics['invalid_signatures'] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['invalid_signatures'] += 1
                if node_id:
                    self._counts_by_node[node_id]['invalid_signatures'] += 1
            
            elif event_type == SecurityEventType.HANDSHAKE_FAILURE:
                reason = details.get('reason', 'unknown') if details else 'unknown'
                self._metrics['handshake_failures'][reason] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['handshake_failures'] += 1
                if node_id:
                    self._counts_by_node[node_id]['handshake_failures'] += 1
            
            elif event_type == SecurityEventType.MALFORMED_REQUEST:
                request_type = details.get('type', 'unknown') if details else 'unknown'
                self._metrics['malformed_requests'][request_type] += 1
                if source_ip:
                    self._counts_by_ip[source_ip]['malformed_requests'] += 1
                if node_id:
                    self._counts_by_node[node_id]['malformed_requests'] += 1
            
            elif event_type == SecurityEventType.SYNC_ANOMALY:
                self._metrics['sync_anomalies'] += 1
                if node_id:
                    self._counts_by_node[node_id]['sync_anomalies'] += 1
            
            elif event_type == SecurityEventType.BLOCK_VALIDATION_FAILURE:
                self._metrics['block_validation_failures'] += 1
                if node_id:
                    self._counts_by_node[node_id]['block_validation_failures'] += 1
            
            elif event_type == SecurityEventType.TX_VALIDATION_FAILURE:
                self._metrics['tx_validation_failures'] += 1
                if node_id:
                    self._counts_by_node[node_id]['tx_validation_failures'] += 1
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get current security metrics.
        
        Returns:
            Dictionary of security metrics
        """
        async with self._lock:
            # Create a copy to avoid modifying the metrics while they're being read
            return {
                'window_start': self._metrics_start_time,
                'window_duration': self._metrics_window,
                'metrics': dict(self._metrics),
                'top_ip_offenders': self._get_top_offenders(self._counts_by_ip, 10),
                'top_node_offenders': self._get_top_offenders(self._counts_by_node, 10)
            }
    
    def _get_top_offenders(self, counts_dict: Dict, limit: int) -> List[Dict[str, Any]]:
        """
        Get the top offenders by total event count.
        
        Args:
            counts_dict: Dictionary of counts by ID
            limit: Maximum number of offenders to return
        
        Returns:
            List of offenders with their event counts
        """
        # Sum all event types for each ID
        totals = {
            id_: sum(counts.values())
            for id_, counts in counts_dict.items()
        }
        
        # Sort by total events (descending)
        sorted_ids = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        
        # Return top N offenders with detailed counts
        return [
            {
                'id': id_,
                'total': total,
                'events': dict(counts_dict[id_])
            }
            for id_, total in sorted_ids[:limit]
        ]
    
    async def get_recent_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent security events.
        
        Args:
            limit: Maximum number of events to return (None for all)
        
        Returns:
            List of recent security events
        """
        async with self._lock:
            events = list(self._recent_events)
            
            if limit is not None:
                events = events[-limit:]
            
            # Convert events to dictionaries
            return [
                {
                    'event_type': event.event_type.value,
                    'timestamp': event.timestamp,
                    'source_ip': event.source_ip,
                    'node_id': event.node_id,
                    'details': event.details
                }
                for event in events
            ]
    
    async def record_event(self, event_name: str, source_ip: Optional[str] = None, details: Optional[str] = None):
        """
        Convenience method for recording security events.
        
        This method provides a simpler interface for logging security events
        without requiring SecurityEventType enum values.
        
        Args:
            event_name: Name of the security event
            source_ip: IP address source of the event
            details: Additional details about the event
        """
        # Map common event names to SecurityEventType
        event_type_map = {
            "rate_limit_exceeded": SecurityEventType.RATE_LIMIT_HIT,
            "invalid_transaction_structure": SecurityEventType.MALFORMED_REQUEST,
            "invalid_transaction_basic": SecurityEventType.TX_VALIDATION_FAILURE,
            "invalid_transaction": SecurityEventType.TX_VALIDATION_FAILURE,
            "transaction_processing_error": SecurityEventType.TX_VALIDATION_FAILURE,
            "invalid_handshake": SecurityEventType.HANDSHAKE_FAILURE,
            "invalid_block_structure": SecurityEventType.MALFORMED_REQUEST,
            "invalid_block": SecurityEventType.BLOCK_VALIDATION_FAILURE,
            "block_processing_error": SecurityEventType.BLOCK_VALIDATION_FAILURE,
        }
        
        # Get the appropriate event type or default to MALFORMED_REQUEST
        event_type = event_type_map.get(event_name, SecurityEventType.MALFORMED_REQUEST)
        
        # Prepare details dict
        details_dict = {"reason": details} if details else None
        
        # Log the event
        await self.log_event(event_type, source_ip=source_ip, details=details_dict)


# Singleton instance
_security_monitor: Optional[SecurityMonitor] = None

def get_security_monitor() -> SecurityMonitor:
    """Get the singleton instance of SecurityMonitor"""
    global _security_monitor
    
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    
    return _security_monitor