from typing import Optional, Union
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket, SSU_PACKET_HEADER
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, SSU_CONTROL_HEADER
from lib.VoxaCommunications_Router.net.dns.dns_packet import DNSPacket, DNS_PACKET_HEADER


PACKET_HEADERS: dict[str, Union[Packet, SSUPacket, SSUControlPacket]] = {
    SSU_CONTROL_HEADER: SSUControlPacket,
    SSU_PACKET_HEADER: SSUPacket,
    DNS_PACKET_HEADER: DNSPacket
}

# Configuration keys for SSU Node settings
SSU_NODE_CONFIG_KEYS: list[str] = [
    "host",
    "port",
    "max_ssu_loop_index",
    "connection_timeout"
]

# Default values corresponding to the configuration keys
SSU_NODE_CONFIG_DEFAULT_VALUES: list[str] = [
    "0.0.0.0",
    9999,
    5,
    10
]

def attempt_upgrade(packet: Packet) -> Union[Packet, SSUPacket, SSUControlPacket]:
    """
    Attempt to upgrade a Packet to a more specific type based on its header.
    This function checks the packet's header and returns an instance of the
    appropriate packet type (Packet, SSUPacket, or SSUControlPacket).
    Args:
        packet (Packet): The packet to upgrade
    Returns:
        Union[Packet, SSUPacket, SSUControlPacket]: The upgraded packet instance
    """
    header: str = packet.get_header()
    packet_type: Union[Packet, SSUPacket, SSUControlPacket] = PACKET_HEADERS.get(header, Packet)
    return packet_type(**packet.dict())

def packet_to_header(packet: Packet) -> str:
    """
    Convert a Packet to its header string.
    
    Args:
        packet (Packet): The packet to convert
    Returns:
        str: The header string of the packet
    """
    for header, packet_type in PACKET_HEADERS.items():
        if isinstance(packet, packet_type):
            return header
    return packet.get_header()  # Fallback to the packet's own header if not found