from typing import Optional, Union
from schema.RRISchema import RRISchema

class Route(RRISchema):
    child_route: Optional[dict] | RRISchema | bytes = None
    route_data: Optional[bytes] = None # Data packet, type might change in the future
    encrypted_message_hash: Optional[str] = None # Hash of the encrypted message, used for verification