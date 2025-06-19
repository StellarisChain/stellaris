import json
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket

INTERNAL_HTTP_PACKET_RESPONSE_HEADER: str = "INTERNAL_HTTP_PACKET_RESPONSE"

class InternalHTTPPacketResponse(SSUPacket):
    """
    Class representing an internal HTTP packet.
    """
    packet_weight: int = 5
    error_code: int = 0
    response_json: dict = {}

    def build_data(self):
        self.str_data = json.dumps({
            "error_code": self.error_code,
            "response_json": self.response_json
        })

    def parse_data(self):
        if not self.str_data:
            return None
        data_without_header = self.str_data.replace(f"{INTERNAL_HTTP_PACKET_RESPONSE_HEADER}", "", 1)
        try:
            data: dict = json.loads(data_without_header)
            self.error_code = data.get("error_code", self.error_code)
            self.response_json = data.get("response_json", self.response_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Internal HTTP Packet data (JSON): {e}")