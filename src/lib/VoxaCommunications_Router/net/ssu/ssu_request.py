import uuid
from pydantic import BaseModel
from typing import Optional
from copy import deepcopy
from lib.VoxaCommunications_Router.net.packet import Packet
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from lib.VoxaCommunications_Router.net.ssu.ssu_control_packet import SSUControlPacket

class SSURequest(BaseModel):
    payload: Packet | SSUPacket | SSUControlPacket = None # Idealy it should be Packet or SSUPacket. But SSUControlPacket is stil allowed for potential use cases.
    addr: Optional[tuple[str, int]] = None
    request_id: Optional[str] = None
    response: Optional[Packet | SSUPacket | SSUControlPacket] = None

    def send_request(self, wait_for_response: Optional[bool] = True, set_self_from_response: Optional[bool] = False) -> Optional[str]:
        from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
        from lib.VoxaCommunications_Router.net.ssu.ssu_node import SSUNode
        net_manager: NetManager = get_global_net_manager()
        ssu_node: SSUNode = net_manager.ssu_node
        if not ssu_node or not ssu_node.running:
            raise RuntimeError("SSU Node is not running. Cannot send SSU request.")
        if wait_for_response:
            response: SSURequest = ssu_node.send_ssu_request_and_wait(self)
            if set_self_from_response:
                self: SSURequest = deepcopy(response)
            return response.request_id
        else:
            return ssu_node.send_ssu_request(self)
        return None   
        
    def is_response(self) -> bool:
        return self.response is not None

    def generate_request_id(self):
        self.request_id = str(uuid.uuid4())
        return self.request_id