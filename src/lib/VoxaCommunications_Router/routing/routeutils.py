import json
import base64
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from copy import deepcopy
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.cryptography.encryptionutils import encrypt_message, encrypt_message_return_hash, encrypt_route_message
from util.logging import log
from util.jsonutils import serialize_for_json, serialize_dict_for_json
from modern_benchmark import benchmark

"""
Developer Note:
Take a deep breath, this is a complex and anoying function to write.
This function is responsible for encrypting the routing chain of a request.

Some thoughts:
When sending, each node/relay only forwards the part that it decrypts, to precent the sender's ip from being exposed.
Then each node/relay sends the data back to the previous node/relay, which then forwards it to the next one.
You can also only decrypt it one block at a time.
"""

logger = log()

# TODO: Encrypt the routing data, for now it remains a utf-8 string in binary format.
# TODO: Make this more efficent, over 20 in a request results in a lot of data to encrypt which can take hours
@benchmark(name="routing.encrypt_chain", slow_threshold_ms=10000)
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
    
    # Create new routing map for encrypted routes
    new_routing_map: RoutingMap = deepcopy(routing_map)
    new_routing_map.routes = serialize_dict_for_json(new_routing_map.routes)

    logger.info(f"Total children in routing map: {total_children}")
    last_child_index = total_children - 1 # Start from zero index
    for n in range(total_children):
        i = last_child_index - n # Reverse order
        child_route: dict | bytes = new_routing_map.get_nth_child_route(i)
        # When going backwards, i - 1 is the next route in the chain
        next_route: dict | bytes = new_routing_map.get_nth_child_route(i - 1)

        logger.debug(f"Processing child route: {i}")
        do_encrypt: bool = True

        # If it's the first (last_child_index = 1) or last (i = 0) we don't encrypt
        # TODO: encrypt the last one as well        
        if last_child_index == i:
            do_encrypt = False
            child_route["route_data"] = serialize_for_json(request.data)
            new_routing_map.set_nth_child_route(i, child_route)

        if not next_route:
            do_encrypt = False
            logger.debug(f"No next route found for child route {i}, skipping encryption.")
            if isinstance(child_route, dict):
                logger.debug(f"Child route id: {child_route.get("relay_id", "N/A")}")

        if do_encrypt:
            # Ensure next_route is a dict before accessing public_key
            if isinstance(next_route, dict) and 'public_key' in next_route:
                encrypted_child_route, encrypted_message_hash, encrypted_fernet = encrypt_route_message(
                    message = child_route,
                    public_key = next_route['public_key'] # Encrypt from the next route's public key, which would appear before this on the route map
                )
                child_route = serialize_for_json(encrypted_child_route)
            else:
                logger.error(f"Next route is not a valid dict or missing public_key for route {i}")
                do_encrypt = False
        
        new_routing_map.set_nth_child_route(i, child_route)

    logger.info(f"Final routing reached")
    return new_routing_map.routes


@benchmark(name="routing.encrypt_chain_threaded", slow_threshold_ms=5000)
def encrypt_routing_chain_threaded(request: Request = None, max_workers: int = 4) -> dict:
    """Multi-threaded variant of encrypt_routing_chain for better performance.

    Args:
        request (Request): The request object containing the routing map.
        max_workers (int): Maximum number of worker threads to use.

    Returns:
        dict: The encrypted routing chain.
    """
    routing_map: RoutingMap = request.routing_map
    if not request or not routing_map:
        logger.error("Request or routing map is not provided.")
        return None

    total_children = routing_map.get_total_children()
    if total_children == 0:
        logger.error("No child routes found in the routing map.")
        return None
    
    # Create new routing map for encrypted routes
    new_routing_map: RoutingMap = deepcopy(routing_map)
    new_routing_map.routes = serialize_dict_for_json(new_routing_map.routes)

    logger.info(f"Total children in routing map: {total_children}")
    last_child_index = total_children - 1

    # Thread-safe lock for accessing routing map
    map_lock = Lock()
    
    # Store encryption tasks and their dependencies
    encryption_tasks = []
    completed_routes = set()
    
    def encrypt_route_task(route_index: int) -> tuple[int, dict | bytes]:
        """Encrypt a single route in a thread-safe manner."""
        try:
            with map_lock:
                child_route = new_routing_map.get_nth_child_route(route_index)
                next_route = new_routing_map.get_nth_child_route(route_index - 1)
            
            logger.debug(f"Processing child route: {route_index}")
            do_encrypt = True

            # Handle the last route (highest index) - add route_data
            if last_child_index == route_index:
                do_encrypt = False
                if isinstance(child_route, dict):
                    child_route["route_data"] = serialize_for_json(request.data)

            # Check if next route exists
            if not next_route:
                do_encrypt = False
                logger.debug(f"No next route found for child route {route_index}, skipping encryption.")
                if isinstance(child_route, dict):
                    logger.debug(f"Child route id: {child_route.get('relay_id', 'N/A')}")

            # Perform encryption if needed
            if do_encrypt:
                if isinstance(next_route, dict) and 'public_key' in next_route:
                    encrypted_child_route, encrypted_message_hash, encrypted_fernet = encrypt_route_message(
                        message=child_route,
                        public_key=next_route['public_key']
                    )
                    child_route = serialize_for_json(encrypted_child_route)
                else:
                    logger.error(f"Next route is not a valid dict or missing public_key for route {route_index}")
                    do_encrypt = False

            return route_index, child_route
            
        except Exception as e:
            logger.error(f"Error encrypting route {route_index}: {str(e)}")
            return route_index, None

    # Process routes in reverse order, but group independent routes for parallel processing
    # Routes that don't depend on encryption results can be processed in parallel
    processed_indices = set()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all routes for processing
        # Note: The encryption dependencies are handled within each task
        future_to_index = {}
        
        for n in range(total_children):
            route_index = last_child_index - n  # Reverse order
            future = executor.submit(encrypt_route_task, route_index)
            future_to_index[future] = route_index
        
        # Process completed tasks and update routing map
        for future in as_completed(future_to_index):
            route_index = future_to_index[future]
            try:
                index, encrypted_route = future.result()
                if encrypted_route is not None:
                    with map_lock:
                        new_routing_map.set_nth_child_route(index, encrypted_route)
                    processed_indices.add(index)
                    logger.debug(f"Successfully processed route {index}")
                else:
                    logger.error(f"Failed to encrypt route {index}")
            except Exception as e:
                logger.error(f"Error processing route {route_index}: {str(e)}")

    # Verify all routes were processed
    if len(processed_indices) != total_children:
        logger.warning(f"Not all routes were processed. Expected: {total_children}, Processed: {len(processed_indices)}")

    logger.info(f"Multi-threaded routing encryption completed")
    return new_routing_map.routes


@benchmark(name="routing.encrypt_chain_batched", slow_threshold_ms=3000)
def encrypt_routing_chain_sequential_batched(request: Request = None, batch_size: int = 5) -> dict:
    """Sequential batched variant that processes routes in dependency-aware batches.
    
    This approach maintains encryption order dependencies while still providing
    some parallelization within independent batches.

    Args:
        request (Request): The request object containing the routing map.
        batch_size (int): Number of routes to process in each batch.

    Returns:
        dict: The encrypted routing chain.
    """
    routing_map: RoutingMap = request.routing_map
    if not request or not routing_map:
        logger.error("Request or routing map is not provided.")
        return None

    total_children = routing_map.get_total_children()
    if total_children == 0:
        logger.error("No child routes found in the routing map.")
        return None
    
    # Create new routing map for encrypted routes
    new_routing_map: RoutingMap = deepcopy(routing_map)
    new_routing_map.routes = serialize_dict_for_json(new_routing_map.routes)

    logger.info(f"Total children in routing map: {total_children}")
    last_child_index = total_children - 1

    # Process in batches, maintaining dependency order
    for batch_start in range(0, total_children, batch_size):
        batch_end = min(batch_start + batch_size, total_children)
        batch_indices = []
        
        # Collect indices for this batch (in reverse order)
        for n in range(batch_start, batch_end):
            route_index = last_child_index - n
            batch_indices.append(route_index)
        
        logger.debug(f"Processing batch: indices {batch_indices}")
        
        # Process each route in the batch sequentially to maintain dependencies
        for route_index in batch_indices:
            child_route = new_routing_map.get_nth_child_route(route_index)
            next_route = new_routing_map.get_nth_child_route(route_index - 1)

            logger.debug(f"Processing child route: {route_index}")
            do_encrypt = True

            # Handle the last route
            if last_child_index == route_index:
                do_encrypt = False
                if isinstance(child_route, dict):
                    child_route["route_data"] = serialize_for_json(request.data)
                new_routing_map.set_nth_child_route(route_index, child_route)

            if not next_route:
                do_encrypt = False
                logger.debug(f"No next route found for child route {route_index}, skipping encryption.")
                if isinstance(child_route, dict):
                    logger.debug(f"Child route id: {child_route.get('relay_id', 'N/A')}")

            if do_encrypt:
                if isinstance(next_route, dict) and 'public_key' in next_route:
                    try:
                        encrypted_child_route, encrypted_message_hash, encrypted_fernet = encrypt_route_message(
                            message=child_route,
                            public_key=next_route['public_key']
                        )
                        child_route = serialize_for_json(encrypted_child_route)
                    except Exception as e:
                        logger.error(f"Encryption failed for route {route_index}: {str(e)}")
                        do_encrypt = False
                else:
                    logger.error(f"Next route is not a valid dict or missing public_key for route {route_index}")
                    do_encrypt = False
            
            new_routing_map.set_nth_child_route(route_index, child_route)
        
        logger.debug(f"Completed batch with indices {batch_indices}")

    logger.info(f"Sequential batched routing encryption completed")
    return new_routing_map.routes