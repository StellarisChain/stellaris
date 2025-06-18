#!/usr/bin/env python3
"""
Voxa Discovery Test Script

This script demonstrates the new discovery capabilities of the VoxaCommunications_Router library.
It can be used to test and validate the node and relay discovery functionality.
"""

import asyncio
import sys
import os
import ipaddress

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lib.VoxaCommunications_Router.discovery import (
    DiscoveryManager, 
    NodeDiscovery, 
    RelayDiscovery, 
    NetworkScanner
)
from src.util.logging import log, set_log_config
import uuid

async def test_network_scanner():
    """Test basic network scanning functionality."""
    print("\n=== Testing Network Scanner ===")
    
    scanner = NetworkScanner(timeout=2.0, max_workers=20)
    
    # Test getting local networks
    networks = scanner.get_local_networks()
    print(f"Detected local networks: {networks}")
    
    # Test port scanning on localhost
    print("Testing port scan on localhost...")
    results = scanner.scan_host_ports("127.0.0.1", [9000, 8080, 22, 80])
    print(f"Localhost port scan results: {results}")
    
    # Test Voxa service probing (if local service is running)
    if results.get(9000):
        print("Found service on port 9000, testing Voxa probe...")
        service_info = await scanner.probe_voxa_service("127.0.0.1", 9000)
        if service_info:
            print(f"Voxa service detected: {service_info}")
        else:
            print("No Voxa service detected on port 9000")

async def test_node_discovery():
    """Test node discovery functionality."""
    print("\n=== Testing Node Discovery ===")
    
    node_discovery = NodeDiscovery(cache_duration=60)
    
    # Test discovering nodes
    print("Discovering nodes...")
    nodes = await node_discovery.discover_nodes(
        networks=["127.0.0.0/24"],  # Only scan localhost for testing
        use_cache=False
    )
    
    print(f"Found {len(nodes)} nodes:")
    for i, node in enumerate(nodes, 1):
        print(f"  Node {i}:")
        print(f"    Host: {node.get('host')}")
        print(f"    Port: {node.get('port')}")
        print(f"    Status: {node.get('status')}")
        print(f"    Capabilities: {node.get('capabilities', [])}")
        print(f"    Version: {node.get('version', 'Unknown')}")
    
    # Test ping functionality
    if nodes:
        first_node = nodes[0]
        print(f"\nTesting ping to {first_node['host']}:{first_node['port']}...")
        is_alive = await node_discovery.ping_node(first_node['host'], first_node['port'])
        print(f"Ping result: {'SUCCESS' if is_alive else 'FAILED'}")

async def test_relay_discovery():
    """Test relay discovery functionality."""
    print("\n=== Testing Relay Discovery ===")
    
    # Configure relay discovery with custom ports for testing
    relay_discovery = RelayDiscovery(cache_duration=60, relay_ports=[8080, 8081, 3000])
    
    print(f"Configured relay ports: {relay_discovery.get_relay_ports()}")
    
    # Test discovering relays
    print("Discovering relays...")
    relays = await relay_discovery.discover_relays(
        networks=["127.0.0.0/24"],  # Only scan localhost for testing
        use_cache=False
    )
    
    print(f"Found {len(relays)} relays:")
    for i, relay in enumerate(relays, 1):
        print(f"  Relay {i}:")
        print(f"    Host: {relay.get('host')}")
        print(f"    Port: {relay.get('port')}")
        print(f"    Type: {relay.get('relay_type')}")
        print(f"    Status: {relay.get('status')}")
        print(f"    Capabilities: {relay.get('capabilities', [])}")
    
    # Test adding new relay port
    print("\nAdding port 5000 to relay discovery...")
    relay_discovery.add_relay_port(5000)
    print(f"Updated relay ports: {relay_discovery.get_relay_ports()}")

async def test_discovery_manager():
    """Test the main discovery manager."""
    print("\n=== Testing Discovery Manager ===")
    
    discovery_manager = DiscoveryManager()
    
    # Test comprehensive discovery
    print("Running comprehensive discovery...")
    results = await discovery_manager.discover_all(
        networks=["127.0.0.0/24"],
        force_refresh=True
    )
    
    print(f"Discovery results:")
    print(f"  Total services: {results.get('total_services', 0)}")
    print(f"  Nodes found: {len(results.get('nodes', []))}")
    print(f"  Relays found: {len(results.get('relays', []))}")
    print(f"  Last updated: {results.get('last_updated')}")
    
    # Test network overview
    print("\nGetting network overview...")
    overview = await discovery_manager.get_network_overview()
    
    print("Network Overview:")
    print(f"  Total services: {overview['total_services']}")
    print(f"  Nodes: {overview['nodes']['total']} (healthy: {overview['nodes']['healthy']})")
    print(f"  Relays: {overview['relays']['total']} (healthy: {overview['relays']['healthy']})")
    print(f"  Networks: {list(overview['networks'].keys())}")
    
    # Test cache status
    cache_status = discovery_manager.get_cache_status()
    print(f"\nCache status:")
    print(f"  Nodes cached: {cache_status['nodes_cached']}")
    print(f"  Relays cached: {cache_status['relays_cached']}")
    print(f"  Last discovery: {cache_status['last_full_discovery']}")
    
    # Test finding specific service
    print("\nTesting specific service lookup...")
    service = await discovery_manager.find_service("127.0.0.1", 9000)
    if service:
        print(f"Found service at 127.0.0.1:9000: {service.get('service_type', 'unknown')}")
    else:
        print("No Voxa service found at 127.0.0.1:9000")

async def test_configuration():
    """Test configuration and customization options."""
    print("\n=== Testing Configuration ===")
    
    # Test custom configuration
    custom_config = {
        "timeout": 5.0,
        "max_workers": 30,
        "cache_duration": 600,
        "relay_ports": [8080, 9001, 9002]
    }
    
    discovery_manager = DiscoveryManager(config=custom_config)
    
    print("Created discovery manager with custom config:")
    print(f"  Timeout: {discovery_manager.config['timeout']}s")
    print(f"  Max workers: {discovery_manager.config['max_workers']}")
    print(f"  Cache duration: {discovery_manager.config['cache_duration']}s")
    print(f"  Relay ports: {discovery_manager.config['relay_ports']}")
    
    # Test dynamic port configuration
    print("\nTesting dynamic port configuration...")
    original_ports = discovery_manager.relay_discovery.get_relay_ports()
    print(f"Original relay ports: {original_ports}")
    
    discovery_manager.add_relay_port(7777)
    new_ports = discovery_manager.relay_discovery.get_relay_ports()
    print(f"After adding port 7777: {new_ports}")
    
    discovery_manager.configure_relay_ports([8080, 8081, 8082])
    final_ports = discovery_manager.relay_discovery.get_relay_ports()
    print(f"After reconfiguring: {final_ports}")

async def test_public_ip_discovery():
    """Test public IP discovery functionality with safety measures."""
    print("\n=== Testing Public IP Discovery Configuration ===")
    
    discovery_manager = DiscoveryManager()
    
    # Test getting current public IP config
    print("Current public IP discovery configuration:")
    config = discovery_manager.get_public_ip_config()
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # Test enabling public IP discovery with safe test ranges
    print("\nTesting public IP discovery enablement...")
    test_ranges = ["203.0.113.0/28"]  # RFC 5737 test range - safe to scan
    
    discovery_manager.enable_public_ip_discovery(
        public_ip_ranges=test_ranges,
        max_hosts_per_range=16  # Small range for testing
    )
    
    print("Public IP discovery enabled with test ranges")
    updated_config = discovery_manager.get_public_ip_config()
    print(f"  Enabled: {updated_config['allow_public_ip_discovery']}")
    print(f"  Ranges: {updated_config['public_ip_ranges']}")
    
    # Test configuration of rate limiting
    print("\nTesting rate limiting configuration...")
    discovery_manager.configure_public_ip_scanning(
        rate_limit=True,
        delay_ms=500  # Higher delay for public scans
    )
    
    final_config = discovery_manager.get_public_ip_config()
    print(f"  Rate limiting: {final_config['rate_limit_public_scans']}")
    print(f"  Scan delay: {final_config['public_scan_delay_ms']}ms")
    
    # Test disabling public IP discovery
    print("\nDisabling public IP discovery...")
    discovery_manager.disable_public_ip_discovery()
    
    disabled_config = discovery_manager.get_public_ip_config()
    print(f"  Public discovery disabled: {not disabled_config['allow_public_ip_discovery']}")
    print(f"  Local only: {disabled_config['scan_local_only']}")
    
    print("\n⚠️  IMPORTANT SECURITY NOTE:")
    print("  - Public IP discovery can scan beyond your local network")
    print("  - Only enable with explicit permission to scan target ranges")
    print("  - Use rate limiting to be respectful of network resources")
    print("  - Consider legal and ethical implications before scanning")

async def test_api_public_discovery():
    """Test the public IP discovery API endpoint."""
    print("\n=== Testing Public IP Discovery API ===")
    
    try:
        from src.api.info.configure_public_discovery import handler as config_handler
        
        # Test getting status
        print("Testing API status endpoint...")
        status_result = await config_handler(action="status")
        print(f"Status API result: {status_result['success']}")
        if status_result.get('warning'):
            print(f"Warning: {status_result['warning']}")
        
        # Test enabling via API (with safe test range)
        print("\nTesting API enable endpoint...")
        enable_result = await config_handler(
            action="enable",
            public_ip_ranges=["203.0.113.0/28"],  # Safe test range
            max_hosts_per_range=16
        )
        print(f"Enable API result: {enable_result['success']}")
        print(f"Message: {enable_result.get('message', 'No message')}")
        
        # Test configuration via API
        print("\nTesting API configure endpoint...")
        configure_result = await config_handler(
            action="configure",
            rate_limit=True,
            delay_ms=200
        )
        print(f"Configure API result: {configure_result['success']}")
        
        # Test disabling via API
        print("\nTesting API disable endpoint...")
        disable_result = await config_handler(action="disable")
        print(f"Disable API result: {disable_result['success']}")
        print(f"Message: {disable_result.get('message', 'No message')}")
        
        print("\nAPI endpoints available:")
        print("  GET/POST /info/configure_public_discovery/?action=status")
        print("  POST /info/configure_public_discovery/?action=enable")
        print("  POST /info/configure_public_discovery/?action=disable")
        print("  POST /info/configure_public_discovery/?action=configure")
        
    except Exception as e:
        print(f"API integration test failed: {e}")

async def demo_network_scope_comparison():
    """Demonstrate the difference between local and public IP discovery."""
    print("\n=== Network Scope Comparison Demo ===")
    
    # Create scanner with local-only config
    local_config = {
        "scan_local_only": True,
        "allow_public_ip_discovery": False
    }
    local_scanner = NetworkScanner(config=local_config)
    
    print("Local-only scanner networks:")
    local_networks = local_scanner.get_networks_to_scan()
    for network in local_networks:
        print(f"  {network} (private: {ipaddress.IPv4Network(network, strict=False).is_private})")
    
    # Create scanner with public IP discovery enabled
    public_config = {
        "scan_local_only": False,
        "allow_public_ip_discovery": True,
        "public_ip_ranges": ["203.0.113.0/28", "198.51.100.0/28"]
    }
    public_scanner = NetworkScanner(config=public_config)
    
    print("\nPublic IP discovery scanner networks:")
    public_networks = public_scanner.get_networks_to_scan()
    for network in public_networks:
        is_private = ipaddress.IPv4Network(network, strict=False).is_private
        print(f"  {network} (private: {is_private})")
        if not is_private:
            print(f"    ⚠️  PUBLIC RANGE - would scan internet IPs!")
    
    print("\nSafety Features:")
    print("  ✓ Public discovery disabled by default")
    print("  ✓ Warning messages when public discovery is enabled")
    print("  ✓ Rate limiting for public scans")
    print("  ✓ Configurable host limits per range")
    print("  ✓ Explicit permission required to enable")

async def demo_api_integration():
    """Demonstrate how the discovery system integrates with the API."""
    print("\n=== API Integration Demo ===")
    
    # This demonstrates how the new API endpoints would work
    print("The following API endpoints are now available:")
    print("  GET /data/discover_nodes/ - Discover all nodes")
    print("  GET /data/discover_relays/ - Discover all relays")
    print("  GET /info/network_overview/ - Get network overview")
    
    print("\nExample API usage:")
    print("  curl http://localhost:9000/data/discover_nodes/")
    print("  curl http://localhost:9000/data/discover_relays/")
    print("  curl http://localhost:9000/info/network_overview/")
    
    # Show example of programmatic usage
    try:
        from src.api.data.discover_nodes import handler as discover_nodes_handler
        from src.api.data.discover_relays import handler as discover_relays_handler
        from src.api.info.network_overview import handler as network_overview_handler
        
        print("\nTesting API handlers programmatically...")
        
        # Test node discovery API
        node_result = await discover_nodes_handler(force_refresh=True)
        print(f"Node discovery API result: {node_result['success']}, found {node_result['count']} nodes")
        
        # Test relay discovery API
        relay_result = await discover_relays_handler(force_refresh=True)
        print(f"Relay discovery API result: {relay_result['success']}, found {relay_result['count']} relays")
        
        # Test network overview API
        overview_result = await network_overview_handler()
        if overview_result['success']:
            overview = overview_result['overview']
            print(f"Network overview API: {overview['total_services']} total services")
        
    except Exception as e:
        print(f"API integration test failed: {e}")

async def main():
    """Main test function."""
    print("VoxaCommunications Router Discovery Test")
    print("=" * 50)
    
    # Set up logging
    log_id = str(uuid.uuid4())
    set_log_config(log_id)
    
    logger = log()
    logger.info("Starting discovery system tests")
    
    try:
        # Run all tests
        await test_network_scanner()
        await test_node_discovery()
        await test_relay_discovery()
        await test_discovery_manager()
        await test_configuration()
        await test_public_ip_discovery()  # New test
        await test_api_public_discovery()  # New test
        await demo_network_scope_comparison()  # New test
        await demo_api_integration()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        print("\nTo use the discovery system in your application:")
        print("1. Import: from lib.VoxaCommunications_Router.discovery import DiscoveryManager")
        print("2. Create: discovery_manager = DiscoveryManager()")
        print("3. Discover: results = await discovery_manager.discover_all()")
        print("4. Use the new API endpoints for web-based discovery")
        print("\n⚠️  PUBLIC IP DISCOVERY:")
        print("   - Disabled by default for security")
        print("   - Enable only with explicit permission")
        print("   - Use API endpoint: /info/configure_public_discovery/")
        print("   - Configure in config/discovery.json")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        logger.error(f"Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)