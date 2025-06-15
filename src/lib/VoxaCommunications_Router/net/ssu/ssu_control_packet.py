from lib.VoxaCommunications_Router.net.packet import Packet

class SSUControlPacket(Packet):
    """
    Represents an SSU control request packet.

    Inherits from the Packet class and is used to handle SSU control requests.
    """
    pass

def is_ssu_control_request(packet: Packet) -> bool:
    """
    Check if the given packet is an SSU control request.

    An SSU control request is defined as a packet that contains raw data
    starting with the byte sequence b'SSU_CONTROL'.

    Args:
        packet (Packet): The packet to check.

    Returns:
        bool: True if the packet is an SSU control request, False otherwise.
    """
    if packet.raw_data and packet.raw_data.startswith(b'SSU_CONTROL'):
        return True
    return False