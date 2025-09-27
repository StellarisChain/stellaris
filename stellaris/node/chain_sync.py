"""
Chain synchronization module for Stellaris blockchain.

This module handles intelligent syncing of the blockchain with peers,
implementing both push and pull strategies for efficient synchronization.
"""

import asyncio
import time
import logging
import random
from typing import Dict, List, Optional, Any, Set, Tuple

from stellaris.node.handshake_handler import get_handshake_manager
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.security_monitor import get_security_monitor
from stellaris.node.block_processor import get_block_processor
from stellaris.database import Database

# Setup logging
logger = logging.getLogger("stellaris.node.chain_sync")


class ChainSynchronizer:
    """
    Intelligent chain synchronization manager.
    
    Handles blockchain synchronization with peers using both push and pull strategies:
    - Pull: Request missing blocks from peers when we detect we're behind
    - Push: Announce new blocks to peers when we receive them
    
    Also implements smart peer selection, parallel downloads, and efficient
    fork resolution.
    """
    
    def __init__(self):
        self.db = None
        self.handshake_manager = get_handshake_manager()
        self.reputation_manager = get_reputation_manager()
        self.security_monitor = get_security_monitor()
        self.block_processor = get_block_processor()
        
        self.is_running = False
        self.is_syncing = False
        self.last_sync_time = 0
        self.sync_interval = 300  # 5 minutes between full sync checks
        self.sync_lock = asyncio.Lock()
        self.known_peer_heights = {}  # peer -> height
        
        # Sync metrics
        self.sync_stats = {
            "last_sync_time": 0,
            "last_sync_duration": 0,
            "blocks_processed": 0,
            "sync_failures": 0,
            "peer_timeouts": {}  # peer -> count
        }
    
    def set_db(self, db: Database):
        """Set database connection."""
        self.db = db
    
    async def start(self):
        """Start the chain synchronizer."""
        if self.is_running:
            return
            
        self.is_running = True
        asyncio.create_task(self._sync_loop())
        logger.info("Chain synchronizer started")
    
    async def stop(self):
        """Stop the chain synchronizer."""
        self.is_running = False
        logger.info("Chain synchronizer stopped")
    
    async def _sync_loop(self):
        """Main synchronization loop."""
        while self.is_running:
            try:
                # Check if it's time to sync
                current_time = time.time()
                if current_time - self.last_sync_time >= self.sync_interval:
                    # Run a full sync
                    await self.sync_with_peers()
                    self.last_sync_time = current_time
                
                # Sleep for a bit before checking again
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)  # Longer sleep on error
    
    async def sync_with_peers(self):
        """
        Synchronize blockchain with peers.
        
        This method implements the core synchronization logic:
        1. Get height information from multiple peers
        2. Determine best peer to sync from
        3. Download and validate missing blocks
        """
        # Prevent multiple syncs from running simultaneously
        if self.is_syncing:
            logger.info("Sync already in progress, skipping")
            return
            
        async with self.sync_lock:
            try:
                self.is_syncing = True
                sync_start_time = time.time()
                blocks_processed = 0
                
                # Get our current height
                our_height = await self._get_our_height()
                logger.info(f"Our current height: {our_height}")
                
                # Get heights from peers
                trusted_peers = await self.handshake_manager.get_trusted_peers()
                if not trusted_peers:
                    logger.warning("No trusted peers available for sync")
                    return
                
                # Query peer heights in parallel
                peer_heights = await self._get_peer_heights(trusted_peers)
                if not peer_heights:
                    logger.warning("Could not get heights from any peers")
                    return
                
                # Update known peer heights
                self.known_peer_heights = peer_heights
                
                # Find best peer to sync from
                best_peers = self._select_best_peers(peer_heights, our_height)
                if not best_peers:
                    logger.info("No peers with higher height found, we're up to date")
                    return
                
                # Start synchronization
                logger.info(f"Starting sync from height {our_height} with peers: {best_peers}")
                
                # Sync blocks in batches
                blocks_processed = await self._sync_blocks_from_peers(best_peers, our_height)
                
                # Update sync metrics
                sync_end_time = time.time()
                self.sync_stats["last_sync_time"] = sync_end_time
                self.sync_stats["last_sync_duration"] = sync_end_time - sync_start_time
                self.sync_stats["blocks_processed"] += blocks_processed
                
                logger.info(f"Sync completed, processed {blocks_processed} blocks in {sync_end_time - sync_start_time:.2f} seconds")
                
            except Exception as e:
                logger.error(f"Error during sync: {e}")
                self.sync_stats["sync_failures"] += 1
            finally:
                self.is_syncing = False
    
    async def announce_new_block(self, block_data: Dict[str, Any], exclude_peer: Optional[str] = None):
        """
        Announce a new block to peers (push strategy).
        
        Args:
            block_data: Block data to announce
            exclude_peer: Peer to exclude from announcement (usually the source)
        """
        # Get trusted peers
        trusted_peers = await self.handshake_manager.get_trusted_peers(exclude_peer)
        
        # Announce to each trusted peer
        # TODO: Implement actual HTTP client call to peer nodes
        for peer in trusted_peers:
            try:
                # This would be replaced with actual HTTP client call
                # Example: await http_client.post(f"{peer}/api/blocks", json={"block": block_data, "handshake_token": token})
                
                # For now, just log
                logger.info(f"Would announce block {block_data.get('hash')} to peer {peer}")
                
                # Update known peer heights
                if peer in self.known_peer_heights:
                    block_height = block_data.get("height")
                    if block_height > self.known_peer_heights[peer]:
                        self.known_peer_heights[peer] = block_height
                
                # Record successful announcement
                self.reputation_manager.record_good_behavior(peer, "block_announcement_success")
                
            except Exception as e:
                logger.error(f"Failed to announce block to {peer}: {e}")
                self.reputation_manager.record_violation(peer, "block_announcement_failure")
                
                # Record timeout
                if "timeout" in str(e).lower():
                    self.sync_stats["peer_timeouts"][peer] = self.sync_stats["peer_timeouts"].get(peer, 0) + 1
    
    async def handle_chain_reorganization(self, fork_block_hash: str):
        """
        Handle chain reorganization when a competing fork becomes the main chain.
        
        Args:
            fork_block_hash: The hash of the block where the fork begins
        """
        # This would handle chain reorganization
        # 1. Find common ancestor
        # 2. Roll back transactions from blocks after common ancestor
        # 3. Apply transactions from new fork blocks
        # 4. Update UTXO set
        
        logger.info(f"Chain reorganization initiated at block {fork_block_hash}")
        # Implementation depends on database structure
    
    async def _get_our_height(self) -> int:
        """Get our current blockchain height."""
        if not self.db:
            return -1
        
        # Use the actual Stellaris database interface
        last_block = await self.db.get_last_block()
        return last_block.get('id', -1) if last_block else -1
    
    async def _get_peer_heights(self, peers: List[str]) -> Dict[str, int]:
        """
        Get blockchain heights from multiple peers.
        
        Args:
            peers: List of peer URLs
            
        Returns:
            Dictionary mapping peer URLs to their reported heights
        """
        results = {}
        tasks = []
        
        # Query each peer in parallel
        for peer in peers:
            task = asyncio.create_task(self._get_peer_height(peer))
            tasks.append((peer, task))
        
        # Wait for all tasks to complete
        for peer, task in tasks:
            try:
                height = await asyncio.wait_for(task, timeout=10)
                if height is not None:
                    results[peer] = height
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting height from peer {peer}")
                self.reputation_manager.record_violation(peer, "sync_timeout")
                # Record timeout
                self.sync_stats["peer_timeouts"][peer] = self.sync_stats["peer_timeouts"].get(peer, 0) + 1
            except Exception as e:
                logger.error(f"Error getting height from peer {peer}: {e}")
                self.reputation_manager.record_violation(peer, "sync_error")
        
        return results
    
    async def _get_peer_height(self, peer: str) -> Optional[int]:
        """
        Get blockchain height from a single peer.
        
        Args:
            peer: Peer URL
            
        Returns:
            Reported blockchain height or None on error
        """
        # TODO: Implement actual HTTP client call to peer node
        # This would typically be an async HTTP GET to the peer's status endpoint
        # Example: response = await http_client.get(f"{peer}/api/status")
        
        # For now, simulate with a random height
        # In real implementation, this would use the actual peer's height
        # This is just for demonstration purposes
        
        # Simulate 20% chance of failure
        if random.random() < 0.2:
            return None
            
        # Simulate a height 0-100 blocks ahead of our height
        our_height = await self._get_our_height()
        simulated_height = our_height + random.randint(0, 100)
        
        # In real implementation, we'd parse the height from the response
        return simulated_height
    
    def _select_best_peers(self, peer_heights: Dict[str, int], our_height: int) -> List[str]:
        """
        Select best peers to sync from based on reported heights and reputation.
        
        Args:
            peer_heights: Dictionary mapping peer URLs to their reported heights
            our_height: Our current blockchain height
            
        Returns:
            List of peer URLs to sync from
        """
        candidates = []
        
        # Filter peers with higher height than ours
        for peer, height in peer_heights.items():
            if height > our_height:
                # Calculate "score" based on height advantage and reputation
                height_advantage = height - our_height
                reputation = self.reputation_manager.get_reputation(peer)
                
                # Incorporate timeout history
                timeouts = self.sync_stats["peer_timeouts"].get(peer, 0)
                timeout_penalty = min(timeouts * 10, 50)  # Cap penalty at 50
                
                # Calculate final score
                score = height_advantage + reputation - timeout_penalty
                
                candidates.append((peer, score))
        
        # Sort by score (higher is better)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Take top 3 peers
        return [peer for peer, _ in candidates[:3]]
    
    async def _sync_blocks_from_peers(self, peers: List[str], start_height: int) -> int:
        """
        Sync blocks from selected peers.
        
        Args:
            peers: List of peer URLs to sync from
            start_height: Starting height to sync from
            
        Returns:
            Number of blocks processed
        """
        if not peers:
            return 0
            
        # Initialize counters
        blocks_processed = 0
        current_height = start_height
        
        # Download blocks in batches
        while self.is_running and self.is_syncing:
            # Determine the target height
            # For simplicity, download in batches of 20 blocks
            batch_size = 20
            end_height = current_height + batch_size
            
            # Download batch from peers
            downloaded_blocks = await self._download_blocks_batch(peers, current_height + 1, end_height)
            
            if not downloaded_blocks:
                # No more blocks to download
                logger.info("No more blocks to download, sync complete")
                break
            
            # Process downloaded blocks
            for block in downloaded_blocks:
                # Submit block to processor
                success, message = await self.block_processor.submit_block(block)
                
                if not success:
                    logger.warning(f"Failed to process block at height {block.get('height')}: {message}")
                    # If we encounter a problem, we might be on a fork
                    # For simplicity, we'll just continue with next block
                    # In a real implementation, we might need to handle fork detection
                    continue
                
                blocks_processed += 1
                current_height = max(current_height, block.get("height"))
            
            # Check if we need to continue
            max_peer_height = max(peer_heights.values()) if (peer_heights := self._get_max_peer_heights(peers)) else current_height
            
            if current_height >= max_peer_height:
                logger.info(f"Reached max peer height: {max_peer_height}")
                break
        
        return blocks_processed
    
    async def _download_blocks_batch(self, peers: List[str], start_height: int, end_height: int) -> List[Dict[str, Any]]:
        """
        Download a batch of blocks from peers.
        
        Args:
            peers: List of peer URLs to download from
            start_height: Starting height (inclusive)
            end_height: Ending height (inclusive)
            
        Returns:
            List of downloaded blocks
        """
        # Distribute block downloads among peers
        blocks_per_peer = (end_height - start_height + 1) // len(peers)
        if blocks_per_peer < 1:
            blocks_per_peer = 1
            
        tasks = []
        height = start_height
        
        # Create download tasks
        for peer in peers:
            peer_end_height = min(height + blocks_per_peer - 1, end_height)
            task = asyncio.create_task(self._download_blocks_from_peer(peer, height, peer_end_height))
            tasks.append(task)
            height = peer_end_height + 1
            
            if height > end_height:
                break
        
        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_blocks = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error downloading blocks: {result}")
                continue
                
            all_blocks.extend(result)
        
        # Sort blocks by height
        all_blocks.sort(key=lambda b: b.get("height", 0))
        
        return all_blocks
    
    async def _download_blocks_from_peer(self, peer: str, start_height: int, end_height: int) -> List[Dict[str, Any]]:
        """
        Download blocks from a single peer.
        
        Args:
            peer: Peer URL to download from
            start_height: Starting height (inclusive)
            end_height: Ending height (inclusive)
            
        Returns:
            List of downloaded blocks
        """
        # TODO: Implement actual HTTP client call to peer node
        # This would typically be an async HTTP GET to the peer's blocks endpoint
        # Example: response = await http_client.get(f"{peer}/api/blocks?start_height={start_height}&end_height={end_height}")
        
        # For now, simulate with empty blocks
        # In real implementation, this would use the actual peer's response
        # This is just for demonstration purposes
        
        # Simulate 20% chance of failure
        if random.random() < 0.2:
            logger.warning(f"Simulated failure downloading blocks {start_height}-{end_height} from {peer}")
            return []
            
        # Simulate block download
        # In real implementation, we'd parse the blocks from the response
        simulated_blocks = []
        for height in range(start_height, end_height + 1):
            simulated_block = {
                "hash": f"block_hash_{height}",
                "previous_hash": f"block_hash_{height-1}",
                "height": height,
                "timestamp": int(time.time()) - (end_height - height) * 600,  # Simulate 10-minute blocks
                "transactions": [],
                "difficulty": 1,
                "nonce": 0
            }
            simulated_blocks.append(simulated_block)
        
        return simulated_blocks
    
    def _get_max_peer_heights(self, peers: List[str]) -> Dict[str, int]:
        """
        Get the maximum reported heights for the given peers.
        
        Args:
            peers: List of peer URLs
            
        Returns:
            Dictionary mapping peer URLs to their reported heights
        """
        result = {}
        for peer in peers:
            if peer in self.known_peer_heights:
                result[peer] = self.known_peer_heights[peer]
        return result


# Singleton instance
_chain_synchronizer = None


def get_chain_synchronizer() -> ChainSynchronizer:
    """Get or create the chain synchronizer singleton."""
    global _chain_synchronizer
    if _chain_synchronizer is None:
        _chain_synchronizer = ChainSynchronizer()
    return _chain_synchronizer