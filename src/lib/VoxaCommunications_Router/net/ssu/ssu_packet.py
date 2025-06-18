from typing import Optional
from lib.VoxaCommunications_Router.net.packet import Packet

SSU_PACKET_HEADER: str = "SSU_PACKET"

class SSUPacket(Packet):
    ssu_control_packet: Optional[None] = None
    
    def upgrade_to_ssu_control_packet(self):
        from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, is_ssu_control_request
        if not is_ssu_control_request(self):
            return None
        self.ssu_control_packet = SSUControlPacket(**self.dict())
        return self.ssu_control_packet
    
    def upgrade_to_ssu_request(self, generate_request_id: Optional[bool] = True):
        from lib.VoxaCommunications_Router.net.ssu.ssu_request import SSURequest
        ssu_request = SSURequest(payload=self)
        self.correct_addr() # Ensure the address is set correctly
        ssu_request.addr = self.addr
        if generate_request_id:
            ssu_request.generate_request_id()
        return ssu_request