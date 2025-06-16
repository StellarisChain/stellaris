from typing import Optional
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.packet import Packet

SSU_CONTROL_HEADER: str = "SSU_CONTROL"

class SSUControlPacket(SSUPacket):
    """
    Represents an SSU control request packet.

    Inherits from the Packet class and is used to handle SSU control requests.
    str_data example: "SSU_CONTROL COMMAND PARAMS" params are comma-separated key=value pairs and are optional
    """
    ssu_control_command: Optional[str] = "unknown" # Options: "STATUS", "PUNCH", etc.
    ssu_control_params: Optional[dict] = None

    def parse_ssu_control(self):
        """
        Parse the SSU control command and parameters from the str_data.

        The str_data is expected to be in the format:
        "SSU_CONTROL COMMAND PARAMS"
        where PARAMS are optional and are comma-separated key=value pairs.

        Example:
            str_data = "SSU_CONTROL RESTART delay=5,force=true"
            This will set:
                ssu_control_command = "RESTART"
                ssu_control_params = {"delay": "5", "force": "true"}
        """
        if not self.str_data:
            return
        
        parts: list[str] = self.str_data.split(' ', 2)
        if len(parts) < 2 or parts[0] != SSU_CONTROL_HEADER:
            return
        
        self.ssu_control_command = parts[1]
        
        if len(parts) == 3:
            params_str = parts[2]
            params = {}
            for param in params_str.split(','):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.strip()] = value.strip()
            self.ssu_control_params = params

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
    if packet.raw_data and packet.raw_data.startswith(bytes(SSU_CONTROL_HEADER, 'utf-8')):
        return True
    if packet.str_data and packet.str_data.startswith(SSU_CONTROL_HEADER):
        return True
    return False