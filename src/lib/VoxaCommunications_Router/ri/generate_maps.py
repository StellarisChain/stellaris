import random
from typing import Optional
from lib.VoxaCommunications_Router.routing.route import Route
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.util.ri_utils import ri_list

def generate_relay_map() -> RoutingMap:
    """
    Generate a routing map for relays.
    
    This function creates a routing map with random relay routes.
    """
    rri_list = ri_list(path="rri", duplicates=False) # Fetch relay RI list, with no duplicates
    if not rri_list:
        raise ValueError("No relay RIs found. Ensure that relays are registered in the network.")
    
    routing_map = RoutingMap(routes={})
    temp_routing_map: list[Route] = []
    for rri in rri_list:
        route = Route(
            child_route=None,  # No child route for relay routes
            **rri,  # Unpack the RRI data into the Route
        )
        temp_routing_map.append(route)

    # Shuffle the routes to create a psuedo random routing map
    # Todo: Implement a more sophisticated shuffling algorithm if needed
    random.shuffle(temp_routing_map)

    routing_map.routes = temp_routing_map[0].dict()
    def populate_routing_map(previous_route: dict, current_route: Route, index: Optional[int] = -1) -> None:
        index += 1
        previous_route["child_route"] = current_route.dict()
        if index >= len(temp_routing_map) - 1:
            return
        populate_routing_map(previous_route["child_route"], temp_routing_map[index], index)
    populate_routing_map(routing_map.routes, temp_routing_map[1], 1)
    return routing_map