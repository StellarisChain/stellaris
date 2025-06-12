import random
import concurrent.futures
from typing import Optional
from lib.VoxaCommunications_Router.routing.route import Route
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.util.ri_utils import ri_list

def _create_route(rri: dict) -> Route:
    """
    Helper function to create a single Route object from RRI data.
    This function is designed to be used with ThreadPoolExecutor.
    """
    return Route(
        child_route=None,  # No child route for relay routes
        **rri,  # Unpack the RRI data into the Route
    )

def generate_relay_map(max_workers: Optional[int] = None, max_map_size: Optional[int] = 50, ri_list_extra_size: Optional[int] = 20) -> RoutingMap:
    """
    Generate a routing map for relays using multi-threading.
    
    This function creates a routing map with random relay routes.
    Uses concurrent processing for route creation and iterative approach
    to avoid maximum recursion depth issues.
    
    Args:
        max_workers: Maximum number of worker threads. If None, defaults to min(32, (os.cpu_count() or 1) + 4)
        max_map_size: Maximum number of routes to include in the routing map. Defaults to 50.
        ri_list_extra_size: Extra size to fetch from the relay RI list. Defaults to 20.
    """
    rri_list_data = ri_list(path="rri", duplicates=False, limit=max_map_size+ri_list_extra_size) # Fetch relay RI list, with no duplicates
    if not rri_list_data:
        raise ValueError("No relay RIs found. Ensure that relays are registered in the network.")
    
    routing_map = RoutingMap(routes={})
    
    # Use ThreadPoolExecutor to create Route objects concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all route creation tasks
        future_to_rri = {executor.submit(_create_route, rri): rri for rri in rri_list_data}
        
        # Collect results as they complete
        temp_routing_map: list[Route] = []
        for future in concurrent.futures.as_completed(future_to_rri):
            try:
                route = future.result()
                temp_routing_map.append(route)
            except Exception as exc:
                rri = future_to_rri[future]
                print(f'Route creation failed for RRI {rri}: {exc}')
                # Continue processing other routes even if one fails

    if not temp_routing_map:
        raise ValueError("Failed to create any routes from the available RRI data.")

    # Shuffle the routes to create a pseudo random routing map
    # Todo: Implement a more sophisticated shuffling algorithm if needed
    random.shuffle(temp_routing_map)

    # Limit the number of routes to max_map_size
    temp_routing_map = temp_routing_map[:max_map_size]

    # Convert first route to dict and set as root
    routing_map.routes = temp_routing_map[0].dict()
    
    # Use iterative approach instead of recursion to avoid maximum recursion depth
    current_route = routing_map.routes
    for i in range(1, len(temp_routing_map)):
        current_route["child_route"] = temp_routing_map[i].dict()
        current_route = current_route["child_route"]
    
    return routing_map