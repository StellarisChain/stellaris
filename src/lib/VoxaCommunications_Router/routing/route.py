from typing import Optional, Union
from schema.RRISchema import RRISchema

class Route(RRISchema):
    encrypted_message_hash: Optional[str] = None # Hash of the encrypted message, used for verification
    encrypted_fernet: Optional[str] = None # Encrypted Fernet key, used for decryption
    child_route: Optional[dict] | RRISchema | bytes = None
    route_data: Optional[bytes] = None # Data packet, type might change in the future