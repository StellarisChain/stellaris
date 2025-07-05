from typing import Dict, Any, Optional
from dataclasses import dataclass
from stellaris.constants import ENDIAN
from stellaris.utils.general import sha256
import json

@dataclass
class IBCMessage:
    """Base class for all IBC messages"""
    type: str
    data: Dict[str, Any]
    
    def to_bytes(self) -> bytes:
        """Convert message to bytes for transaction inclusion"""
        message_dict = {
            "type": self.type,
            "data": self.data
        }
        return json.dumps(message_dict, sort_keys=True).encode('utf-8')
    
    def hex(self) -> str:
        """Convert message to hex string"""
        return self.to_bytes().hex()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'IBCMessage':
        """Create message from bytes"""
        message_dict = json.loads(data.decode('utf-8'))
        return cls(
            type=message_dict["type"],
            data=message_dict["data"]
        )

@dataclass
class ClientCreateMessage(IBCMessage):
    """Message to create a new IBC client"""
    def __init__(self, client_id: str, client_type: str, consensus_state: Dict[str, Any], 
                 client_state: Dict[str, Any]):
        super().__init__(
            type="client_create",
            data={
                "client_id": client_id,
                "client_type": client_type,
                "consensus_state": consensus_state,
                "client_state": client_state
            }
        )

@dataclass
class ClientUpdateMessage(IBCMessage):
    """Message to update an existing IBC client"""
    def __init__(self, client_id: str, header: Dict[str, Any]):
        super().__init__(
            type="client_update",
            data={
                "client_id": client_id,
                "header": header
            }
        )

@dataclass
class ConnectionOpenInitMessage(IBCMessage):
    """Message to initiate a new IBC connection"""
    def __init__(self, connection_id: str, client_id: str, counterparty_client_id: str,
                 counterparty_connection_id: str = "", version: str = "1"):
        super().__init__(
            type="connection_open_init",
            data={
                "connection_id": connection_id,
                "client_id": client_id,
                "counterparty_client_id": counterparty_client_id,
                "counterparty_connection_id": counterparty_connection_id,
                "version": version
            }
        )

@dataclass
class ConnectionOpenTryMessage(IBCMessage):
    """Message to try opening a connection"""
    def __init__(self, connection_id: str, client_id: str, counterparty_client_id: str,
                 counterparty_connection_id: str, version: str, proof: str, proof_height: int):
        super().__init__(
            type="connection_open_try",
            data={
                "connection_id": connection_id,
                "client_id": client_id,
                "counterparty_client_id": counterparty_client_id,
                "counterparty_connection_id": counterparty_connection_id,
                "version": version,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class ConnectionOpenAckMessage(IBCMessage):
    """Message to acknowledge a connection opening"""
    def __init__(self, connection_id: str, counterparty_connection_id: str,
                 version: str, proof: str, proof_height: int):
        super().__init__(
            type="connection_open_ack",
            data={
                "connection_id": connection_id,
                "counterparty_connection_id": counterparty_connection_id,
                "version": version,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class ConnectionOpenConfirmMessage(IBCMessage):
    """Message to confirm a connection opening"""
    def __init__(self, connection_id: str, proof: str, proof_height: int):
        super().__init__(
            type="connection_open_confirm",
            data={
                "connection_id": connection_id,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class ChannelOpenInitMessage(IBCMessage):
    """Message to initiate a new IBC channel"""
    def __init__(self, port_id: str, channel_id: str, counterparty_port_id: str,
                 counterparty_channel_id: str, connection_id: str, version: str):
        super().__init__(
            type="channel_open_init",
            data={
                "port_id": port_id,
                "channel_id": channel_id,
                "counterparty_port_id": counterparty_port_id,
                "counterparty_channel_id": counterparty_channel_id,
                "connection_id": connection_id,
                "version": version
            }
        )

@dataclass
class ChannelOpenTryMessage(IBCMessage):
    """Message to try opening a channel"""
    def __init__(self, port_id: str, channel_id: str, counterparty_port_id: str,
                 counterparty_channel_id: str, connection_id: str, version: str,
                 proof: str, proof_height: int):
        super().__init__(
            type="channel_open_try",
            data={
                "port_id": port_id,
                "channel_id": channel_id,
                "counterparty_port_id": counterparty_port_id,
                "counterparty_channel_id": counterparty_channel_id,
                "connection_id": connection_id,
                "version": version,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class ChannelOpenAckMessage(IBCMessage):
    """Message to acknowledge a channel opening"""
    def __init__(self, port_id: str, channel_id: str, counterparty_version: str,
                 proof: str, proof_height: int):
        super().__init__(
            type="channel_open_ack",
            data={
                "port_id": port_id,
                "channel_id": channel_id,
                "counterparty_version": counterparty_version,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class ChannelOpenConfirmMessage(IBCMessage):
    """Message to confirm a channel opening"""
    def __init__(self, port_id: str, channel_id: str, proof: str, proof_height: int):
        super().__init__(
            type="channel_open_confirm",
            data={
                "port_id": port_id,
                "channel_id": channel_id,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class PacketSendMessage(IBCMessage):
    """Message to send an IBC packet"""
    def __init__(self, source_port: str, source_channel: str, dest_port: str,
                 dest_channel: str, data: bytes, timeout_height: int, timeout_timestamp: int):
        super().__init__(
            type="packet_send",
            data={
                "source_port": source_port,
                "source_channel": source_channel,
                "dest_port": dest_port,
                "dest_channel": dest_channel,
                "data": data.hex(),
                "timeout_height": timeout_height,
                "timeout_timestamp": timeout_timestamp
            }
        )

@dataclass
class PacketReceiveMessage(IBCMessage):
    """Message to receive an IBC packet"""
    def __init__(self, packet: Dict[str, Any], proof: str, proof_height: int):
        super().__init__(
            type="packet_receive",
            data={
                "packet": packet,
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class PacketAckMessage(IBCMessage):
    """Message to acknowledge an IBC packet"""
    def __init__(self, packet: Dict[str, Any], acknowledgement: bytes, proof: str, proof_height: int):
        super().__init__(
            type="packet_ack",
            data={
                "packet": packet,
                "acknowledgement": acknowledgement.hex(),
                "proof": proof,
                "proof_height": proof_height
            }
        )

@dataclass
class PacketTimeoutMessage(IBCMessage):
    """Message to timeout an IBC packet"""
    def __init__(self, packet: Dict[str, Any], proof: str, proof_height: int):
        super().__init__(
            type="packet_timeout",
            data={
                "packet": packet,
                "proof": proof,
                "proof_height": proof_height
            }
        )

def create_message_from_dict(msg_dict: Dict[str, Any]) -> IBCMessage:
    """Factory function to create appropriate message type from dictionary"""
    msg_type = msg_dict["type"]
    data = msg_dict["data"]
    
    if msg_type == "client_create":
        return ClientCreateMessage(
            client_id=data["client_id"],
            client_type=data["client_type"],
            consensus_state=data["consensus_state"],
            client_state=data["client_state"]
        )
    elif msg_type == "client_update":
        return ClientUpdateMessage(
            client_id=data["client_id"],
            header=data["header"]
        )
    elif msg_type == "connection_open_init":
        return ConnectionOpenInitMessage(
            connection_id=data["connection_id"],
            client_id=data["client_id"],
            counterparty_client_id=data["counterparty_client_id"],
            counterparty_connection_id=data.get("counterparty_connection_id", ""),
            version=data.get("version", "1")
        )
    elif msg_type == "connection_open_try":
        return ConnectionOpenTryMessage(
            connection_id=data["connection_id"],
            client_id=data["client_id"],
            counterparty_client_id=data["counterparty_client_id"],
            counterparty_connection_id=data["counterparty_connection_id"],
            version=data["version"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "connection_open_ack":
        return ConnectionOpenAckMessage(
            connection_id=data["connection_id"],
            counterparty_connection_id=data["counterparty_connection_id"],
            version=data["version"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "connection_open_confirm":
        return ConnectionOpenConfirmMessage(
            connection_id=data["connection_id"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "channel_open_init":
        return ChannelOpenInitMessage(
            port_id=data["port_id"],
            channel_id=data["channel_id"],
            counterparty_port_id=data["counterparty_port_id"],
            counterparty_channel_id=data.get("counterparty_channel_id", ""),
            connection_id=data["connection_id"],
            version=data["version"]
        )
    elif msg_type == "channel_open_try":
        return ChannelOpenTryMessage(
            port_id=data["port_id"],
            channel_id=data["channel_id"],
            counterparty_port_id=data["counterparty_port_id"],
            counterparty_channel_id=data["counterparty_channel_id"],
            connection_id=data["connection_id"],
            version=data["version"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "channel_open_ack":
        return ChannelOpenAckMessage(
            port_id=data["port_id"],
            channel_id=data["channel_id"],
            counterparty_version=data["counterparty_version"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "channel_open_confirm":
        return ChannelOpenConfirmMessage(
            port_id=data["port_id"],
            channel_id=data["channel_id"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "packet_send":
        return PacketSendMessage(
            source_port=data["source_port"],
            source_channel=data["source_channel"],
            dest_port=data["dest_port"],
            dest_channel=data["dest_channel"],
            data=bytes.fromhex(data["data"]),
            timeout_height=data["timeout_height"],
            timeout_timestamp=data["timeout_timestamp"]
        )
    elif msg_type == "packet_receive":
        return PacketReceiveMessage(
            packet=data["packet"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "packet_ack":
        return PacketAckMessage(
            packet=data["packet"],
            acknowledgement=bytes.fromhex(data["acknowledgement"]),
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    elif msg_type == "packet_timeout":
        return PacketTimeoutMessage(
            packet=data["packet"],
            proof=data["proof"],
            proof_height=data["proof_height"]
        )
    else:
        raise ValueError(f"Unknown IBC message type: {msg_type}")