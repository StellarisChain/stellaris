from typing import Optional, Union
from lib.VoxaCommunications_Router.ri.generate_maps import generate_relay_map
from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.dns.dns_packet import DNSPacket
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.packets import InternalHTTPPacket
from lib.VoxaCommunications_Router.net.ssu.ssu_request import SSURequest
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.request_data import RequestData
from lib.VoxaCommunications_Router.routing.typing import RequestContentsHTTP, RequestContentsTCP
from lib.VoxaCommunications_Router.routing.routeutils import encrypt_routing_chain_threaded, encrypt_routing_chain_sequential_batched, routing_chain_next_block
from util.logging import log
from util.jsonutils import base_model_from_keys

logger = log()

"""
The interface module to the VoxaCommunications Network.

TODO: This should probably be a class that manages state and configuration for network interactions.
"""

ROUTING_CHAIN_METHOD_DEFAULT: str = "threaded"

def request_factory(target: str, request_protocol: str = "http", contents_kwargs: dict = {}) -> Request:
    request_contents: Union[RequestContentsHTTP, RequestContentsTCP] = None
    match request_protocol:
        case "http":
            request_contents = RequestContentsHTTP(**contents_kwargs) or RequestContentsHTTP(**base_model_from_keys(RequestContentsHTTP, contents_kwargs)[1])
        case "tcp":
            request_contents = RequestContentsTCP(**base_model_from_keys(RequestContentsTCP, contents_kwargs)[1])
        case _:
            raise ValueError(f"Unknown request protocol: {request_protocol}. Supported protocols are 'http' and 'tcp'.")
    request_data: RequestData = RequestData(
        target=target,
        request_protocol=request_protocol,
        request_contents=request_contents
    )
    relay_map: RoutingMap = generate_relay_map(max_map_size=20)  # Default relay map generation
    request: Request = Request(request_data=request_data, routing_map=relay_map, target=target)
    request.generate_routing_chain()
    return request

# in development
async def send_request(request: Request, timeout: Optional[int] = 30):
    """
    Send a request through the VoxaCommunications Network.
    
    Args:
        request (Request): The request object to be sent.
    
    Returns:
        Response: The response object received from the network.
    """
    logger.info(f"Sending request with end target: {request.target} via protocol: {request.request_protocol}")
    
    if not request.routing_chain:
        request.routing_chain = generate_encrypted_routing_chain(request)
    
    net_manager: NetManager = get_global_net_manager()
    match request.request_protocol:
        case "ssu":
            ssu_node: SSUNode = net_manager.ssu_node
            if not ssu_node or not ssu_node.running:
                raise RuntimeError(f"SSU Node is not running. Cannot send SSU request. {ssu_node}:{ssu_node.running}")
            ssu_packet: SSUPacket = request.to_ssu_packet()
            ssu_request: SSURequest = ssu_packet.upgrade_to_ssu_request(generate_request_id=True)
            response: SSURequest = await ssu_node.send_ssu_request_and_wait(ssu_request, timeout=timeout)
            if (response is not None) and response.is_response():
                response_packet: Union[SSUPacket, Packet, DNSPacket] = response.response
            pass
        case "i2p":
            pass

def generate_encrypted_routing_chain(request: Request, routing_map: Optional[RoutingMap] = None, method: Optional[str] = ROUTING_CHAIN_METHOD_DEFAULT, max_map_size: Optional[int] = 20) -> dict:
    """
    Generate an encrypted routing chain for the given request using the specified method.
    
    Args:
        request (Request): The request object to generate the routing chain for.
        routing_map (Optional[RoutingMap]): The routing map to use for generating the routing chain. If None, a default map will be used.
        method (Optional[str]): The method to use for generating the routing chain. Options are "threaded" or "sequential_batched". Defaults to "threaded".
        batch_size (Optional[int]): The batch size to use when method is "sequential_batched". Defaults to 10.
    
    Returns:
        Request: The updated request object with the encrypted routing chain.
    """
    if routing_map:
        request.routing_map = routing_map
    elif not request.routing_map:
        # If no routing map is provided, and the request has no routing map, generate a default one
        request.routing_map = generate_relay_map(max_map_size=max_map_size)
    routing_chain: dict = {}
    match method:
        case "default":
            routing_chain = request.generate_routing_chain()
        case "threaded":
            routing_chain = request.routing_chain_from_func(encrypt_routing_chain_threaded)
        case "batched":
            routing_chain = request.routing_chain_from_func(encrypt_routing_chain_sequential_batched)
        case _:
            logger.warning(f"Unknown routing chain generation method: {method}, defaulting to 'threaded'")
            routing_chain = request.routing_chain_from_func(encrypt_routing_chain_threaded)
    
    return routing_chain