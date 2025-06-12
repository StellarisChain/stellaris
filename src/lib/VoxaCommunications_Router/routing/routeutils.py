import json
import base64
from copy import deepcopy
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.cryptography.encryptionutils import encrypt_message, encrypt_message_return_hash, encrypt_route_message
from util.logging import log
from util.jsonutils import serialize_for_json, serialize_dict_for_json

"""
Developer Note:
Take a deep breath, this is a complex and anoying function to write.
This function is responsible for encrypting the routing chain of a request.
"""

logger = log()

# TODO: Encrypt the routing data, for now it remains a utf-8 string in binary format.
# TODO: Make this more efficent, over 20 in a request results in a lot of data to encrypt which can take hours
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
    
    new_routing_map: RoutingMap = deepcopy(routing_map)
    new_routing_map.routes = serialize_dict_for_json(new_routing_map.routes)

    logger.info(f"Total children in routing map: {total_children}")
    last_child_index = total_children - 1
    for n in range(total_children):
        i = last_child_index - n  # Reverse order
        child_route: dict | bytes = new_routing_map.get_nth_child_route(i)
        next_route: dict | bytes = new_routing_map.get_nth_child_route(i - 1) # Will be None if its the first child route      

        logger.debug(f"Processing child route: {i}")
        do_encrypt: bool = True

        # If it's the first (last_child_index = 1) or last (i = 0) we don't encrypt
        # TODO: encrypt the last one as well
        if last_child_index == i or not next_route:
            do_encrypt = False
        
        if last_child_index == i:
            child_route["route_data"] = serialize_for_json(request.data)
            new_routing_map.set_nth_child_route(i, child_route)

        if do_encrypt:
            # logger.debug(child_route)
            encrypted_child_route, encrypted_message_hash, encrypted_fernet = encrypt_route_message(
                message = child_route,
                public_key = next_route['public_key'] # Encrypt from the next route's public key, which would appear before this on the route map
            )
            child_route = serialize_for_json(encrypted_child_route)
        
        new_routing_map.set_nth_child_route(i, child_route)

    logger.info(f"Final routing reached")
    return new_routing_map.routes