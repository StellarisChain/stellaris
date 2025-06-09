from pydantic import BaseModel

class RoutingMap(BaseModel):
    """
    Represents a routing map for the Voxa Communications Router.
    This class is used to define the routing structure and rules for communication.
    """
    routes: dict = {} # Will be populated from routing.route