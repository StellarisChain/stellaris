from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
from schema.BaseRISchema import BaseRISchema
import re

class NRISchema(BaseModel):
    """Schema for Node Routing Information (NRI) requests"""
    
    node_id: str
    node_ip: str
    node_port: int
    node_type: str = "standard"
    capabilities: List[str] = []
    # routing_table: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = {}
    
    @validator('node_id')
    def validate_node_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError('Node ID must be at least 3 characters long')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Node ID can only contain alphanumeric characters, underscores, and hyphens')
        return v
    
    @validator('node_ip')
    def validate_node_ip(cls, v):
        # Basic IP validation
        if not re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', v):
            raise ValueError('Invalid IP address format')
        return v
    
    @validator('node_port')
    def validate_node_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('node_type')
    def validate_node_type(cls, v):
        allowed_types = ['standard', 'relay', 'gateway', 'bridge']
        if v not in allowed_types:
            raise ValueError(f'Node type must be one of: {", ".join(allowed_types)}')
        return v