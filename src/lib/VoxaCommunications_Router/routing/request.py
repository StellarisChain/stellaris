import json
from typing import Union, Optional, Any
from pydantic import BaseModel, validator
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.routing.request_data import RequestData
#from lib.VoxaCommunications_Router.routing.routeutils import routing_chain_next_block
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket

class Request:
    """Request class for handling routing requests in VoxaCommunications-NetNode.

    This class encapsulates the details of a routing request, including the
    route to be processed and any associated data.
    """

    def __init__(self, routing_map: RoutingMap, target: Optional[str] = None, request_data: Optional[RequestData] = None) -> None:
        """Initialize the Request with a route.

        Args:
            route: The route to be processed, can be a Route object or a dictionary.
        """
        self.routing_map: RoutingMap = routing_map  # The routing map containing the route information
        self.request_protocol: str = "ssu" # "ssu" or "i2p" # Protocol to use for the request, i2p is a fallback. Refer to validate_request_protocol
        #self.data: bytes = "placeholder".encode("utf-8") # using a placeholder right now
        self.request_data: RequestData = request_data
        self.target: str = target # Where the request is being sent, ex "example.com" or an IP address
        self.data: bytes = b"" # Placeholder for request data
        if self.request_data:
            self.request_data.target = self.target
            self.data = self.request_data.to_bytes()
        self.routing_chain: dict = {}
    
    @property
    def bytes_data(self) -> bytes:
        """Get the request data as bytes."""
        return self.request_data.to_bytes() if self.request_data else b""
    
    @bytes_data.setter
    def bytes_data(self, request_data: Union[RequestData, bytes]) -> None:
        self.data = request_data.to_bytes() if isinstance(request_data, RequestData) else request_data

    def to_ssu_packet(self) -> SSUPacket:
        """Convert the request to an SSU packet.

        Returns:
            SSUPacket: The SSU packet representation of the request.
        """
        if not self.request_data:
            raise ValueError("Request data is not set.")
        ssu_packet = SSUPacket()
        next_blocks: Union[str, bytes, dict] = self.routing_chain_next_block()
        ssu_packet.str_data = next_blocks
        ssu_packet.addr = (self.routing_chain.get("relay_ip"), self.routing_chain.get("relay_port")) if isinstance(self.routing_chain, dict) else None
        ssu_packet.str_to_raw()

        return ssu_packet
    
    def set_request_data(self, request_data: Union[RequestData, bytes]) -> None:
        """Set the request data for the request.

        Args:
            request_data: The request data to be set, can be a RequestData object or bytes.
        """
        if isinstance(request_data, RequestData):
            self.request_data.target = self.target
            self.request_data = request_data
            self.data = self.request_data.to_bytes()
        elif isinstance(request_data, bytes):
            self.data = request_data
        else:
            raise TypeError("request_data must be of type RequestData or bytes")

    def generate_routing_chain(self) -> dict:
        from lib.VoxaCommunications_Router.routing.routeutils import encrypt_routing_chain # Should not cause an issue with circular imports
        self.routing_chain = encrypt_routing_chain(self)
        if not self.routing_chain:
            raise ValueError("Routing chain could not be generated. Ensure the routing map is properly configured.")
        return self.routing_chain
    
    def routing_chain_from_func(self, func, **kwargs) -> dict:
        """Generate the routing chain using a custom function.

        Args:
            func: A function that takes a Request object and returns a routing chain dictionary.

        Returns:
            dict: The generated routing chain.
        """
        self.routing_chain = func(self, **kwargs)
        if not self.routing_chain:
            raise ValueError("Routing chain could not be generated. Ensure the custom function is properly implemented.")
        return self.routing_chain

    @validator('request_protocol')
    def validate_request_protocol(cls, v):
        allowed_protocols: list[str] = ["ssu", "i2p"]
        if v not in allowed_protocols:
            raise ValueError("request_protocol must be 'ssu' or 'i2p'")
        return v
    
    def to_dict(self) -> dict:
        """Convert the Request object to a dictionary representation."""
        return {
            "request_protocol": self.request_protocol,
            "data": self.data.decode("utf-8") if self.data else None,
            "target": self.target,
            "routing_chain": self.routing_chain
        }
    
    def routing_chain_next_block(self) -> Any:
        """Get the next block in the routing chain.

        Args:
            routing_chain (dict, str): The routing chain to process.

        Returns:
            Any: The next block in the routing chain.
        """
        # Stolen from routeutils.py
        routing_chain = self.routing_chain
        if isinstance(routing_chain, str):
            try:
                routing_chain = json.loads(routing_chain)
            except json.JSONDecodeError as e:
                return None

        if not isinstance(routing_chain, dict):
            return None

        # Check for the next block
        next_block = routing_chain.get("child_route")
        if not next_block:
            return None

        return next_block