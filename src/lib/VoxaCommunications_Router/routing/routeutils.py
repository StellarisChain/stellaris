from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.cryptography.encryptionutils import encrypt_message, encrypt_message_return_hash
from util.logging import log

logger = log()
def encrypt_routing_chain(request: Request = None) -> dict:
    """Encrypt the routing chain of a request.

    Args:
        request (Request): The request object containing the routing map.

    Returns:
        str: The encrypted routing chain.
    """
    routing_map: RoutingMap = request.routing_map
    if not request or not routing_map:
        logger.error("Request or routing map is not provided.")
        return None

    total_children = routing_map.get_total_children()
    if total_children == 0:
        logger.error("No child routes found in the routing map.")
        return None
    
    encrypted_routing_chain: dict = {} # Diffrence between routing_chain and routing_map is that routing_chain has the data packet at the end

    logger.debug(f"Total children in routing map: {total_children}")
    for n in range(total_children):
        i = total_children - n - 1  # Reverse order
        child_route = routing_map.get_nth_child_route(i)
        logger.debug(f"Processing child route {i}: {child_route["relay_ip"]}")

        if not child_route:
            raise ValueError(f"Child route {i} does not exist in the routing map.")
        
    return encrypted_routing_chain