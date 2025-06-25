"""
USING P2PD AT THE MOMENT
In the future, we should have our own P2P implementation
"""

from p2pd import (
    list_interfaces,
    load_interfaces,
    P2PNode,
    P2P_DIRECT,
    P2P_RELAY,
    P2P_PUNCH,
    P2P_REVERSE,
    EXT_BIND,
    NIC_BIND,
    IP4,
    IP6,
    P2P_STRATEGIES
)
from typing import Any, Dict, List, Optional, Union
from util.logging import log

class P2PManager:
    async def __init__(self, node_id: Optional[str] = None) -> None:
        self.logger = log()
        self.logger.info("Initializing P2PManager...")
        self.interfaces = await list_interfaces()
        self.loaded_interfaces = await load_interfaces(self.interfaces)
        self.p2p_node = P2PNode(ifs=self.loaded_interfaces)
        self.nickname = node_id
    
    async def start(self):
        await self.p2p_node.start()
        self.logger.info("P2P Node started with interfaces: %s", self.loaded_interfaces)
        nickname = await self.p2p_node.nickname(self.nickname if self.nickname else self.p2p_node.node_id)
        self.logger.info(f"P2P Node nickname set to: {nickname}")

    async def connect(self, address: str, strategies: Optional[list] = P2P_STRATEGIES, address_types: Optional[list] = [EXT_BIND, NIC_BIND], priority: Optional[list] = [IP4, IP6]):
        config: dict[str, Any] = {
            "addr_types": address_types,
            "addr_families": priority,
            "return_msg": False
        }
        pipe = await self.p2p_node.connect(address, strategies=strategies, config=config)
        self.logger.info(f"Connected to P2P Node at: {address}")
        return pipe
