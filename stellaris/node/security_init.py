"""
security_init.py - Security services initialization for Stellaris

This module provides functions to initialize and manage all security-related
services used by the Stellaris node system.
"""

import asyncio
import logging
from typing import Optional

# Import security components
from stellaris.node.peer_reputation import get_reputation_manager
from stellaris.node.handshake_challenge import get_challenge_manager
from stellaris.node.security_monitor import get_security_monitor
from stellaris.node.handshake_handler import get_handshake_manager

# Conditionally import components that might not be available yet
try:
    from stellaris.node.transaction_processor import get_transaction_processor
except ImportError:
    get_transaction_processor = None
    
try:
    from stellaris.node.block_processor import get_block_processor
except ImportError:
    get_block_processor = None
    
try:
    from stellaris.node.chain_sync import get_chain_synchronizer
except ImportError:
    get_chain_synchronizer = None

# Setup logging
logger = logging.getLogger("stellaris.node.security_init")


async def initialize_security_services(db=None):
    """
    Initialize all security services.
    
    This function should be called during application startup to ensure
    all security services are properly initialized and their background
    tasks are started.
    
    Args:
        db: Optional database connection to set for services
    """
    services = {}
    
    # Initialize core security components
    reputation_manager = get_reputation_manager()
    challenge_manager = get_challenge_manager()
    security_monitor = get_security_monitor()
    handshake_manager = get_handshake_manager()
    
    services['reputation_manager'] = reputation_manager
    services['challenge_manager'] = challenge_manager
    services['security_monitor'] = security_monitor
    services['handshake_manager'] = handshake_manager
    
    # Set database connections if provided
    if db:
        if hasattr(reputation_manager, 'set_db'):
            reputation_manager.set_db(db)
        if hasattr(challenge_manager, 'set_db'):
            challenge_manager.set_db(db)
        if hasattr(handshake_manager, 'set_db'):
            handshake_manager.set_db(db)
    
    # Start background tasks for core services
    await reputation_manager.start()
    await challenge_manager.start()
    await security_monitor.start()
    
    # Initialize additional services if available
    if get_transaction_processor:
        transaction_processor = get_transaction_processor()
        services['transaction_processor'] = transaction_processor
        if db and hasattr(transaction_processor, 'set_db'):
            transaction_processor.set_db(db)
    
    if get_block_processor:
        block_processor = get_block_processor()
        services['block_processor'] = block_processor
        if db and hasattr(block_processor, 'set_db'):
            block_processor.set_db(db)
    
    if get_chain_synchronizer:
        chain_sync = get_chain_synchronizer()
        services['chain_sync'] = chain_sync
        if db and hasattr(chain_sync, 'set_db'):
            chain_sync.set_db(db)
    
    logger.info("Security services initialized")
    return services


async def shutdown_security_services():
    """
    Properly shutdown all security services.
    
    This function should be called during application shutdown to ensure
    all background tasks are properly cancelled and resources are released.
    """
    # Get instances
    reputation_manager = get_reputation_manager()
    challenge_manager = get_challenge_manager()
    security_monitor = get_security_monitor()
    
    # Stop background tasks
    await reputation_manager.stop()
    await challenge_manager.stop()
    await security_monitor.stop()
    
    print("Security services stopped")