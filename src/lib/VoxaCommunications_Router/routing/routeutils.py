from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.cryptography.encryptionutils import encrypt_message, encrypt_message_return_hash
from util.logging import log

logger = log()

# TODO: Encrypt the routing data, for now it remains a utf-8 string in binary format.
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
    last_child_index = total_children - 1
    previous_child: dict = None  # To keep track of the previous child route
    for n in range(total_children):
        i = last_child_index - n  # Reverse order
        child_route = routing_map.get_nth_child_route(i)
        next_route = routing_map.get_nth_child_route(i - 1) # Will be None if its the first child route

        # Dont encrypt the first child route.
        do_encrypt = True
        if not next_route:
            do_encrypt = False

        # If its the last child, append the request data to it, there should be some cypher, but for now we just append the data
        if i == last_child_index:
            child_route["route_data"] = request.data
        logger.debug(f"Processing child route {i}: {child_route["relay_ip"]}")

        if not child_route:
            raise ValueError(f"Child route {i} does not exist in the routing map.")
        
        if not previous_child:
            previous_child = child_route
        else:
            if do_encrypt:
                child_route, encrypted_message_hash = encrypt_message_return_hash(
                    message = child_route,
                    public_key = previous_child["public_key"] # I think this is the correct public key to use
                )
            previous_child["child_route"] = child_route
            previous_child["encrypted_message_hash"] = encrypted_message_hash
        
    logger.debug(previous_child)
    return encrypted_routing_chain