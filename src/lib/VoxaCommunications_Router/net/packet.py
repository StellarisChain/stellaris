from pydantic import BaseModel
from typing import Optional

# Unencrypted plaintext packet structure
class Packet(BaseModel):
    raw_data: Optional[bytes] = None # UTF-8 encoded string data
    str_data: Optional[str] = None
    addr: Optional[tuple[str, int]] = None
    ssu_control_packet: Optional[None] = None

    def raw_to_str(self):
        if self.raw_data:
            self.str_data = self.raw_data.decode('utf-8', errors='ignore')
    
    def str_to_raw(self):
        if self.str_data:
            self.raw_data = self.str_data.encode('utf-8', errors='ignore')
    
    def upgrade_to_ssu_control_packet(self):
        from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, is_ssu_control_request
        if not is_ssu_control_request(self):
            return None
        self.ssu_control_packet = SSUControlPacket(**self.dict())
        return self.ssu_control_packet

    def __str__(self):
        return f"Packet(addr={self.addr}, str_data={self.str_data}, raw_data={self.raw_data})"