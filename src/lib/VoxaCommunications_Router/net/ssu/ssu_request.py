import uuid
from pydantic import BaseModel
from typing import Optional
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket

class SSURequest(BaseModel):
    payload: Packet | SSUPacket | SSUControlPacket = None # Idealy it should be Packet or SSUPacket. But SSUControlPacket is stil allowed for potential use cases.
    addr: Optional[tuple[str, int]] = None
    request_id: Optional[str] = None
    response: Optional[Packet | SSUPacket | SSUControlPacket] = None

    def is_response(self) -> bool:
        return self.response is not None

    def generate_request_id(self):
        self.request_id = str(uuid.uuid4())
        return self.request_id