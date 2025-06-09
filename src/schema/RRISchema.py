from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
from schema.BaseRISchema import BaseRISchema
import re

class RRISchema(BaseModel):
    """Schema for Relay Routing Information (RRI) requests"""
    
    relay_id: str
    relay_ip: str
    relay_port: int
    relay_type: str = "standard"
    supported_protocols: List[str] = []
    routing_info: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = {}
    public_key: Optional[str] = None
    public_key_hash: Optional[str] = None
    fernet_key: Optional[str] = None
    fernet_key_hash: Optional[str] = None
    program_version: Optional[str] = None
    
    @validator('relay_id')
    def validate_relay_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError('Relay ID must be at least 3 characters long')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Relay ID can only contain alphanumeric characters, underscores, and hyphens')
        return v
    
    @validator('relay_ip')
    def validate_relay_ip(cls, v):
        # Basic IP validation
        if not re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', v):
            raise ValueError('Invalid IP address format')
        return v
    
    @validator('relay_port')
    def validate_relay_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('relay_type')
    def validate_relay_type(cls, v):
        allowed_types = ['standard', 'high_capacity', 'secure', 'bridge']
        if v not in allowed_types:
            raise ValueError(f'Relay type must be one of: {", ".join(allowed_types)}')
        return v