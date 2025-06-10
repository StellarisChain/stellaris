from typing import Union, Optional
from lib.VoxaCommunications_Router.routing.route import Route

class Request:
    """Request class for handling routing requests in VoxaCommunications-NetNode.

    This class encapsulates the details of a routing request, including the
    route to be processed and any associated data.
    """

    def __init__(self, route: Union[Route, dict], target: Optional[str] = None) -> None:
        """Initialize the Request with a route.

        Args:
            route: The route to be processed, can be a Route object or a dictionary.
        """
        self.route: Route = Route(**route) if isinstance(route, dict) else route
        self.data: dict = {} # May have to be changed in the future
        self.target: str = target # Where the request is being sent, ex "example.com" or an IP address