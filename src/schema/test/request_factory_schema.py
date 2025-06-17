from pydantic import BaseModel, validator

# For /test/request_factory/
class RequestFactorySchema(BaseModel):
    target: str
    request_protocol: str
    contents_kwargs: dict

    @validator('request_protocol')
    def validate_protocol(self):
        allowed_protocols = ["http", "tcp"]
        if self.request_protocol not in allowed_protocols:
            raise ValueError(f"Invalid request protocol: {self.request_protocol}. Allowed protocols are {allowed_protocols}.")
        return self.request_protocol