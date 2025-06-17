from fastapi import Request, HTTPException
from lib.VoxaCommunications_Router.net.net_interface import request_factory
from lib.VoxaCommunications_Router.routing.request import Request
from schema.test.request_factory_schema import RequestFactorySchema
from util.logging import log

logger = log()

# test the request factory
def handler(request: Request, request_factory_schema: RequestFactorySchema):
    """
    Handle a request to create a new request object using the request factory.
    
    Args:
        request: FastAPI request object
    """
    logger.info(f"Processing request factory request for target: {request_factory_schema.target}")
    try:
        # Create the request using the factory
        request_obj: Request = request_factory(
            target=request_factory_schema.target,
            request_protocol=request_factory_schema.request_protocol,
            contents_kwargs=request_factory_schema.contents_kwargs
        )
        
        # Log the created request object
        logger.info(f"Created request object: {request_obj}")
        return {"status": "success", "request": request_obj.to_dict()}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))