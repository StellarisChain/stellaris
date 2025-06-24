import importlib
import asyncio
import os
import inspect
from typing import Any, Optional, Type, Union
from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
from lib.VoxaCommunications_Router.net.packets import PropagationPacket, PROPAGATION_PACKET_HEADER
from lib.VoxaCommunications_Router.net.packets.propagation_data import PropagationData
from lib.VoxaCommunications_Router.net.ssu.ssu_request import SSURequest
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from util.logging import log

class PropagationHandler:
    def __init__(self) -> None:
        self.logger = log()
        self.net_manager: NetManager = get_global_net_manager()
        self.ssu_node: SSUNode = self.net_manager.ssu_node
    
    def setup_hooks(self) -> None:
        """
        Set up hooks for handling propagation packets.
        """
        self.ssu_node.bind_hook(PROPAGATION_PACKET_HEADER, self.handle_propagation_packet)
        self.logger.info("PropagationHandler hooks set up successfully")

    async def handle_propagation_packet(self, packet: PropagationPacket) -> None:
        """
        Handle incoming propagation packets.
        """
        self.logger.debug(f"Handling propagation packet: {packet}")
        
        # Ensure the packet is valid and has the correct data
        if not packet.data:
            self.logger.error("PropagationPacket has no data")
            return
        
        # Process the propagation data
        try:
            packet_data = packet.parse_data()
            self.logger.info(f"Processed propagation data: {packet_data}")
            packet_data.upgrade_packet()
            self.logger.debug(f"Packet Data: {packet_data.packet}")

        except Exception as e:
            self.logger.error(f"Failed to process propagation packet: {e}")
            return
        
    def send_ssu_packet(self, packet: SSUPacket, depth: Optional[int] = 2) -> None:
        """
        Send a SSUPacket through the SSU node.
        """
        if not isinstance(packet, SSUPacket):
            self.logger.error("Invalid packet type for SSU")
            return
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        propagation_data = PropagationData(packet=packet, current_depth=depth)
        propagation_packet = PropagationPacket(data=propagation_data)

        try:
            # Run the async task and wait for it to complete
            loop.run_until_complete(self.send_propagation_packet(propagation_packet))
            self.logger.debug("SendSSUPacket completed")
        except Exception as e:
            self.logger.error(f"Error sending SSUPacket: {e}")
            raise
        
    async def send_propagation_packet(self, packet: PropagationPacket) -> None:
        """
        Send a propagation packet to the network.
        """
        if not isinstance(packet, PropagationPacket):
            self.logger.error("Invalid packet type for propagation")
            return
        
        # Build the packet data
        packet.build_data()
        packet.str_to_raw()

        if not packet.has_header(PROPAGATION_PACKET_HEADER):
            packet.assemble_header(PROPAGATION_PACKET_HEADER)
        
        ssu_request: SSURequest = packet.upgrade_to_ssu_request(generate_request_id=True)
        
        # Send the packet through the SSU node
        self.logger.debug(f"Sending propagation request: {ssu_request.request_id}")
        await self.ssu_node.send_ssu_request(ssu_request)
        self.logger.info(f"Sent propagation packet: {packet}")