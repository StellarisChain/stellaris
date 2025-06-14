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
    
def get_program_ports() -> list:
    """Retrieve program port configurations from settings.

    Returns:
        list: A list of port numbers found in configuration files.
    """
    json_settings: list[dict] = [
        read_json_from_namespace("config.settings"),
        read_json_from_namespace("config.p2p"),
        read_json_from_namespace("config.kytan")
    ]
    ports = []
    
    def extract_ports_from_dict(data, current_ports):
        """Recursively search for 'port' keys in nested dictionaries."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "port":
                    # Convert to int if it's a string
                    port_val = int(value) if isinstance(value, str) else value
                    if port_val not in current_ports:
                        current_ports.append(port_val)
                elif isinstance(value, dict):
                    extract_ports_from_dict(value, current_ports)
                elif isinstance(value, list):
                    for item in value:
                        extract_ports_from_dict(item, current_ports)
        elif isinstance(data, list):
            for item in data:
                extract_ports_from_dict(item, current_ports)
    
    # Extract ports from each configuration file
    for config in json_settings:
        if config:  # Check if config is not None
            extract_ports_from_dict(config, ports)
    
    return ports
