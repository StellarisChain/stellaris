import asyncio
import socket
from typing import Optional, Union
from copy import deepcopy
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket, SSU_PACKET_HEADER
from lib.VoxaCommunications_Router.net.ssu.ssu_request import SSURequest
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket, SSU_CONTROL_HEADER
from lib.VoxaCommunications_Router.net.dns.dns_packet import DNSPacket, DNS_PACKET_HEADER
from util.logging import log
from util.jsonutils import json_from_keys, lists_to_dict
from util.jsonreader import read_json_from_namespace
from util.wrappers import deprecated

PACKET_HEADERS: dict[str, Union[Packet, SSUPacket, SSUControlPacket]] = {
    SSU_CONTROL_HEADER: SSUControlPacket,
    SSU_PACKET_HEADER: SSUPacket,
    DNS_PACKET_HEADER: DNSPacket
}

# Configuration keys for SSU Node settings
SSU_NODE_CONFIG_KEYS: list[str] = [
    "host",
    "port",
    "max_ssu_loop_index",
    "connection_timeout"
]

# Default values corresponding to the configuration keys
SSU_NODE_CONFIG_DEFAULT_VALUES: list[str] = [
    "0.0.0.0",
    9999,
    5,
    10
]

def attempt_upgrade(packet: Packet) -> Union[Packet, SSUPacket, SSUControlPacket]:
    """
    Attempt to upgrade a Packet to a more specific type based on its header.
    This function checks the packet's header and returns an instance of the
    appropriate packet type (Packet, SSUPacket, or SSUControlPacket).
    Args:
        packet (Packet): The packet to upgrade
    Returns:
        Union[Packet, SSUPacket, SSUControlPacket]: The upgraded packet instance
    """
    header: str = packet.get_header()
    packet_type: Union[Packet, SSUPacket, SSUControlPacket] = PACKET_HEADERS.get(header, Packet)
    return packet_type(**packet.dict())

def packet_to_header(packet: Packet) -> str:
    """
    Convert a Packet to its header string.
    
    Args:
        packet (Packet): The packet to convert
    Returns:
        str: The header string of the packet
    """
    for header, packet_type in PACKET_HEADERS.items():
        if isinstance(packet, packet_type):
            return header
    return packet.get_header()  # Fallback to the packet's own header if not found

class SSUNode:
    """
    SSU (Secure Semireliable UDP) Node implementation for peer-to-peer communication.
    
    This class provides a UDP-based networking node that handles SSU packets,
    control packets, and manages peer connections. It supports NAT traversal
    through UDP hole punching and maintains request/response tracking.
    
    Attributes:
        config (dict): Configuration dictionary containing host, port, timeouts, etc.
        logger: Logger instance for debugging and monitoring
        sock (socket.socket): UDP socket for network communication
        loop (asyncio.AbstractEventLoop): Event loop for async operations
        running (bool): Flag indicating if the node is currently running
        host (str): IP address the node binds to
        port (int): Port number the node listens on
        peers (list): List of connected peer addresses
        request_pool (dict): Active requests awaiting responses
        request_returns (dict): Completed requests with their responses
    """
    
    def __init__(self, config: Optional[dict] = read_json_from_namespace("config.p2p")):
        """
        Initialize the SSU Node with configuration.
        
        Args:
            config (Optional[dict]): Configuration dictionary. If None, defaults are used.
        """
        # Load configuration with defaults fallback
        self.config: dict = json_from_keys(SSU_NODE_CONFIG_KEYS, config) or lists_to_dict(SSU_NODE_CONFIG_KEYS, SSU_NODE_CONFIG_DEFAULT_VALUES)
        self.logger = log()
        
        # Network components
        self.sock: socket.socket = None
        self.loop: asyncio.AbstractEventLoop = None
        self.running = False
        
        # Server configuration
        self.host: str = self.config.get("host")
        self.port: str | int = self.config.get("port")
        
        # Peer management
        self.peers: list = []  # List of all peer connections

        # Request / Response management
        self.request_pool: dict[str, SSURequest] = {}  # Active requests by ID
        self.request_returns: dict[str, SSURequest] = {}  # Completed requests by ID
        self.packet_hooks: dict[str, callable] = {}  # Hooks for packet processing [packet_header]
        
        # Ensure port is an integer
        if isinstance(self.port, str):
            self.port = int(self.port)
    
    async def serve(self):
        """
        Start the SSU Node server and begin listening for incoming connections.
        
        This method initializes the UDP socket, binds to the configured host/port,
        and starts the UDP packet handling loop.
        """
        self.running = True
        
        # Create and bind UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.logger.info(f"SSU Node listening on {self.host}:{self.port}")

        # Start the UDP handling task
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.loop.create_task(self.handle_udp())
    
    async def stop(self):
        """
        Stop the SSU Node server and clean up resources.
        
        This method sets the running flag to False, closes the socket,
        and performs cleanup operations.
        """
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        self.logger.info("SSU Node stopped")
        await asyncio.sleep(0.1)  # Allow cleanup time
    
    async def handle_udp(self):
        """
        Main UDP packet handling loop.
        
        This method continuously listens for incoming UDP packets, processes them
        based on their type (control packets vs regular SSU packets), and manages
        the request/response lifecycle for peer communications.
        """
        if not self.sock:
            self.logger.error("Socket not initialized")
            return
        
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Receive incoming UDP packet
                raw_data, addr = await self.loop.run_in_executor(None, self.sock.recvfrom, 4096)
                self.peers.append(addr)  # Track peer address
                self.logger.info(f"Received {len(raw_data)} bytes from {addr}")
                
                # Parse as SSU packet
                packet: Packet | SSUPacket | SSUControlPacket = SSUPacket(raw_data=raw_data, addr=addr)
                packet.raw_to_str()
                
                # Try to upgrade to control packet
                ssu_control_packet: SSUControlPacket = packet.upgrade_to_ssu_control_packet()
                
                # Handle control packets (STATUS, PUNCH, etc.)
                if ssu_control_packet:
                    ssu_control_packet.parse_ssu_control()
                    self.logger.info(f"Received SSU Control Packet")
                    
                    match ssu_control_packet.ssu_control_command:
                        case "STATUS":
                            # Handle status inquiry packets
                            self.logger.info(f"Received STATUS command with params: {ssu_control_packet.ssu_control_params}")
                            pass
                            
                        case "PUNCH":
                            # Handle NAT traversal punch packets
                            self.logger.info(f"Received PUNCH command with params: {ssu_control_packet.ssu_control_params}")
                            
                            index: int = int(ssu_control_packet.ssu_control_params.get("index", "0"))
                            max_index: int = int(self.config.get("max_ssu_loop_index"))

                            # Limit punch packet exchanges to prevent infinite loops
                            if index >= max_index:
                                self.logger.info(f"Max PUNCH index {max_index} reached, not sending response")
                                continue
                            else:
                                # Send punch response with incremented index
                                response = SSUControlPacket(
                                    addr=addr,
                                    ssu_control_command="PUNCH",
                                    ssu_control_params={
                                        "index": int(ssu_control_packet.ssu_control_params.get("index", "0")) + 1,
                                    }
                                )
                                response.assemble_ssu_control()
                                response.str_to_raw()
                                self.sock.sendto(response.raw_data, addr)
                                self.logger.info(f"Sent PUNCH response to {addr}")
                                
                        case _:
                            self.logger.warning(f"Unknown SSU control command: {ssu_control_packet.ssu_control_command}")
                else:
                    # Handle regular SSU packets
                    self.logger.info(f"Received SSU Packet: {packet}")
                    
                    # Check if this packet is a response to any pending request
                    for request_id, request in list(self.request_pool.items()):
                        if request.addr == addr:
                            self.logger.info(f"Packet matches request_id {request_id}, processing response")
                            # Create a copy of the request with the response attached
                            request_copy: SSURequest = deepcopy(request)
                            request_copy.response = packet
                            # Move from active pool to completed returns
                            self.request_returns[request_id] = request_copy
                            del self.request_pool[request_id]
                            break

                    for header, hook in self.packet_hooks.items():
                        if packet.get_header() == header:
                            try:
                                packet: Union[Packet, SSUPacket, SSUControlPacket] = attempt_upgrade(packet)
                                self.logger.info(f"Executing packet hook for header {header}")
                                self.loop.create_task(hook(packet))
                            except Exception as e:
                                self.logger.error(f"Error executing packet hook for {header}: {e}")

            except Exception as e:
                self.logger.error(f"Error receiving data: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    def bind_hook(self, packet_header: str, hook: callable):
        """
        Bind a custom processing hook to a specific packet header.
        
        Args:
            packet_header (str): The header to bind the hook to
            hook (callable): The function to call when a packet with this header is received
        """
        if not callable(hook):
            raise ValueError("Hook must be a callable function")
        
        self.packet_hooks[packet_header] = hook
        self.logger.info(f"Hook bound for packet header: {packet_header}")

    @deprecated("Use send_ssu_request instead")
    async def send_packet(self, packet: Packet | SSUPacket | SSUControlPacket):
        """
        Send a packet directly without request tracking (deprecated).
        
        Args:
            packet: The packet to send (Packet, SSUPacket, or SSUControlPacket)
            
        Note:
            This method is deprecated. Use send_ssu_request instead for better
            request/response tracking and error handling.
        """
        if not self.sock:
            self.logger.error("Socket not initialized")
            return
        
        # Ensure packet has raw data
        if not packet.raw_data:
            packet.str_to_raw()
        
        if not packet.raw_data:
            self.logger.error("Packet has no raw data to send")
            return
        
        if not packet.addr:
            self.logger.error("Packet has no address to send to")
            return
        
        self.sock.sendto(packet.raw_data, packet.addr)
        self.logger.info(f"Sent {len(packet.raw_data)} bytes to {packet.addr}")

    async def send_ssu_request(self, request: SSURequest) -> None | str:
        """
        Send an SSU request and add it to the request pool for response tracking.
        
        Args:
            request (SSURequest): The SSU request to send
            
        Returns:
            str | None: The request ID if successful, None if failed
        """
        if not self.sock:
            self.logger.error("Socket not initialized")
            return
        
        if not request.payload:
            self.logger.error("Request has no payload to send")
            return
        
        # Ensure the request has a header
        # TODO: This should be handled in the SSURequest constructor
        has_header: bool = request.payload.has_header()
        if not has_header:
            request.payload.assemble_header(packet_to_header(request.payload))
            
        # Ensure payload is in raw format for transmission
        request.payload.str_to_raw()
        
        # Add our request to the pool
        self.request_pool[request.request_id] = request
        self.sock.sendto(request.payload.raw_data, request.addr)
        self.logger.info(f"Sent {len(request.payload.raw_data)} bytes to {request.addr} with request_id {request.request_id}")
        return request.request_id

    async def send_ssu_request_and_wait(self, request: SSURequest, timeout: Optional[int] = None) -> Optional[SSURequest]:
        """
        Send an SSU request and wait for a response with timeout.
        
        This method sends a request and blocks until either a response is received
        or the timeout period expires. It handles cleanup of timed-out requests.
        
        Args:
            request (SSURequest): The SSU request to send
            timeout (Optional[int]): Timeout in seconds. Uses config default if None.
            
        Returns:
            Optional[SSURequest]: The completed request with response, or None if timeout/error
        """
        # Use configured timeout if none provided
        if timeout is None:
            timeout = int(self.config.get("connection_timeout", 10))
        
        # Send the request
        request_id: str | None = await self.send_ssu_request(request)
        if not request_id:
            return None
        
        self.logger.info(f"Waiting for response to request_id {request_id} with timeout {timeout}s")
        start_time: float = asyncio.get_event_loop().time()
        
        # Wait for response or timeout
        while True:
            # Check if response has arrived
            if request_id in self.request_returns:
                response: SSURequest = self.request_returns[request_id]
                del self.request_returns[request_id]
                self.logger.info(f"Received response for request_id {request_id}")
                return response
            
            # Check for timeout
            if (asyncio.get_event_loop().time() - start_time) > timeout:
                self.logger.warning(f"Timeout waiting for response to request_id {request_id}")
                # Clean up timed-out request
                if request_id in self.request_pool:
                    del self.request_pool[request_id]
                return None
            
            # Brief sleep to prevent busy waiting
            await asyncio.sleep(0.01)