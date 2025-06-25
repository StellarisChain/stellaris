import importlib
import asyncio
import os
import inspect
from copy import deepcopy
from typing import Any, Optional, Type, Union
from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
from lib.VoxaCommunications_Router.net.packets import PropagationPacket, PROPAGATION_PACKET_HEADER
from lib.VoxaCommunications_Router.net.packets.propagation_data import PropagationData
from lib.VoxaCommunications_Router.net.ssu.ssu_request import SSURequest
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.util.ri_utils import ri_list
from util.logging import log

class PropagationHandler:
    def __init__(self) -> None:
        self.logger = log()
        self.net_manager: NetManager = get_global_net_manager()
        self.ssu_node: SSUNode = self.net_manager.ssu_node
        self.setup_hooks()
    
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
            propagate = True # Forward the packet to all the listed NRI or RRI nodes
            packet_data = packet.parse_data()
            self.logger.info(f"Processed propagation data: {packet_data}")
            packet_data.upgrade_packet()
            packet_data.current_depth += 1
            self.logger.debug(f"Packet Data (DEPTH: {packet_data.current_depth}): {packet_data.packet}")
            if packet_data.current_depth >= packet_data.target_depth:
                self.logger.warning(f"Packet exceeded target depth: {packet_data.current_depth}")
                propagate = False
            
            target_ri: str = packet_data.target_ri

            if not target_ri in ["ALL", "NRI", "RRI"]:
                self.logger.error(f"Invalid target RI: {target_ri}")
                propagate = False

            if propagate:
                propagation_packet: PropagationPacket = PropagationPacket(data=packet_data)
                propagation_packet.build_data()
                propagation_packet.str_to_raw()

                if not propagation_packet.has_header(PROPAGATION_PACKET_HEADER):
                    propagation_packet.assemble_header(PROPAGATION_PACKET_HEADER)

                target_ri = target_ri.lower()
                # TODO: Can someone refine this
                def get_addrs_from_ri(ri_type: str) -> list[str]:
                    ri_name: str = "node" if ri_type == "nri" else "relay"
                    ri_data: list = ri_list(ri_name=ri_type)
                    output_data: list[str] = []
                    for ri in ri_data:
                        ri: dict = dict(ri)
                        addr = f"{ri.get(ri_name+'_ip')}:{ri.get(ri_name+'_port')}"
                        output_data.append(addr)
                    return output_data

                target_list: list[str] = []
                if target_ri.capitalize() != "ALL":
                    target_ri = target_ri.lower()
                    target_list = get_addrs_from_ri(target_ri)
                else:
                    target_list = get_addrs_from_ri("nri") + get_addrs_from_ri("rri")

                for target_addr in target_list:
                    self.logger.debug(f"Sending propagation packet to target: {target_addr}")
                    propagation_packet_clone = deepcopy(propagation_packet)
                    propagation_packet_clone.addr = target_addr

                    self.send_propagation_packet(propagation_packet_clone)

        except Exception as e:
            self.logger.error(f"Failed to process propagation packet: {e}")
            return

    def send_ssu_packet(self, packet: SSUPacket, depth: Optional[int] = 2, target_ri: Optional[str] = "all") -> None:
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

        propagation_data = PropagationData(packet=packet, current_depth=depth, target_ri=target_ri)
        propagation_packet = PropagationPacket(data=propagation_data, addr=packet.addr)

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

global_propagation_handler: Optional[PropagationHandler] = None

def get_global_propagation_handler() -> PropagationHandler:
    """
    Get the global instance of PropagationHandler.
    """
    return global_propagation_handler

def set_global_propagation_handler(handler: PropagationHandler) -> None:
    """
    Set the global instance of PropagationHandler.
    """
    global global_propagation_handler
    if not isinstance(handler, PropagationHandler):
        raise TypeError("Handler must be an instance of PropagationHandler")
    global_propagation_handler = handler
    global_propagation_handler.logger.info("Global PropagationHandler set successfully")
