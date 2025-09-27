"""
Routes package for Stellaris node API endpoints.

This package contains all the API routes for the Stellaris node.
"""

from fastapi import APIRouter

# Import all route modules
from stellaris.node.routes.handshake import router as handshake_router
from stellaris.node.routes.transactions import router as transactions_router
from stellaris.node.routes.blocks import router as blocks_router
from stellaris.node.routes.status import router as status_router

# Create main router
api_router = APIRouter()

# Include all routers
api_router.include_router(handshake_router, tags=["handshake"])
api_router.include_router(transactions_router, tags=["transactions"])
api_router.include_router(blocks_router, tags=["blocks"])
api_router.include_router(status_router, tags=["status"])