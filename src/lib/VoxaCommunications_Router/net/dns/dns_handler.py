from typing import Optional, Union
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
from lib.VoxaCommunications_Router.net.dns.dns_manager import DNSManager
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.dns.dns_packet import DNSPacket, DNS_PACKET_HEADER
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from schema.dns.dns_record import DNSRecord
from schema.dns.a_record import ARecord
from util.logging import log

class DNSHandler:
    def __init__(self) -> None:
        self.net_manager: NetManager = get_global_net_manager()
        self.ssu_node: SSUNode = self.net_manager.ssu_node
        self.dns_manager: DNSManager = self.net_manager.dns_manager
        self.logger = log()

    def setup_hooks(self) -> None:
        """
        Set up hooks for handling DNS packets.
        """
        self.ssu_node.bind_hook(DNS_PACKET_HEADER, self.handle_dns_packet)
        self.logger.info("DNSHandler hooks set up successfully")
    
    async def handle_dns_packet(self, packet: DNSPacket) -> None:
        self.logger.debug(f"Handling DNS packet: {packet}")
        schema: Optional[Union[ARecord, DNSRecord]] = packet.to_schema()