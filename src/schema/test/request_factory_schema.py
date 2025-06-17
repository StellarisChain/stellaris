from pydantic import BaseModel, field_validator

# For /test/request_factory/
class RequestFactorySchema(BaseModel):
    target: str
    request_protocol: str
    contents_kwargs: dict

    @field_validator('request_protocol')
    @classmethod
    def validate_protocol(cls, v):
        allowed_protocols: list[str] = ["http", "tcp"]
        if v not in allowed_protocols:
            raise ValueError(f"Invalid request protocol: {v}. Allowed protocols are {allowed_protocols}.")
        return v