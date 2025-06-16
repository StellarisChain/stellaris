from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field, validator
import json

class RequestContentsTCP(BaseModel):
    # TCP-specific options
    protocol: str = Field(default="tcp", description="Protocol type")
    
    # Data payload
    data: Optional[Union[str, bytes]] = Field(default=None, description="Data to send over TCP")
    
    # Connection options
    timeout: Optional[float] = Field(default=30.0, description="Connection timeout in seconds")
    keep_alive: bool = Field(default=False, description="Whether to keep connection alive")
    buffer_size: int = Field(default=4096, description="Buffer size for data transmission")
    
    # Encoding options
    encoding: str = Field(default="utf-8", description="Text encoding for string data")
    
    # Authentication/Security
    auth: Optional[Dict[str, str]] = Field(default=None, description="Authentication credentials")
    
    # Connection metadata
    connection_id: Optional[str] = Field(default=None, description="Optional connection identifier")

    @validator('protocol')
    def validate_protocol(cls, v: str) -> str:
        allowed_protocols: list[str] = ["tcp", "udp"]
        if v.lower() not in allowed_protocols:
            raise ValueError(f"Protocol must be one of: {', '.join(allowed_protocols)}")
        return v.lower()
    
    @validator('timeout')
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Timeout must be positive")
        return v
    
    @validator('buffer_size')
    def validate_buffer_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Buffer size must be positive")
        return v
    
    def to_bytes(self) -> bytes:
        """Convert the request data to bytes."""
        if isinstance(self.data, bytes):
            return self.data
        elif isinstance(self.data, str):
            return self.data.encode(self.encoding)
        else:
            # Convert entire request to JSON if no specific data
            return json.dumps(self.dict(), default=str).encode(self.encoding)
    
    def set_data(self, data: Union[str, bytes, Dict[str, Any]]) -> None:
        """Set the data payload."""
        if isinstance(data, dict):
            self.data = json.dumps(data)
        else:
            self.data = data