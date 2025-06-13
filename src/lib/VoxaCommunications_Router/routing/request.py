from typing import Union, Optional
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap

class Request:
    """Request class for handling routing requests in VoxaCommunications-NetNode.

    This class encapsulates the details of a routing request, including the
    route to be processed and any associated data.
    """

    def __init__(self, routing_map: RoutingMap, target: Optional[str] = None) -> None:
        """Initialize the Request with a route.

        Args:
            route: The route to be processed, can be a Route object or a dictionary.
        """
        self.routing_map: RoutingMap = routing_map  # The routing map containing the route information
        self.request_protocol: str = "tcp" # https, "udp", "http", etc. Default is TCP
        self.data: bytes = "placeholder".encode("utf-8") # using a placeholder right now
        self.target: str = target # Where the request is being sent, ex "example.com" or an IP address
        self.routing_chain: dict = {}

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