from typing import Optional, Union, Dict, Any
from pydantic import BaseModel
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.ssu.ssu_utils import attempt_upgrade

class PropagationData(BaseModel):
    packet_header: Optional[str] = None
    packet: SSUPacket = None
    current_depth: int = 0
    target_depth: int = 2
    target_ri: Optional[str] = "ALL" # RRI, NRI, or ALL

    def load_header(self):
        """
         Load the header for the propagation packet.
        """
        if not self.packet:
            raise ValueError("Packet is not set")
        self.packet_header = self.packet.get_header()
        self.packet.remove_header()

    def upgrade_packet(self) -> None:
        self.packet = attempt_upgrade(self.packet)