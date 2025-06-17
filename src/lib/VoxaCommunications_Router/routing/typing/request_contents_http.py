from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, validator
import json

class RequestContentsHTTP(BaseModel):
    # Core HTTP request components
    method: str = Field(default="GET", description="HTTP method")
    
    # Request headers
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    
    # Request body/payload
    body: Optional[str] = Field(default=None, description="Request body content")
    
    # Authentication
    auth: Optional[Dict[str, str]] = Field(default=None, description="Authentication credentials")
    
    # Request metadata
    timeout: Optional[float] = Field(default=30.0, description="Request timeout in seconds")
    follow_redirects: bool = Field(default=True, description="Whether to follow redirects")

    @validator('method')
    def validate_method(cls, v: str) -> str:
        allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        v_upper = v.upper()
        if v_upper not in allowed_methods:
            raise ValueError(f"Method must be one of: {', '.join(allowed_methods)}")
        return v_upper
    
    @validator('timeout')
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Timeout must be positive")
        return v
    
    def to_bytes(self) -> bytes:
        """Convert the request data to bytes."""
        return json.dumps(self.dict(), default=str).encode('utf-8')
    
    def add_header(self, key: str, value: str) -> None:
        """Add a header to the request."""
        self.headers[key] = value
    
    def set_json_body(self, data: Dict[str, Any]) -> None:
        """Set the request body as JSON and add appropriate content-type header."""
        self.body = json.dumps(data)
        self.add_header("Content-Type", "application/json")
    