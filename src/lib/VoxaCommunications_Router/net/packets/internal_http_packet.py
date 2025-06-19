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
    params: dict = {}
    post_data: dict = {}

    def build_data(self):
        self.str_data = json.dumps({
            "endpoint": self.endpoint,
            "method": self.method,
            "params": self.params,
            "post_data": self.post_data
        })

    def parse_data(self):
        if not self.str_data:
            return None
        data_without_header = self.str_data.replace(f"{INTERNAL_HTTP_PACKET_HEADER}", "", 1)
        try:
            data: dict = json.loads(data_without_header)
            self.endpoint = data.get("endpoint", self.endpoint)
            self.method = data.get("method", self.method)
            self.params = data.get("params", self.params)
            self.post_data = data.get("post_data", self.post_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Internal HTTP Packet data: {e}")