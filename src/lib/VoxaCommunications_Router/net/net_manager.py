import miniupnpc
import traceback
import asyncio
import os
from libp2p import IHost, new_host
from typing import Optional
from lib.VoxaCommunications_Router.util.net_utils import get_program_ports
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
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
        self.p2p_config: dict = read_json_from_namespace("config.p2p") or {}
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    
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
    
    def serve_ssu_node(self) -> None:
        """Start the SSU node server."""
        if not self.ssu_node:
            self.logger.error("SSU Node not set up. Call setup_ssu_node() first.")
            return
        
        self.loop.create_task(self.ssu_node.serve())
        self.logger.info("SSU Node server started")

global_net_manager: NetManager = None

def get_global_net_manager() -> NetManager:
    return global_net_manager

def set_global_net_manager(net_manager: NetManager) -> None:
    global global_net_manager
    global_net_manager = net_manager