#!/usr/bin/env python3
"""
Simple demonstration of Stellaris IBC API endpoints.
This script shows how to interact with the IBC functionality via REST API.
"""

import asyncio
import aiohttp
import json
import time

async def test_ibc_api():
    """Test IBC API endpoints"""
    base_url = "http://localhost:3006"
    
    print("🌐 Stellaris IBC API Demonstration")
    print("=" * 50)
    
    # Note: This demonstration assumes a running Stellaris node
    print("📋 This demo shows the IBC API structure.")
    print("   To run against a live node, start the Stellaris node with:")
    print("   python run_node.py")
    print()
    
    # Demo API calls (structure only)
    demo_calls = [
        {
            "name": "Create IBC Client",
            "method": "POST",
            "endpoint": "/ibc/client/create",
            "payload": {
                "client_id": "stellaris-light-client-1",
                "client_type": "stellaris-light",
                "consensus_state": {
                    "height": 1000,
                    "timestamp": int(time.time()),
                    "root": "abc123def456"
                },
                "client_state": {
                    "chain_id": "stellaris-testnet",
                    "trust_level": "1/3",
                    "trusting_period": 1209600,
                    "unbonding_period": 1814400
                }
            }
        },
        {
            "name": "Update IBC Client",
            "method": "POST", 
            "endpoint": "/ibc/client/update",
            "payload": {
                "client_id": "stellaris-light-client-1",
                "header": {
                    "height": 1001,
                    "timestamp": int(time.time()),
                    "consensus_state": {
                        "height": 1001,
                        "timestamp": int(time.time()),
                        "root": "def456ghi789"
                    }
                }
            }
        },
        {
            "name": "Get IBC Client",
            "method": "GET",
            "endpoint": "/ibc/client/stellaris-light-client-1",
            "payload": None
        },
        {
            "name": "Initialize IBC Connection",
            "method": "POST",
            "endpoint": "/ibc/connection/open_init",
            "payload": {
                "connection_id": "connection-stellaris-cosmos",
                "client_id": "stellaris-light-client-1",
                "counterparty_client_id": "cosmos-light-client-1",
                "version": "1"
            }
        },
        {
            "name": "Try IBC Connection",
            "method": "POST",
            "endpoint": "/ibc/connection/open_try",
            "payload": {
                "connection_id": "connection-stellaris-cosmos",
                "client_id": "stellaris-light-client-1",
                "counterparty_client_id": "cosmos-light-client-1",
                "counterparty_connection_id": "connection-cosmos-stellaris",
                "version": "1",
                "proof": "proof_data_here",
                "proof_height": 1000
            }
        },
        {
            "name": "Get IBC Connection",
            "method": "GET",
            "endpoint": "/ibc/connection/connection-stellaris-cosmos",
            "payload": None
        },
        {
            "name": "Initialize IBC Channel",
            "method": "POST",
            "endpoint": "/ibc/channel/open_init",
            "payload": {
                "port_id": "transfer",
                "channel_id": "channel-0",
                "counterparty_port_id": "transfer",
                "connection_id": "connection-stellaris-cosmos",
                "version": "stellaris-1"
            }
        },
        {
            "name": "Get IBC Channel",
            "method": "GET",
            "endpoint": "/ibc/channel/transfer/channel-0",
            "payload": None
        },
        {
            "name": "Send IBC Packet",
            "method": "POST",
            "endpoint": "/ibc/packet/send",
            "payload": {
                "source_port": "transfer",
                "source_channel": "channel-0",
                "dest_port": "transfer",
                "dest_channel": "channel-0",
                "data": "48656c6c6f2066726f6d205374656c6c6172697321",  # "Hello from Stellaris!" in hex
                "timeout_height": 2000,
                "timeout_timestamp": int(time.time()) + 3600
            }
        },
        {
            "name": "Receive IBC Packet",
            "method": "POST",
            "endpoint": "/ibc/packet/receive",
            "payload": {
                "packet": {
                    "source_port": "transfer",
                    "source_channel": "channel-0",
                    "dest_port": "transfer",
                    "dest_channel": "channel-0",
                    "data": "48656c6c6f2066726f6d20436f736d6f7321",  # "Hello from Cosmos!" in hex
                    "sequence": 1,
                    "timeout_height": 2000,
                    "timeout_timestamp": int(time.time()) + 3600
                },
                "proof": "packet_proof_data_here",
                "proof_height": 1500
            }
        }
    ]
    
    print("🔗 IBC API Endpoints:")
    print()
    
    for i, call in enumerate(demo_calls, 1):
        print(f"{i:2d}. {call['name']}")
        print(f"    {call['method']} {base_url}{call['endpoint']}")
        
        if call['payload']:
            print(f"    Payload:")
            payload_str = json.dumps(call['payload'], indent=6)
            # Indent the payload
            indented_payload = '\n'.join(f"      {line}" for line in payload_str.split('\n'))
            print(indented_payload)
        else:
            print(f"    No payload required")
        print()
    
    print("📝 Example Usage with curl:")
    print()
    
    # Show a few curl examples
    curl_examples = [
        {
            "name": "Create IBC Client",
            "call": demo_calls[0]
        },
        {
            "name": "Send IBC Packet", 
            "call": demo_calls[8]
        }
    ]
    
    for example in curl_examples:
        call = example['call']
        print(f"# {example['name']}")
        if call['method'] == 'POST':
            payload_json = json.dumps(call['payload'], separators=(',', ':'))
            print(f"curl -X {call['method']} \\")
            print(f"  -H 'Content-Type: application/json' \\")
            print(f"  -d '{payload_json}' \\")
            print(f"  {base_url}{call['endpoint']}")
        else:
            print(f"curl -X {call['method']} {base_url}{call['endpoint']}")
        print()
    
    print("🎯 Key Features:")
    print("• Complete IBC protocol implementation")
    print("• Client state management and verification")
    print("• Connection handshake (4-step process)")
    print("• Channel handshake (4-step process)")
    print("• Packet lifecycle (send, receive, ack, timeout)")
    print("• Cross-chain asset and data transfer")
    print("• Integration with existing Stellaris transaction system")
    print("• REST API for easy integration")
    print()
    
    print("🔧 Architecture:")
    print("• IBC messages are embedded in Stellaris transactions (version 4)")
    print("• IBC state is managed alongside blockchain state")
    print("• Existing node network propagates IBC transactions")
    print("• Modular design allows easy extension")
    print()
    
    print("✅ Ready for cross-chain interoperability!")

if __name__ == "__main__":
    asyncio.run(test_ibc_api())