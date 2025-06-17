from pydantic import BaseModel, validator
from typing import Optional, Union

# ARecord for VoxaCommunications Router DNS requests
class ARecord(BaseModel):
    """Schema for DNS A Record requests"""
    record_type: str = "A"  # Record type. Keep this static.
    domain: str
    ip_address: Optional[str] = None  # Optional IP address, if not provided, will be resolved
    node_id: Optional[str] = None  # Optional node ID for the request
    allowed_protocols: list[str] = ["ssu", "i2p"]  # Allowed protocols for the request
    ttl: Optional[int] = 3600  # Default TTL is 1 hour
    
    @validator('domain')
    def validate_domain(cls, v):
        if not v or len(v) < 3:
            raise ValueError('Domain must be at least 3 characters long')
        if not v.isalnum() and '-' not in v:
            raise ValueError('Domain can only contain alphanumeric characters and hyphens')
        return v
    
    @validator('ip_address')
    def validate_ip_address(cls, v):
        if v is None:
            return v
        parts = v.split('.')
        if len(parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            raise ValueError('Invalid IP address format')
        return v
    
    @validator('node_id')
    def validate_node_id(cls, v):
        if v is not None and (len(v) < 3 or not v.isalnum()):
            raise ValueError('Node ID must be at least 3 characters long and alphanumeric')
        return v
    
    @validator('allowed_protocols')
    def validate_allowed_protocols(cls, v):
        if not isinstance(v, list) or not all(isinstance(item, str) for item in v):
            raise ValueError('allowed_protocols must be a list of strings')
        for protocol in v:
            if protocol not in ["ssu", "i2p"]:
                raise ValueError(f"Invalid protocol: {protocol}. Allowed protocols are 'ssu' and 'i2p'.")
        return v