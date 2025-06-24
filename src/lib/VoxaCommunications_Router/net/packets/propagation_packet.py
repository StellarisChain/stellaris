import json
from typing import Optional
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.packets.propagation_data import PropagationData

PROPAGATION_PACKET_HEADER: str = "PROPAGATION_PACKET"

class PropagationPacket(SSUPacket):
    """
    PropagationPacket is a specialized SSUPacket used for propagating data across the network.
    """
    packet_weight: int = 4
    data: PropagationData = None

    def build_data(self):
        """
        Build the packet data from the PropagationData instance.
        """
        if not self.data:
            raise ValueError("PropagationData is not set")
        self.str_data = self.data.json()
        self.assemble_header(PROPAGATION_PACKET_HEADER)
        self.str_to_raw()

    def parse_data(self) -> PropagationData:
        """
        Parse the packet data into a PropagationData instance.
        """
        if not self.str_data:
            self.raw_to_str()
        if not self.has_header(PROPAGATION_PACKET_HEADER):
            raise ValueError("Packet does not have the correct header")
        
        self.remove_header()
        data_without_header = self.str_data.replace(f"{PROPAGATION_PACKET_HEADER} ", "", 1)
        dict_data = json.loads(data_without_header)
        try:
            self.data = PropagationData(**dict_data)
            return self.data
        except Exception as e:
            raise ValueError(f"Failed to parse PropagationPacket data: {e}")