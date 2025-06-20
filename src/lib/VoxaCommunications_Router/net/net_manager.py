import miniupnpc
import traceback
import asyncio
import httpx  # Replace requests with httpx for async support
import os
import random
from stun import get_ip_info, STUN_SERVERS
from libp2p import IHost, new_host
from typing import Optional, Any
from lib.VoxaCommunications_Router.util.net_utils import get_program_ports
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.packets import InternalHTTPPacket, INTERNAL_HTTP_PACKET_HEADER, InternalHTTPPacketResponse, INTERNAL_HTTP_PACKET_RESPONSE_HEADER
from lib.VoxaCommunications_Router.net.dns.dns_manager import DNSManager, set_global_dns_manager
from util.logging import log
from util.envutils import detect_container
from util.jsonreader import read_json_from_namespace

class NetManager:
    def __init__(self):
        self.program_ports = get_program_ports()
        self.logger = log()
        self.upnp_setup = False
        self.libp2p_setup = False
        self.libp2phost: IHost = None
        self.is_container = detect_container()
        self.ssu_node: SSUNode = None
        self.dns_manager: DNSManager = None
        self.p2p_config: dict = read_json_from_namespace("config.p2p") or {}
        self.settings: dict = read_json_from_namespace("config.settings") or {}
        self.server_settings: dict = self.settings.get("server-settings", {})
        self.features: dict = self.settings.get("features", {})
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.stun_servers: list[str] = self.p2p_config.get("stun_servers", list(STUN_SERVERS))
        if not self.stun_servers or len(self.stun_servers) == 0:
            self.logger.warning("No STUN servers configured, using default list")
            self.stun_servers = list(STUN_SERVERS)
        self.ip_info: tuple[str, Any, Any] = get_ip_info(stun_host=random.choice(self.stun_servers)) # Probably not the best way to do this, but it works for now
        self.nat_type: Optional[str] = self.ip_info[0] if self.ip_info else None
        self.logger.warning(f"Detected NAT type: {self.nat_type}")
        # Create a reusable HTTP client for internal requests
        self._http_client: Optional[httpx.AsyncClient] = None

    # Takes UDP packets and sends them to legacy HTTP endpoints
    def setup_internal_http(self) -> None:
        """Set up the internal HTTP packet handler."""
        self.logger.info("Setting up Internal HTTP Packet handler")
        self.ssu_node.bind_hook(INTERNAL_HTTP_PACKET_HEADER, self.handle_internal_http_packet)
        self.logger.info("Internal HTTP Packet handler set up successfully")

    async def handle_internal_http_packet(self, packet: InternalHTTPPacket) -> InternalHTTPPacketResponse:
        """Handle incoming internal HTTP packets."""
        packet.parse_data()
        
        # Use HTTP instead of HTTPS and add timeout
        port = self.server_settings.get('port', 9999)
        endpoint = f"http://127.0.0.1:{port}{packet.endpoint}"
        
        self.logger.info(f"Handling Internal HTTP Packet, for endpoint: {endpoint}")
        
        # Create HTTP client if it doesn't exist
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),  # 30 second timeout
                verify=False,  # Skip SSL verification for localhost
                follow_redirects=True
            )
        
        try:
            response: httpx.Response = None
            
            match packet.method.upper():
                case "GET":
                    response = await self._http_client.get(endpoint, params=packet.params)
                case "POST":
                    # Use json parameter for JSON data, data for form data
                    if packet.post_data:
                        response = await self._http_client.post(endpoint, json=packet.post_data)
                    else:
                        response = await self._http_client.post(endpoint)
                case _:
                    self.logger.warning(f"Unsupported HTTP method: {packet.method}")
                    # Return error response for unsupported methods
                    response_packet = InternalHTTPPacketResponse()
                    response_packet.error_code = 405  # Method Not Allowed
                    response_packet.response_json = {"error": f"Method {packet.method} not supported"}
                    response_packet.build_data()
                    response_packet.assemble_header(INTERNAL_HTTP_PACKET_RESPONSE_HEADER)
                    response_packet.str_to_raw()
                    return response_packet
            
            self.logger.info(f"Received response with status: {response.status_code}")
            
            # Generate response packet
            response_packet = InternalHTTPPacketResponse()
            response_packet.error_code = response.status_code
            
            # Handle JSON response safely
            try:
                response_packet.response_json = response.json()
            except Exception as json_error:
                self.logger.warning(f"Failed to parse JSON response: {json_error}")
                # Fallback to text response
                response_packet.response_json = {"response_text": response.text}
            
            response_packet.build_data()
            response_packet.assemble_header(INTERNAL_HTTP_PACKET_RESPONSE_HEADER)
            response_packet.str_to_raw()
            
            return response_packet
            
        except httpx.TimeoutException:
            self.logger.error(f"Request timeout for endpoint: {endpoint}")
            response_packet = InternalHTTPPacketResponse()
            response_packet.error_code = 408  # Request Timeout
            response_packet.response_json = {"error": "Request timeout"}
            response_packet.build_data()
            response_packet.assemble_header(INTERNAL_HTTP_PACKET_RESPONSE_HEADER)
            response_packet.str_to_raw()
            return response_packet
            
        except httpx.ConnectError:
            self.logger.error(f"Connection error for endpoint: {endpoint}")
            response_packet = InternalHTTPPacketResponse()
            response_packet.error_code = 503  # Service Unavailable
            response_packet.response_json = {"error": "Connection failed"}
            response_packet.build_data()
            response_packet.assemble_header(INTERNAL_HTTP_PACKET_RESPONSE_HEADER)
            response_packet.str_to_raw()
            return response_packet
            
        except Exception as e:
            self.logger.error(f"Unexpected error handling internal HTTP packet: {e}")
            response_packet = InternalHTTPPacketResponse()
            response_packet.error_code = 500  # Internal Server Error
            response_packet.response_json = {"error": f"Internal error: {str(e)}"}
            response_packet.build_data()
            response_packet.assemble_header(INTERNAL_HTTP_PACKET_RESPONSE_HEADER)
            response_packet.str_to_raw()
            return response_packet

    async def cleanup(self):
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def setup_libp2p(self) -> None:
        """Set up the P2P host."""
        try:
            self.libp2phost = await new_host()
            self.libp2p_setup = True
            self.logger.info("P2P host set up successfully")
        except Exception as e:
            self.logger.error(f"Failed to set up P2P host: {e}")
            self.libp2p_setup = False
        
    def setup_upnp(self) -> None:
        """Set up UPnP port forwarding for the program ports."""
        if self.is_container:
            self.logger.warning("Running in container - UPnP may not be available. Consider using host networking mode.")
            
        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            
            try:
                num_devices = upnp.discover()
            except Exception as e:
                # miniupnpc sometimes throws "Success" exception even when it works
                if str(e) == "Success":
                    num_devices = 1  # Assume at least one device found
                    self.logger.info("UPnP discovery succeeded (caught 'Success' exception)")
                else:
                    raise e
            
            if num_devices == 0:
                self.logger.warning("No UPnP devices found - this is expected in containers")
                self._handle_upnp_fallback()
                return
            
            upnp.selectigd()
            self.upnp_setup = True
            self.logger.info("UPnP setup completed successfully")
            return
            #external_ip = upnp.externalipaddress()
            #print(f"External IP Address: {external_ip}")
        except Exception as e:
            if self.is_container:
                self.logger.info(f"UPnP unavailable in container (expected): {e}")
                self._handle_upnp_fallback()
            else:
                self.logger.error(f"UPnP setup failed: {e}")
                traceback.print_exc()
            self.upnp_setup = False
    
    def _handle_upnp_fallback(self) -> None:
        """Handle fallback when UPnP is not available."""
        self.logger.info("UPnP not available - running in manual port forwarding mode")
        self.logger.info(f"Please manually forward these ports on your router: {self.program_ports}")
        if self.is_container:
            self.logger.info("Container detected. To enable UPnP, run with: docker run --network=host ...")
    
    def add_port_mappings(self) -> None:
        """Add port mappings for the program ports."""
        if not self.upnp_setup:
            self.logger.warning("UPnP not set up. Call setup_upnp() first.")
            return
        
        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            upnp.selectigd()
            
            for port in self.program_ports:
                try:
                    upnp.addportmapping(port, 'TCP', upnp.lanaddr, port, 'VoxaCommunications-NetNode', '')
                    self.logger.info(f"Port {port} mapped successfully")
                except Exception as e:
                    self.logger.error(f"Failed to map port {port}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to add port mappings: {e}")
    
    def setup_ssu_node(self) -> None:
        """Initialize the SSU (Secure Semireliable UDP) node."""
        self.logger.info("Setting up SSU Node")
        self.ssu_node = SSUNode(config=self.p2p_config)
    
    def serve_ssu_node(self) -> asyncio.Task:
        """Start the SSU node server."""
        if not self.ssu_node:
            self.logger.error("SSU Node not set up. Call setup_ssu_node() first.")
            return None
        
        self.logger.info("Starting SSU Node server...")
        
        # Create task in the existing event loop instead of blocking
        task = self.loop.create_task(self.ssu_node.serve())
        
        # Add a callback to log when the task actually starts
        def on_task_done(task_result: asyncio.Task) -> None:
            if task_result.exception():
                self.logger.error(f"SSU Node server task failed: {task_result.exception()}")
            else:
                self.logger.info("SSU Node server task completed")
        
        task.add_done_callback(on_task_done)
        self.logger.info("SSU Node server task created and scheduled")
        
        return task

    def setup_dns_manager(self) -> None:
        """Initialize the DNS manager."""
        self.logger.info("Setting up DNS Manager")
        self.dns_manager = DNSManager()
        set_global_dns_manager(self.dns_manager)

global_net_manager: NetManager = None

def get_global_net_manager() -> NetManager:
    return global_net_manager

def set_global_net_manager(net_manager: NetManager) -> None:
    global global_net_manager
    global_net_manager = net_manager