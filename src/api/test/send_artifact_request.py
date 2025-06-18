import traceback
import asyncio
from fastapi import Request as FastAPIRequest, HTTPException
from typing import Any, Optional
from lib.VoxaCommunications_Router.net.net_interface import request_factory, send_request
from lib.VoxaCommunications_Router.routing.request import Request
from stores.testartifacts import set_artifact, get_artifact_from_type
from util.logging import log

logger = log()

ENABLE_RESPONSE_MODEL = False # It complains otherwise, used by routes.py

# EXAMPLE REQUEST
"""

"""

# test the request factory
async def handler(request: FastAPIRequest):
    """
    If kytan errors, SSUNode wont run.
    """
    try:
        request_artifact: Request = get_artifact_from_type(Request)
        if request_artifact:
            logger.info(f"Request artifact found: {request_artifact}")
            # or asyncio.run(send_request(request_artifact))
            await send_request(request_artifact)
        else:
            logger.warning("No request artifact found")
            raise HTTPException(status_code=404, detail="Request artifact not found")
    except Exception as e:
        logger.error(f"Error during request send: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))