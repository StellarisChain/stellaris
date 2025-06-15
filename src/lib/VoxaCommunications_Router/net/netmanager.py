import miniupnpc
from libp2p import IHost, new_host
from lib.VoxaCommunications_Router.util.net_utils import get_program_ports
from util.logging import log

class NetManager:
    def __init__(self):
        self.program_ports = get_program_ports()
        self.logger = log()
        self.upnp_setup = False
        self.libp2p_setup = False
        self.libp2phost: IHost = None
    
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
        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            num_devices = upnp.discover()
            if num_devices == 0:
                self.logger.warning("No UPnP devices found")
                return
            
            upnp.selectigd()
            self.upnp_setup = True
            return
            #external_ip = upnp.externalipaddress()
            #print(f"External IP Address: {external_ip}")
        except Exception as e:
            self.logger.error(f"UPnP setup failed: {e}")
            self.upnp_setup = False
    
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