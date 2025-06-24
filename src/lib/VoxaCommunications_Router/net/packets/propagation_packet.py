from typing import Optional
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket

PROPAGATION_PACKET_HEADER: str = "PROPAGATION_PACKET"

class PropagationPacket(SSUPacket):
    """
    PropagationPacket is a specialized SSUPacket used for propagating data across the network.
    """
    packet_weight: int = 4
    data = None