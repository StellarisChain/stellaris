from typing import Dict, Any, Optional
from datetime import datetime
from stellaris.ibc.state import IBCPacketCommitment, IBCPacketAcknowledgement
from stellaris.utils.general import sha256

class IBCPacket:
    """
    IBC Packet implementation for managing packet lifecycle.
    Handles packet sending, receiving, acknowledgment, and timeout.
    """
    
    def __init__(self, ibc_state, ibc_channel):
        self.ibc_state = ibc_state
        self.ibc_channel = ibc_channel
    
    async def send_packet(self, source_port: str, source_channel: str, dest_port: str,
                        dest_channel: str, data: bytes, timeout_height: int, 
                        timeout_timestamp: int) -> Optional[int]:
        """
        Send an IBC packet.
        
        Args:
            source_port: Source port ID
            source_channel: Source channel ID
            dest_port: Destination port ID
            dest_channel: Destination channel ID
            data: Packet data
            timeout_height: Timeout height
            timeout_timestamp: Timeout timestamp
            
        Returns:
            Optional[int]: Sequence number if packet was sent successfully
        """
        try:
            # Validate channel exists and is open
            channel = await self.ibc_channel.get_channel(source_port, source_channel)
            if not channel or channel.state != "OPEN":
                return None
            
            # Get next sequence number
            sequence = await self.ibc_state.increment_sequence_send(source_port, source_channel)
            
            # Create packet commitment
            packet_data = {
                "source_port": source_port,
                "source_channel": source_channel,
                "dest_port": dest_port,
                "dest_channel": dest_channel,
                "data": data.hex(),
                "sequence": sequence,
                "timeout_height": timeout_height,
                "timeout_timestamp": timeout_timestamp
            }
            
            # Hash the packet for commitment
            packet_hash = sha256(str(packet_data).encode())
            
            # Create commitment
            commitment = IBCPacketCommitment(
                source_port=source_port,
                source_channel=source_channel,
                sequence=sequence,
                data=data,
                timeout_height=timeout_height,
                timeout_timestamp=timeout_timestamp,
                commitment_hash=packet_hash,
                created_at=datetime.now()
            )
            
            # Store commitment
            if await self.ibc_state.commit_packet(commitment):
                return sequence
            return None
            
        except Exception as e:
            print(f"Error sending packet: {e}")
            return None
    
    async def receive_packet(self, packet: Dict[str, Any], proof: str, proof_height: int) -> bool:
        """
        Receive an IBC packet.
        
        Args:
            packet: Packet data
            proof: Proof of packet commitment on source chain
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if packet was received successfully
        """
        try:
            # Extract packet information
            dest_port = packet.get("dest_port")
            dest_channel = packet.get("dest_channel")
            source_port = packet.get("source_port")
            source_channel = packet.get("source_channel")
            sequence = packet.get("sequence")
            data = bytes.fromhex(packet.get("data", ""))
            timeout_height = packet.get("timeout_height", 0)
            timeout_timestamp = packet.get("timeout_timestamp", 0)
            
            # Validate channel exists and is open
            channel = await self.ibc_channel.get_channel(dest_port, dest_channel)
            if not channel or channel.state != "OPEN":
                return False
            
            # Validate packet hasn't timed out
            if not await self._validate_packet_timeout(timeout_height, timeout_timestamp):
                return False
            
            # Verify proof of packet commitment
            if not await self._verify_packet_proof(channel.connection_id, proof, proof_height, packet):
                return False
            
            # Process packet data (application-specific logic would go here)
            acknowledgement = await self._process_packet_data(data)
            
            # Create acknowledgement
            ack = IBCPacketAcknowledgement(
                dest_port=dest_port,
                dest_channel=dest_channel,
                sequence=sequence,
                acknowledgement=acknowledgement,
                created_at=datetime.now()
            )
            
            # Store acknowledgement
            return await self.ibc_state.acknowledge_packet(ack)
            
        except Exception as e:
            print(f"Error receiving packet: {e}")
            return False
    
    async def acknowledge_packet(self, packet: Dict[str, Any], acknowledgement: bytes,
                               proof: str, proof_height: int) -> bool:
        """
        Acknowledge an IBC packet.
        
        Args:
            packet: Original packet data
            acknowledgement: Acknowledgement data
            proof: Proof of acknowledgement on destination chain
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if packet was acknowledged successfully
        """
        try:
            # Extract packet information
            source_port = packet.get("source_port")
            source_channel = packet.get("source_channel")
            sequence = packet.get("sequence")
            
            # Validate channel exists and is open
            channel = await self.ibc_channel.get_channel(source_port, source_channel)
            if not channel or channel.state != "OPEN":
                return False
            
            # Verify proof of acknowledgement
            if not await self._verify_acknowledgement_proof(channel.connection_id, proof, 
                                                          proof_height, packet, acknowledgement):
                return False
            
            # Process acknowledgement (application-specific logic would go here)
            await self._process_acknowledgement(packet, acknowledgement)
            
            # Remove packet commitment (packet is now acknowledged)
            # In a full implementation, this would be tracked in state
            
            return True
            
        except Exception as e:
            print(f"Error acknowledging packet: {e}")
            return False
    
    async def timeout_packet(self, packet: Dict[str, Any], proof: str, proof_height: int) -> bool:
        """
        Timeout an IBC packet.
        
        Args:
            packet: Original packet data
            proof: Proof of non-receipt on destination chain
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if packet was timed out successfully
        """
        try:
            # Extract packet information
            source_port = packet.get("source_port")
            source_channel = packet.get("source_channel")
            sequence = packet.get("sequence")
            timeout_height = packet.get("timeout_height", 0)
            timeout_timestamp = packet.get("timeout_timestamp", 0)
            
            # Validate channel exists
            channel = await self.ibc_channel.get_channel(source_port, source_channel)
            if not channel:
                return False
            
            # Validate packet has timed out
            if not await self._validate_packet_timeout(timeout_height, timeout_timestamp, check_expired=True):
                return False
            
            # Verify proof of non-receipt
            if not await self._verify_timeout_proof(channel.connection_id, proof, proof_height, packet):
                return False
            
            # Process timeout (application-specific logic would go here)
            await self._process_timeout(packet)
            
            # Remove packet commitment (packet is now timed out)
            # In a full implementation, this would be tracked in state
            
            return True
            
        except Exception as e:
            print(f"Error timing out packet: {e}")
            return False
    
    async def _validate_packet_timeout(self, timeout_height: int, timeout_timestamp: int, 
                                     check_expired: bool = False) -> bool:
        """
        Validate packet timeout constraints.
        
        Args:
            timeout_height: Timeout height
            timeout_timestamp: Timeout timestamp
            check_expired: Whether to check if packet has expired
            
        Returns:
            bool: True if timeout is valid
        """
        try:
            # Get current height and timestamp
            # In a full implementation, this would come from the chain state
            current_height = 1000  # Placeholder
            current_timestamp = int(datetime.now().timestamp())
            
            if check_expired:
                # Check if packet has expired
                if timeout_height > 0 and current_height >= timeout_height:
                    return True
                if timeout_timestamp > 0 and current_timestamp >= timeout_timestamp:
                    return True
                return False
            else:
                # Check if packet hasn't expired yet
                if timeout_height > 0 and current_height >= timeout_height:
                    return False
                if timeout_timestamp > 0 and current_timestamp >= timeout_timestamp:
                    return False
                return True
                
        except Exception as e:
            print(f"Error validating packet timeout: {e}")
            return False
    
    async def _verify_packet_proof(self, connection_id: str, proof: str, proof_height: int,
                                 packet: Dict[str, Any]) -> bool:
        """
        Verify proof of packet commitment.
        
        Args:
            connection_id: Connection ID for verification
            proof: Proof to verify
            proof_height: Height at which proof was generated
            packet: Packet data
            
        Returns:
            bool: True if proof is valid
        """
        try:
            # In a full implementation, this would:
            # 1. Parse the proof
            # 2. Verify the proof against the client's consensus state
            # 3. Verify the proof contains the expected packet commitment
            
            # For now, implement basic validation
            return len(proof) > 0 and proof_height > 0
            
        except Exception as e:
            print(f"Error verifying packet proof: {e}")
            return False
    
    async def _verify_acknowledgement_proof(self, connection_id: str, proof: str, proof_height: int,
                                          packet: Dict[str, Any], acknowledgement: bytes) -> bool:
        """
        Verify proof of packet acknowledgement.
        
        Args:
            connection_id: Connection ID for verification
            proof: Proof to verify
            proof_height: Height at which proof was generated
            packet: Original packet data
            acknowledgement: Acknowledgement data
            
        Returns:
            bool: True if proof is valid
        """
        try:
            # In a full implementation, this would verify the acknowledgement proof
            return len(proof) > 0 and proof_height > 0 and len(acknowledgement) > 0
            
        except Exception as e:
            print(f"Error verifying acknowledgement proof: {e}")
            return False
    
    async def _verify_timeout_proof(self, connection_id: str, proof: str, proof_height: int,
                                  packet: Dict[str, Any]) -> bool:
        """
        Verify proof of packet timeout (non-receipt).
        
        Args:
            connection_id: Connection ID for verification
            proof: Proof to verify
            proof_height: Height at which proof was generated
            packet: Original packet data
            
        Returns:
            bool: True if proof is valid
        """
        try:
            # In a full implementation, this would verify the timeout proof
            return len(proof) > 0 and proof_height > 0
            
        except Exception as e:
            print(f"Error verifying timeout proof: {e}")
            return False
    
    async def _process_packet_data(self, data: bytes) -> bytes:
        """
        Process received packet data.
        
        Args:
            data: Packet data
            
        Returns:
            bytes: Acknowledgement data
        """
        try:
            # In a full implementation, this would:
            # 1. Parse the packet data
            # 2. Execute application-specific logic
            # 3. Return appropriate acknowledgement
            
            # For now, return success acknowledgement
            return b"success"
            
        except Exception as e:
            print(f"Error processing packet data: {e}")
            return b"error"
    
    async def _process_acknowledgement(self, packet: Dict[str, Any], acknowledgement: bytes):
        """
        Process packet acknowledgement.
        
        Args:
            packet: Original packet data
            acknowledgement: Acknowledgement data
        """
        try:
            # In a full implementation, this would execute application-specific logic
            # based on the acknowledgement
            pass
            
        except Exception as e:
            print(f"Error processing acknowledgement: {e}")
    
    async def _process_timeout(self, packet: Dict[str, Any]):
        """
        Process packet timeout.
        
        Args:
            packet: Original packet data
        """
        try:
            # In a full implementation, this would execute application-specific logic
            # for handling packet timeouts
            pass
            
        except Exception as e:
            print(f"Error processing timeout: {e}")