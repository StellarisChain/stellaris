from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import json

@dataclass
class IBCClientState:
    """Represents the state of an IBC light client"""
    client_id: str
    client_type: str
    latest_height: int
    frozen_height: int
    consensus_state: Dict[str, Any]
    client_state: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBCClientState':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

@dataclass
class IBCConnectionState:
    """Represents the state of an IBC connection"""
    connection_id: str
    client_id: str
    counterparty_client_id: str
    counterparty_connection_id: str
    state: str  # INIT, TRYOPEN, OPEN
    version: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBCConnectionState':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

@dataclass
class IBCChannelState:
    """Represents the state of an IBC channel"""
    port_id: str
    channel_id: str
    counterparty_port_id: str
    counterparty_channel_id: str
    connection_id: str
    state: str  # INIT, TRYOPEN, OPEN, CLOSED
    version: str
    ordering: str  # ORDERED, UNORDERED
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBCChannelState':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

@dataclass
class IBCPacketCommitment:
    """Represents a packet commitment"""
    source_port: str
    source_channel: str
    sequence: int
    data: bytes
    timeout_height: int
    timeout_timestamp: int
    commitment_hash: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['data'] = self.data.hex()
        result['created_at'] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBCPacketCommitment':
        data['data'] = bytes.fromhex(data['data'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

@dataclass
class IBCPacketAcknowledgement:
    """Represents a packet acknowledgement"""
    dest_port: str
    dest_channel: str
    sequence: int
    acknowledgement: bytes
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['acknowledgement'] = self.acknowledgement.hex()
        result['created_at'] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBCPacketAcknowledgement':
        data['acknowledgement'] = bytes.fromhex(data['acknowledgement'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

class IBCState:
    """
    Manages IBC state including clients, connections, channels, and packets.
    This class provides methods to store and retrieve IBC state from the database.
    """
    
    def __init__(self, database):
        self.db = database
        self.clients: Dict[str, IBCClientState] = {}
        self.connections: Dict[str, IBCConnectionState] = {}
        self.channels: Dict[str, IBCChannelState] = {}
        self.packet_commitments: Dict[str, IBCPacketCommitment] = {}
        self.packet_acknowledgements: Dict[str, IBCPacketAcknowledgement] = {}
        self.next_sequence_send: Dict[str, int] = {}
        self.next_sequence_recv: Dict[str, int] = {}
        self.next_sequence_ack: Dict[str, int] = {}
    
    # Client methods
    async def create_client(self, client_state: IBCClientState) -> bool:
        """Create a new IBC client"""
        try:
            if client_state.client_id in self.clients:
                return False
            
            self.clients[client_state.client_id] = client_state
            await self._persist_client(client_state)
            return True
        except Exception as e:
            print(f"Error creating client: {e}")
            return False
    
    async def update_client(self, client_id: str, consensus_state: Dict[str, Any], 
                          client_state: Dict[str, Any], height: int) -> bool:
        """Update an existing IBC client"""
        try:
            if client_id not in self.clients:
                return False
            
            client = self.clients[client_id]
            client.consensus_state = consensus_state
            client.client_state = client_state
            client.latest_height = height
            client.updated_at = datetime.now()
            
            await self._persist_client(client)
            return True
        except Exception as e:
            print(f"Error updating client: {e}")
            return False
    
    async def get_client(self, client_id: str) -> Optional[IBCClientState]:
        """Get client by ID"""
        return self.clients.get(client_id)
    
    # Connection methods
    async def create_connection(self, connection_state: IBCConnectionState) -> bool:
        """Create a new IBC connection"""
        try:
            if connection_state.connection_id in self.connections:
                return False
            
            self.connections[connection_state.connection_id] = connection_state
            await self._persist_connection(connection_state)
            return True
        except Exception as e:
            print(f"Error creating connection: {e}")
            return False
    
    async def update_connection_state(self, connection_id: str, new_state: str) -> bool:
        """Update connection state"""
        try:
            if connection_id not in self.connections:
                return False
            
            connection = self.connections[connection_id]
            connection.state = new_state
            connection.updated_at = datetime.now()
            
            await self._persist_connection(connection)
            return True
        except Exception as e:
            print(f"Error updating connection: {e}")
            return False
    
    async def get_connection(self, connection_id: str) -> Optional[IBCConnectionState]:
        """Get connection by ID"""
        return self.connections.get(connection_id)
    
    # Channel methods
    async def create_channel(self, channel_state: IBCChannelState) -> bool:
        """Create a new IBC channel"""
        try:
            channel_key = f"{channel_state.port_id}/{channel_state.channel_id}"
            if channel_key in self.channels:
                return False
            
            self.channels[channel_key] = channel_state
            await self._persist_channel(channel_state)
            
            # Initialize sequence numbers
            self.next_sequence_send[channel_key] = 1
            self.next_sequence_recv[channel_key] = 1
            self.next_sequence_ack[channel_key] = 1
            
            return True
        except Exception as e:
            print(f"Error creating channel: {e}")
            return False
    
    async def update_channel_state(self, port_id: str, channel_id: str, new_state: str) -> bool:
        """Update channel state"""
        try:
            channel_key = f"{port_id}/{channel_id}"
            if channel_key not in self.channels:
                return False
            
            channel = self.channels[channel_key]
            channel.state = new_state
            channel.updated_at = datetime.now()
            
            await self._persist_channel(channel)
            return True
        except Exception as e:
            print(f"Error updating channel: {e}")
            return False
    
    async def get_channel(self, port_id: str, channel_id: str) -> Optional[IBCChannelState]:
        """Get channel by port and channel ID"""
        channel_key = f"{port_id}/{channel_id}"
        return self.channels.get(channel_key)
    
    # Packet methods
    async def commit_packet(self, commitment: IBCPacketCommitment) -> bool:
        """Commit a packet"""
        try:
            commitment_key = f"{commitment.source_port}/{commitment.source_channel}/{commitment.sequence}"
            self.packet_commitments[commitment_key] = commitment
            await self._persist_packet_commitment(commitment)
            return True
        except Exception as e:
            print(f"Error committing packet: {e}")
            return False
    
    async def acknowledge_packet(self, ack: IBCPacketAcknowledgement) -> bool:
        """Acknowledge a packet"""
        try:
            ack_key = f"{ack.dest_port}/{ack.dest_channel}/{ack.sequence}"
            self.packet_acknowledgements[ack_key] = ack
            await self._persist_packet_acknowledgement(ack)
            return True
        except Exception as e:
            print(f"Error acknowledging packet: {e}")
            return False
    
    async def get_next_sequence_send(self, port_id: str, channel_id: str) -> int:
        """Get next sequence number for sending"""
        channel_key = f"{port_id}/{channel_id}"
        return self.next_sequence_send.get(channel_key, 1)
    
    async def increment_sequence_send(self, port_id: str, channel_id: str) -> int:
        """Increment and return next sequence number for sending"""
        channel_key = f"{port_id}/{channel_id}"
        current = self.next_sequence_send.get(channel_key, 1)
        self.next_sequence_send[channel_key] = current + 1
        return current
    
    # Persistence methods (to be implemented based on database structure)
    async def _persist_client(self, client: IBCClientState):
        """Persist client state to database"""
        # This would be implemented with actual database operations
        pass
    
    async def _persist_connection(self, connection: IBCConnectionState):
        """Persist connection state to database"""
        # This would be implemented with actual database operations
        pass
    
    async def _persist_channel(self, channel: IBCChannelState):
        """Persist channel state to database"""
        # This would be implemented with actual database operations
        pass
    
    async def _persist_packet_commitment(self, commitment: IBCPacketCommitment):
        """Persist packet commitment to database"""
        # This would be implemented with actual database operations
        pass
    
    async def _persist_packet_acknowledgement(self, ack: IBCPacketAcknowledgement):
        """Persist packet acknowledgement to database"""
        # This would be implemented with actual database operations
        pass