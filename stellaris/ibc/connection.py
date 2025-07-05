from typing import Dict, Any, Optional
from datetime import datetime
from stellaris.ibc.state import IBCConnectionState

class IBCConnection:
    """
    IBC Connection implementation for managing connections between chains.
    Handles connection opening handshake and state management.
    """
    
    def __init__(self, ibc_state, ibc_client):
        self.ibc_state = ibc_state
        self.ibc_client = ibc_client
    
    async def connection_open_init(self, connection_id: str, client_id: str, 
                                 counterparty_client_id: str, version: str = "1") -> bool:
        """
        Initialize a new connection (step 1 of handshake).
        
        Args:
            connection_id: Unique identifier for the connection
            client_id: ID of the client to use for this connection
            counterparty_client_id: ID of the counterparty's client
            version: Connection version
            
        Returns:
            bool: True if connection was initialized successfully
        """
        try:
            # Validate client exists
            client = await self.ibc_client.get_client(client_id)
            if not client:
                return False
            
            # Validate connection doesn't already exist
            existing_connection = await self.ibc_state.get_connection(connection_id)
            if existing_connection:
                return False
            
            # Create new connection state
            now = datetime.now()
            connection_state = IBCConnectionState(
                connection_id=connection_id,
                client_id=client_id,
                counterparty_client_id=counterparty_client_id,
                counterparty_connection_id="",  # Will be set later
                state="INIT",
                version=version,
                created_at=now,
                updated_at=now
            )
            
            # Store in state
            return await self.ibc_state.create_connection(connection_state)
            
        except Exception as e:
            print(f"Error initializing connection {connection_id}: {e}")
            return False
    
    async def connection_open_try(self, connection_id: str, client_id: str,
                                counterparty_client_id: str, counterparty_connection_id: str,
                                version: str, proof: str, proof_height: int) -> bool:
        """
        Try to open a connection (step 2 of handshake).
        
        Args:
            connection_id: Unique identifier for the connection
            client_id: ID of the client to use for this connection
            counterparty_client_id: ID of the counterparty's client
            counterparty_connection_id: ID of the counterparty's connection
            version: Connection version
            proof: Proof of counterparty's connection state
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if connection try was successful
        """
        try:
            # Validate client exists
            client = await self.ibc_client.get_client(client_id)
            if not client:
                return False
            
            # Verify proof of counterparty's connection state
            if not await self._verify_connection_proof(client_id, proof, proof_height, 
                                                     counterparty_connection_id):
                return False
            
            # Create or update connection state
            existing_connection = await self.ibc_state.get_connection(connection_id)
            if existing_connection:
                # Update existing connection
                existing_connection.counterparty_connection_id = counterparty_connection_id
                existing_connection.state = "TRYOPEN"
                existing_connection.updated_at = datetime.now()
                await self.ibc_state.update_connection_state(connection_id, "TRYOPEN")
            else:
                # Create new connection
                now = datetime.now()
                connection_state = IBCConnectionState(
                    connection_id=connection_id,
                    client_id=client_id,
                    counterparty_client_id=counterparty_client_id,
                    counterparty_connection_id=counterparty_connection_id,
                    state="TRYOPEN",
                    version=version,
                    created_at=now,
                    updated_at=now
                )
                await self.ibc_state.create_connection(connection_state)
            
            return True
            
        except Exception as e:
            print(f"Error in connection try {connection_id}: {e}")
            return False
    
    async def connection_open_ack(self, connection_id: str, counterparty_connection_id: str,
                                version: str, proof: str, proof_height: int) -> bool:
        """
        Acknowledge a connection opening (step 3 of handshake).
        
        Args:
            connection_id: ID of the connection to acknowledge
            counterparty_connection_id: ID of the counterparty's connection
            version: Connection version
            proof: Proof of counterparty's connection state
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if connection ack was successful
        """
        try:
            # Get existing connection
            connection = await self.ibc_state.get_connection(connection_id)
            if not connection or connection.state != "INIT":
                return False
            
            # Verify proof of counterparty's connection state
            if not await self._verify_connection_proof(connection.client_id, proof, proof_height,
                                                     counterparty_connection_id):
                return False
            
            # Update connection state
            connection.counterparty_connection_id = counterparty_connection_id
            connection.state = "OPEN"
            connection.version = version
            connection.updated_at = datetime.now()
            
            return await self.ibc_state.update_connection_state(connection_id, "OPEN")
            
        except Exception as e:
            print(f"Error in connection ack {connection_id}: {e}")
            return False
    
    async def connection_open_confirm(self, connection_id: str, proof: str, proof_height: int) -> bool:
        """
        Confirm a connection opening (step 4 of handshake).
        
        Args:
            connection_id: ID of the connection to confirm
            proof: Proof of counterparty's connection state
            proof_height: Height at which proof was generated
            
        Returns:
            bool: True if connection confirm was successful
        """
        try:
            # Get existing connection
            connection = await self.ibc_state.get_connection(connection_id)
            if not connection or connection.state != "TRYOPEN":
                return False
            
            # Verify proof of counterparty's connection state
            if not await self._verify_connection_proof(connection.client_id, proof, proof_height,
                                                     connection.counterparty_connection_id):
                return False
            
            # Update connection state to OPEN
            return await self.ibc_state.update_connection_state(connection_id, "OPEN")
            
        except Exception as e:
            print(f"Error in connection confirm {connection_id}: {e}")
            return False
    
    async def get_connection(self, connection_id: str) -> Optional[IBCConnectionState]:
        """Get connection by ID"""
        return await self.ibc_state.get_connection(connection_id)
    
    async def _verify_connection_proof(self, client_id: str, proof: str, proof_height: int,
                                     counterparty_connection_id: str) -> bool:
        """
        Verify a proof of counterparty's connection state.
        
        Args:
            client_id: ID of the client to use for verification
            proof: Proof to verify
            proof_height: Height at which proof was generated
            counterparty_connection_id: Expected counterparty connection ID
            
        Returns:
            bool: True if proof is valid
        """
        try:
            # Get client for verification
            client = await self.ibc_client.get_client(client_id)
            if not client:
                return False
            
            # Verify proof height is valid
            if proof_height <= 0:
                return False
            
            # In a full implementation, this would:
            # 1. Parse the proof
            # 2. Verify the proof against the client's consensus state
            # 3. Verify the proof contains the expected connection state
            
            # For now, implement basic validation
            return len(proof) > 0 and len(counterparty_connection_id) > 0
            
        except Exception as e:
            print(f"Error verifying connection proof: {e}")
            return False