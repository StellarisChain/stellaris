import asyncio
import socket
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket
from util.logging import log
from util.jsonutils import json_from_keys, lists_to_dict

SSU_NODE_CONFIG_KEYS: list[str] = [
    "host",
    "port"
]
SSU_NODE_CONFIG_DEFAULT_VALUES: list[str] = [
    "0.0.0.0",
    9999
]

class SSUNode:
    def __init__(self, config: dict):
        self.config: dict = json_from_keys(SSU_NODE_CONFIG_KEYS, config) or lists_to_dict(SSU_NODE_CONFIG_KEYS, SSU_NODE_CONFIG_DEFAULT_VALUES)
        self.logger = log()
        self.sock: socket.socket = None
        self.loop: asyncio.AbstractEventLoop = None
        self.running = False
        self.host: str = self.config.get("host")
        self.port: str | int = self.config.get("port")
        if isinstance(self.port, str):
            self.port = int(self.port)
    
    async def serve(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.logger.info(f"SSU Node listening on {self.host}:{self.port}")

        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.loop.create_task(self.handle_udp())
    
    async def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        self.logger.info("SSU Node stopped")
        await asyncio.sleep(0.1)
    
    async def handle_udp(self):
        if not self.sock:
            self.logger.error("Socket not initialized")
            return
        
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        
        while self.running:
            try:
                raw_data, addr = await self.loop.run_in_executor(None, self.sock.recvfrom, 4096)
                self.logger.info(f"Received {len(raw_data)} bytes from {addr}")
                packet: Packet | SSUPacket | SSUControlPacket = SSUPacket(raw_data=raw_data, addr=addr) # We are in ssu_node, of course it's an SSUPacket
                packet.raw_to_str()
                ssu_control_packet: SSUControlPacket = packet.upgrade_to_ssu_control_packet() # See if we can upgrade to SSUControlPacket
                if ssu_control_packet:
                    ssu_control_packet.parse_ssu_control()
                    self.logger.info(f"Received SSU Control Packet")
                    match ssu_control_packet.ssu_control_command:
                        case "STATUS":
                            self.logger.info(f"Received STATUS command with params: {ssu_control_packet.ssu_control_params}")
                            pass
                        case "PUNCH":
                            self.logger.info(f"Received PUNCH command with params: {ssu_control_packet.ssu_control_params}")
                            response = SSUControlPacket(
                                str_data='SSU_CONTROL PUNCH',
                                addr=addr
                            )
                            response.parse_ssu_control()
                            response.str_to_raw()
                            self.sock.sendto(response.raw_data, addr)
                            self.logger.info(f"Sent PUNCH response to {addr}")
                        case _:
                            self.logger.warning(f"Unknown SSU control command: {ssu_control_packet.ssu_control_command}")

                
            except Exception as e:
                self.logger.error(f"Error receiving data: {e}")
                await asyncio.sleep(1)
