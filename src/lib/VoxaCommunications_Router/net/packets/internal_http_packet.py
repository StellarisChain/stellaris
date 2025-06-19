import json
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket

INTERNAL_HTTP_PACKET_HEADER: str = "INTERNAL_HTTP_PACKET"

class InternalHTTPPacket(SSUPacket):
    """
    Class representing an internal HTTP packet.
    """
    packet_weight: int = 5
    endpoint: str = "/status/health"
    method: str = "GET" # or "POST"

    def build_data(self):
        self.str_data = json.dumps({
            "endpoint": self.endpoint,
            "method": self.method
        })
