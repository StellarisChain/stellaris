import ipaddress
from util.jsonreader import read_json_from_namespace

def validate_ip_address(ip_address: str) -> bool:
    """Validate if the provided string is a valid IPv4 or IPv6 address.

    Args:
        ip_address (str): The IP address to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False

def validate_subnet(subnet: str) -> bool:
    """Validate if the provided string is a valid subnet in CIDR notation.

    Args:
        subnet (str): The subnet to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        ipaddress.ip_network(subnet, strict=False)
        return True
    except ValueError:
        return False
    
def get_program_ports() -> dict:
    """Retrieve program port configurations from settings.

    Returns:
        dict: A dictionary with port configurations.
    """
    settings = read_json_from_namespace("config.settings")
    p2p_settings = read_json_from_namespace("config.p2p")
    kytan_settings = read_json_from_namespace("config.kytan")