from typing import Optional, Union
class Route:
    def __init__(self, ip: str, port: int | str, publickey: str):
        self.ip = ip
        self.port = port
        self.publickey = publickey
    
    def to_dict(self, child_route: Optional[dict] = None) -> dict:
        """Convert the route to a dictionary."""
        return {
            "ip": self.ip,
            "port": self.port,
            "publickey": self.publickey,
            "child_route": child_route if child_route else {}
        }