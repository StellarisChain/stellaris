from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field, validator
from lib.VoxaCommunications_Router.routing.typing import RequestContentsHTTP, RequestContentsTCP

# Data that will be passed over the network
class RequestData(BaseModel):
    protocol: str = "http" # Default protocol
    target: str = Field(..., description="Target URL or endpoint")
    contents: Union[RequestContentsHTTP, RequestContentsTCP] = None

    @validator('protocol')
    def validate_protocol(cls, v: str) -> str:
        allowed_protocols: list[str] = ["http", "https", "tcp", "udp"]
        if v not in allowed_protocols:
            raise ValueError(f"Protocol must be one of: {', '.join(allowed_protocols)}")
        return v
    
    def to_bytes(self) -> bytes:
        """Convert the request data to bytes."""
        return str(self.dict()).encode('utf-8')