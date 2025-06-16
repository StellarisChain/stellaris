from typing import Optional
from lib.VoxaCommunications_Router.net.packet import Packet

class SSUPacket(Packet):
    ssu_control_packet: Optional[None] = None
    
    def upgrade_to_ssu_control_packet(self):
        from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, is_ssu_control_request
        if not is_ssu_control_request(self):
            return None
        self.ssu_control_packet = SSUControlPacket(**self.dict())
        return self.ssu_control_packet