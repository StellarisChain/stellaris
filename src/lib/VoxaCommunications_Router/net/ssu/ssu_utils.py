import json
import uuid
from typing import Optional, Union, Dict, List, Any
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket, SSU_PACKET_HEADER
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, SSU_CONTROL_HEADER
from lib.VoxaCommunications_Router.net.dns.dns_packet import DNSPacket, DNS_PACKET_HEADER
from lib.VoxaCommunications_Router.net.packets import InternalHTTPPacket, INTERNAL_HTTP_PACKET_HEADER, InternalHTTPPacketResponse, INTERNAL_HTTP_PACKET_RESPONSE_HEADER, PropagationPacket, PROPAGATION_PACKET_HEADER


# Fragment packet header identifier
SSU_FRAGMENT_HEADER = "SSU_FRAGMENT"

# Maximum UDP packet size (conservative estimate)
MAX_UDP_PACKET_SIZE = 1400  # bytes

# Fragment reassembly timeout (seconds)
FRAGMENT_TIMEOUT = 30

class SSUFragmentPacket(Packet):
    """
    Packet class for handling fragmented SSU packets.
    
    This class represents a fragment of a larger packet that was split
    due to UDP size limitations.
    """
    
    fragment_id: Optional[str] = None
    fragment_index: int = 0
    total_fragments: int = 1
    original_data: Optional[bytes] = None
    
    def create_fragment(self, fragment_id: str, fragment_index: int, total_fragments: int, data: bytes):
        """Create a fragment packet with the given parameters."""
        self.fragment_id = fragment_id
        self.fragment_index = fragment_index
        self.total_fragments = total_fragments
        self.original_data = data
        
        # Create the fragment payload
        fragment_payload: dict[str, Any] = {
            "fragment_id": fragment_id,
            "fragment_index": fragment_index,
            "total_fragments": total_fragments,
            "data": data.hex()  # Convert bytes to hex string for JSON serialization
        }
        
        self.str_data = json.dumps(fragment_payload)
        self.assemble_header(SSU_FRAGMENT_HEADER)
    
    def parse_fragment(self) -> Dict:
        """Parse fragment data from the packet string data."""
        if not self.str_data:
            return None
        
        # Remove header and parse JSON
        data_without_header = self.str_data.replace(f"{SSU_FRAGMENT_HEADER}:", "", 1)
        try:
            fragment_data: dict = json.loads(data_without_header)
            self.fragment_id = fragment_data.get("fragment_id")
            self.fragment_index = fragment_data.get("fragment_index", 0)
            self.total_fragments = fragment_data.get("total_fragments", 1)
            self.original_data = bytes.fromhex(fragment_data.get("data", ""))
            return fragment_data
        except json.JSONDecodeError:
            return None

PACKET_HEADERS: dict[str, Union[Packet, SSUPacket, SSUControlPacket, SSUFragmentPacket, InternalHTTPPacket, InternalHTTPPacketResponse, PropagationPacket]] = {
    SSU_CONTROL_HEADER: SSUControlPacket,
    DNS_PACKET_HEADER: DNSPacket,
    SSU_FRAGMENT_HEADER: SSUFragmentPacket,
    INTERNAL_HTTP_PACKET_HEADER: InternalHTTPPacket,
    INTERNAL_HTTP_PACKET_RESPONSE_HEADER: InternalHTTPPacketResponse,
    PROPAGATION_PACKET_HEADER: PropagationPacket,
    SSU_PACKET_HEADER: SSUPacket # Keep this as the last entry to ensure it is the default
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

def attempt_upgrade(packet: Packet) -> Union[Packet, SSUPacket, SSUControlPacket, InternalHTTPPacket, InternalHTTPPacketResponse, PropagationPacket]:
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
    packet_type: Union[Packet, SSUPacket, SSUControlPacket, InternalHTTPPacket, InternalHTTPPacketResponse, PropagationPacket] = PACKET_HEADERS.get(header, Packet)
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