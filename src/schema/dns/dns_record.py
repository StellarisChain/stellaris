from pydantic import BaseModel

class DNSRecord(BaseModel):
    record_type: str = "UNSET"  # Default record type, should be overridden by subclasses