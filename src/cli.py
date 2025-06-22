# CLI Testing module

import uuid
import random
import argparse
import sys
import shutil
import asyncio
import os
import json
import traceback
import uvicorn
import io
import requests
import time
from copy import deepcopy
from typing import Optional
from lib.VoxaCommunications_Router.util.ri_utils import save_ri
from lib.VoxaCommunications_Router.registry.registry_manager import RegistryManager
from lib.VoxaCommunications_Router.ri.ri_manager import RIManager
from lib.VoxaCommunications_Router.ri.generate_maps import generate_relay_map
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routeutils import benchmark_collector, encrypt_routing_chain, encrypt_routing_chain_threaded, encrypt_routing_chain_sequential_batched, decrypt_routing_chain_block_previous, decrypt_routing_chain_block
from lib.VoxaCommunications_Router.net.net_interface import send_request, request_factory
from lib.VoxaCommunications_Router.net.net_manager import NetManager, set_global_net_manager
from schema.RRISchema import RRISchema
from stores.registrycontroller import get_global_registry_manager, set_global_registry_manager
from util.filereader import save_key_file, read_key_file
from util.jsonreader import read_json_from_namespace
from util.wrappers import deprecated

__version__ = "0.1.0-TEST"

LAST_RUN_FILE = os.path.join("testoutput", "last_run.txt")
debug = dict(read_json_from_namespace("config.dev")).get("debug", False)

def generate_random_ip() -> str:
    """Generate a random IP address."""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

def create_test_rri(relay_ip: str, relay_port: Optional[int] = None) -> None:
    key_generator = RSAKeyGenerator()
    keys = key_generator.generate_keys()
    public_key, private_key = keys["public_key"], keys["private_key"]
    rri_data = RRISchema(
        relay_id=str(uuid.uuid4()),
        relay_ip=relay_ip,
        relay_port=relay_port,
        relay_type="standard",
        capabilities=["routing", "forwarding"],
        public_key=public_key,
        last_seen=None,
        signature=None
    )
    save_ri(rri_data, relay_id=rri_data.relay_id)

def make_api_request(endpoint: str, method: str = "GET", data: dict = None, base_url: str = "http://localhost:8000") -> dict:
    """Helper function to make API requests to the VoxaCommunications server."""
    url = f"{base_url}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server at {base_url}")
        print("Make sure the VoxaCommunications server is running with: python src/cli.py app run")
        return {"error": "connection_failed"}
    except requests.exceptions.Timeout:
        print(f"Error: Request to {url} timed out")
        return {"error": "timeout"}
    except requests.exceptions.RequestException as e:
        print(f"Error: API request failed: {e}")
        return {"error": str(e)}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON response from {url}")
        return {"error": "invalid_json"}

def deploy_example_app() -> None:
    """Deploy the example test application."""
    print("Deploying example application...")
    
    # Check if example app exists
    example_path = "/workspaces/VoxaCommunications-NetNode/examples/test-app"
    if not os.path.exists(os.path.join(example_path, "Dockerfile")):
        print(f"Error: Example app not found at {example_path}")
        print("Please ensure the example app directory exists with Dockerfile")
        return
    
    deploy_data = {
        "app_id": "example-test-app",
        "image_or_path": example_path,
        "app_type": "docker",
        "replicas": 1,
        "resources": {
            "cpu_limit": 0.5,
            "memory_limit": "256Mi"
        },
        "environment": {
            "APP_ENV": "development",
            "PORT": "5000"
        },
        "network": {
            "ports": [{"container_port": 5000, "host_port": 8080}]
        }
    }
    
    result = make_api_request("/apps/add_app/", method="POST", data=deploy_data)
    
    if "error" in result:
        print(f"Deployment failed: {result}")
        return
    
    print(f"✅ Application deployed successfully!")
    print(f"App ID: {result.get('app_id', 'unknown')}")
    print(f"Status: {result.get('status', 'unknown')}")
    if result.get('status') == 'running':
        print(f"🌐 Access the app at: http://localhost:8080")

def list_deployed_apps() -> None:
    """List all deployed applications."""
    print("Listing deployed applications...")
    
    result = make_api_request("/apps/list_apps/")
    
    if "error" in result:
        print(f"Failed to list applications: {result}")
        return
    
    apps = result.get('apps', [])
    
    if not apps:
        print("No applications are currently deployed.")
        return
    
    print(f"\n📦 Found {len(apps)} deployed application(s):")
    print("-" * 60)
    
    for app in apps:
        status_icon = "🟢" if app.get('status') == 'running' else "🔴" if app.get('status') == 'failed' else "🟡"
        print(f"{status_icon} {app.get('app_id', 'unknown')}")
        print(f"   Status: {app.get('status', 'unknown')}")
        print(f"   Replicas: {app.get('replicas', 'unknown')}")
        print(f"   Type: {app.get('app_type', 'unknown')}")
        if app.get('ports'):
            ports_str = ", ".join([f"{p.get('host_port')}:{p.get('container_port')}" for p in app.get('ports', [])])
            print(f"   Ports: {ports_str}")
        print()

def get_app_status(app_id: str) -> None:
    """Get status of a specific application."""
    print(f"Getting status for application: {app_id}")
    
    result = make_api_request(f"/apps/get_app_status/?app_id={app_id}")
    
    if "error" in result:
        print(f"Failed to get app status: {result}")
        return
    
    app = result.get('app', {})
    
    if not app:
        print(f"❌ Application '{app_id}' not found")
        return
    
    status_icon = "🟢" if app.get('status') == 'running' else "🔴" if app.get('status') == 'failed' else "🟡"
    print(f"\n{status_icon} Application Status: {app.get('status', 'unknown')}")
    print("-" * 40)
    print(f"App ID: {app.get('app_id', 'unknown')}")
    print(f"Type: {app.get('app_type', 'unknown')}")
    print(f"Replicas: {app.get('replicas', 'unknown')}")
    print(f"Created: {app.get('created_at', 'unknown')}")
    print(f"Last Updated: {app.get('last_updated', 'unknown')}")
    
    if app.get('ports'):
        print("Ports:")
        for port in app.get('ports', []):
            print(f"  - {port.get('host_port')}:{port.get('container_port')}")
    
    if app.get('environment'):
        print("Environment Variables:")
        for key, value in app.get('environment', {}).items():
            print(f"  - {key}={value}")

def stop_app(app_id: str) -> None:
    """Stop a deployed application."""
    print(f"Stopping application: {app_id}")
    
    result = make_api_request(f"/apps/add_stop_app/", method="POST", data={"app_id": app_id})
    
    if "error" in result:
        print(f"Failed to stop application: {result}")
        return
    
    if result.get('success'):
        print(f"✅ Application '{app_id}' stopped successfully")
    else:
        print(f"❌ Failed to stop application '{app_id}': {result.get('message', 'unknown error')}")

def scale_app(app_id: str, replicas: int) -> None:
    """Scale an application to the specified number of replicas."""
    print(f"Scaling application '{app_id}' to {replicas} replicas...")
    
    scale_data = {
        "app_id": app_id,
        "replicas": replicas
    }
    
    result = make_api_request(f"/apps/add_scale_app/", method="POST", data=scale_data)
    
    if "error" in result:
        print(f"Failed to scale application: {result}")
        return
    
    if result.get('success'):
        print(f"✅ Application '{app_id}' scaled to {replicas} replicas successfully")
    else:
        print(f"❌ Failed to scale application '{app_id}': {result.get('message', 'unknown error')}")

def create_test_rri(relay_ip: str, relay_port: Optional[int] = None) -> None:
    key_generator = RSAKeyGenerator()
    keys = key_generator.generate_keys()
    public_key, private_key = keys["public_key"], keys["private_key"]
    rri_data = RRISchema(
        relay_id=str(uuid.uuid4()),
        relay_ip=relay_ip,
        relay_port=relay_port,
        relay_type="standard",
        capabilities=["routing", "forwarding"],
        metadata={"location": "datacenter-1"},
        public_key=public_key,
        public_key_hash=keys["public_key_hash"],  # Use hash from same key generation
        private_key_debug=private_key if debug else None,
        program_version=__version__
    ).dict()
    save_ri(rri_data["relay_id"], rri_data, "rri")
    save_key_file(rri_data["relay_id"], private_key, "rri")

def setup_registry_manager() -> None:
    pass

def bootstrap_ri() -> None:
    # Create event loop if needed
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    net_manager: NetManager = NetManager()
    net_manager.setup_ssu_node()
    
    # Start the SSU Node server task
    print("Starting SSU Node server...")
    ssu_task = net_manager.serve_ssu_node()
    
    if ssu_task:
        # Give the SSU Node time to initialize and bind to socket
        print("Waiting for SSU Node to initialize...")
        loop.run_until_complete(asyncio.sleep(1.0))
        
        # Check if the task started successfully
        if not ssu_task.done():
            print("SSU Node started successfully and is running in background")
        elif ssu_task.exception():
            print(f"SSU Node failed to start: {ssu_task.exception()}")
            return
    net_manager.setup_internal_http() # Used with the testing bootstrap of localhost:9000, which would route to itself

    set_global_net_manager(net_manager)
    registry_manager: RegistryManager = RegistryManager(client_type="node")
    set_global_registry_manager(registry_manager)
    ri_manager: RIManager = RIManager(type="node")
    ri_manager.check_initialization()
    if not ri_manager.initialized:
        ri_manager.initialize()
    ri_manager.fetch_bootstrap_ri(path="rri")
    
    # Keep the program running with the SSU Node server
    if ssu_task and not ssu_task.done():
        print("Bootstrap complete. SSU Node is running. Press Ctrl+C to stop.")
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            print("\nReceived interrupt signal, shutting down...")
            ssu_task.cancel()
            try:
                loop.run_until_complete(asyncio.wait_for(ssu_task, timeout=2.0))
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            print("Shutdown complete.")
    else:
        print("SSU Node task completed unexpectedly")

# Clear your RRI after doing this, if you are using a production environment
def generate_test_rri_data(count: int = 10) -> None:
    for _ in range(count):
        key_generator = RSAKeyGenerator()
        # Fix: Call generate_keys() only once to get matching key pair
        keys = key_generator.generate_keys()
        public_key, private_key = keys["public_key"], keys["private_key"]
        rri_data = RRISchema(
            relay_id=str(uuid.uuid4()),
            relay_ip=generate_random_ip(),
            relay_port=random.randint(8000, 9000),
            relay_type="standard",
            capabilities=["routing", "forwarding"],
            metadata={"location": "datacenter-1"},
            public_key=public_key,
            public_key_hash=keys["public_key_hash"],  # Use hash from same key generation
            private_key_debug=private_key if debug else None,
            program_version=__version__
        ).dict()
        save_ri(rri_data["relay_id"], rri_data, "rri")
        save_key_file(rri_data["relay_id"], private_key, "rri")
        #save_key_file(f"{rri_data['relay_id']}_pub", public_key, "rri") # remove after debugging

@deprecated("Debugging function, not for production use")
def diagnose_decryption_issue(current_block: dict, private_key: str) -> dict:
    """
    Diagnose potential issues with decryption by analyzing the block and key data.
    
    Args:
        current_block (dict): The current routing block
        private_key (str): The private key being used for decryption
    
    Returns:
        dict: Diagnostic information about the decryption issue
    """
    diagnosis = {
        "issues_found": [],
        "suggestions": [],
        "key_validation": None,
        "data_validation": {}
    }
    
    # Check if required fields exist
    required_fields = ["relay_id", "encrypted_fernet", "child_route"]
    for field in required_fields:
        if field not in current_block or not current_block[field]:
            diagnosis["issues_found"].append(f"Missing or empty field: {field}")
    
    # Validate the public key in the block
    public_key = current_block.get("public_key")
    if public_key:
        try:
            # Try to validate the key pair
            from lib.VoxaCommunications_Router.cryptography.encryptionutils import validate_rsa_key_pair
            diagnosis["key_validation"] = validate_rsa_key_pair(public_key, private_key)
            if not diagnosis["key_validation"]:
                diagnosis["issues_found"].append("Private key does not match public key in block")
                diagnosis["suggestions"].append("Check if the correct private key is being loaded")
        except Exception as e:
            diagnosis["issues_found"].append(f"Key validation failed: {str(e)}")
    else:
        diagnosis["issues_found"].append("No public key found in current block")
    
    # Validate encrypted_fernet data
    encrypted_fernet = current_block.get("encrypted_fernet")
    if encrypted_fernet:
        try:
            # Try to decode if it's base64
            import base64
            if isinstance(encrypted_fernet, str):
                decoded_fernet = base64.b64decode(encrypted_fernet.encode('utf-8'))
                diagnosis["data_validation"]["encrypted_fernet_length"] = len(decoded_fernet)
            else:
                diagnosis["data_validation"]["encrypted_fernet_length"] = len(encrypted_fernet)
        except Exception as e:
            diagnosis["issues_found"].append(f"Invalid encrypted_fernet data: {str(e)}")
    
    # Add general suggestions
    if diagnosis["issues_found"]:
        diagnosis["suggestions"].extend([
            "Verify that the correct private key file is being loaded",
            "Check if the routing chain was generated with different keys",
            "Ensure the key files haven't been corrupted or modified"
        ])
    
    return diagnosis

def decrypt_test_rri_map(file_path: Optional[str] = None):
    if not file_path:
        with open(LAST_RUN_FILE, 'r') as f:
            line = f.readline().strip()
            if line.startswith("rri_test_map:"):
                file_path = line.split("rri_test_map:")[1]
            else:
                print("No RRI test map found in last_run.txt")
                return
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return
    with open(file_path, 'r') as f:
        routing_chain_str: str = f.read()
    # dosent work in production, as nodes and relays only see one block at a time
    routing_chain: dict = json.loads(routing_chain_str)
    current_block: dict = deepcopy(routing_chain)
    
    # Keep track of all decrypted blocks
    decrypted_blocks = []
    
    running = True
    print("Decrypting routing chain...")
    i = -1
    while running:
        i += 1
        try:
            current_block_id: str = current_block.get("relay_id")
            print(f"Current block ID: {current_block_id}")
            
            # Add current block to our collection before processing
            decrypted_blocks.append({
                "block_index": i,
                "relay_id": current_block_id,
                "block_data": deepcopy(current_block)
            })
            
            # Enhanced debugging for key loading
            try:
                private_key: str = read_key_file(current_block_id, "rri")
                #print(f"Private key length: {len(private_key)} characters")
            except FileNotFoundError as e:
                print(f"Private key file not found: {e}")
            
            # Debug public key information
            public_key = current_block.get("public_key")
            encrypted_fernet = current_block.get("encrypted_fernet")
            if public_key:
                #print(f"Public key present, length: {len(public_key)}")
                #print(f"Public key starts with: {public_key[:50]}...")
                pass
            else:
                print("No public key found in current block")
            
            next_block = decrypt_routing_chain_block_previous(current_block, private_key)
            
            # Check if we've reached the end of the routing chain
            if next_block is None:
                print(f"Reached the end of routing chain at block: {current_block_id}")
                print("SUCCESS: Routing chain decryption completed successfully!")
                running = False
                break
                
            current_block = next_block
        except Exception as e:
            print(f"Decryption complete or error occurred: {e}")
            print(traceback.format_exception(type(e), value=e, tb=e.__traceback__))
            running = False
    
    # Save the complete decrypted routing chain
    complete_decrypted_chain = {
        "decryption_summary": {
            "total_blocks_decrypted": len(decrypted_blocks),
            "success": running == False and "SUCCESS" in locals(),
            "decryption_order": [block["relay_id"] for block in decrypted_blocks]
        },
        "decrypted_blocks": decrypted_blocks,
        "original_encrypted_chain": routing_chain
    }
    
    output_file = os.path.join("testoutput", f"decrypted_rri_map_{str(uuid.uuid4())}.json")
    with open(output_file, 'w') as f:
        f.write(json.dumps(complete_decrypted_chain, indent=2))
    print(f"Complete decrypted routing chain saved to {output_file}")
    print(f"Total blocks processed: {len(decrypted_blocks)}")

def generate_test_rri_map(benchmark: bool = False, method: Optional[str] = "default", max_map_size: Optional[int] = 20, testdecrypt: Optional[bool] = False) -> None:
    relay_map: RoutingMap = generate_relay_map(max_map_size=max_map_size)
    request: Request = Request(routing_map=relay_map, target="example.com")
    if method == "default" :
        routing_chain = request.generate_routing_chain()
    elif method == "threaded":
        routing_chain = request.routing_chain_from_func(encrypt_routing_chain_threaded)
    elif method == "batched":
        routing_chain = request.routing_chain_from_func(encrypt_routing_chain_sequential_batched)
    elif method == "all":
        # For benchmarking purposes, run all methods and compare
        routing_chain = request.generate_routing_chain()
        request.routing_chain_from_func(encrypt_routing_chain_threaded, max_workers=1)
        request.routing_chain_from_func(encrypt_routing_chain_sequential_batched, batch_size=10)
    file_name = os.path.join("testoutput", f"encrypted_rri_map_{str(uuid.uuid4())}.json")
    with open(file_name, 'w') as f:
        f.write(json.dumps(routing_chain, indent=2))
    if os.path.exists(LAST_RUN_FILE):
        os.remove(LAST_RUN_FILE)
    with open(LAST_RUN_FILE, 'w') as f:
        f.write(f"rri_test_map:{file_name}\n")
    print(f"Generated RRI map saved to {file_name}")
    benchmark_stats = benchmark_collector.get_stats()
    if benchmark:
        print(f"\nRouting Module Benchmarks:")
        print("-" * 30)
        for name, stats in benchmark_stats.items():
            print(f"  {name}: {stats.total_calls} calls, "
              f"avg {stats.avg_time*1000:.2f}ms")
        benchmark_file_name = f"testoutput/benchmark_rri_map_{str(uuid.uuid4())}.json"
        print(f"Benchmark data saved to {benchmark_file_name}")
        benchmark_collector.export_to_json(benchmark_file_name)
    if testdecrypt:
        decrypt_test_rri_map(file_path=file_name)

if __name__ == "__main__":
    os.makedirs("testoutput", exist_ok=True)  # Ensure the testoutput directory exists
    # CLI interface with subparsers for different data generation tasks
    parser = argparse.ArgumentParser(description="Generate test data for VoxaCommunications.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # RRI subparser
    rri_parser: argparse.ArgumentParser = subparsers.add_parser('rri', help='RRI-related test data generation')
    rri_subparsers = rri_parser.add_subparsers(dest='rri_command', help='RRI commands')

    # RRI bootstrap subcommand
    rri_bootstrap_parser: argparse.ArgumentParser = rri_subparsers.add_parser('bootstrap', help='Bootstrap RRI data')
    
    # RRI data generation subcommand
    rri_data_parser: argparse.ArgumentParser = rri_subparsers.add_parser('generate', help='Generate test RRI data entries')
    rri_data_parser.add_argument("--count", type=int, default=10, help="Number of RRI entries to generate.")
    
    # RRI create subcommand
    rri_create_parser: argparse.ArgumentParser = rri_subparsers.add_parser('create', help='Create a single RRI entry with specified IP and port')
    rri_create_parser.add_argument("--ip", type=str, required=True, help="IP address for the RRI entry")
    rri_create_parser.add_argument("--port", type=int, help="Port for the RRI entry (optional)")
    
    # RRI clear subcommand
    rri_clear_parser: argparse.ArgumentParser = rri_subparsers.add_parser('clear', help='Clear all RRI data entries')
    rri_clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion of all RRI data")
    
    # RRI map generation subcommand
    rri_map_parser: argparse.ArgumentParser = rri_subparsers.add_parser('map', help='Generate and display RRI relay map')
    rri_map_parser.add_argument("--benchmark", action="store_true", help="Enable benchmarking output for the map generation")
    rri_map_parser.add_argument("--method", type=str, default="default", choices=["default", "threaded", "batched", "all"], 
                               help="Method to use for routing chain generation (default: default)")
    rri_map_parser.add_argument("--mapsize", type=int, default=20, help="Maximum size of the relay map (default: 20). Note: generating large maps may take time. (Grows exponentially)")
    rri_map_parser.add_argument("--testdecrypt", action="store_true", help="Runs the decryption test after generating the map")
    
    # RRI map decryption subcommand
    rri_decrypt_parser: argparse.ArgumentParser = rri_subparsers.add_parser('decrypt', help='Decrypt test RRI map from file')
    rri_decrypt_parser.add_argument("--file", type=str, help="Path to the RRI map file to decrypt. If not provided, uses the last generated map from last_run.txt")
    
    # App subparser
    app_parser: argparse.ArgumentParser = subparsers.add_parser('app', help='Application deployment operations')
    app_subparsers = app_parser.add_subparsers(dest='app_command', help='App commands')
    
    # App deploy subcommand
    app_deploy_parser: argparse.ArgumentParser = app_subparsers.add_parser('deploy', help='Deploy an example application')
    
    # App list subcommand
    app_list_parser: argparse.ArgumentParser = app_subparsers.add_parser('list', help='List deployed applications')
    
    # App status subcommand
    app_status_parser: argparse.ArgumentParser = app_subparsers.add_parser('status', help='Get application status')
    app_status_parser.add_argument("--app-id", type=str, required=True, help="Application ID")
    
    # App stop subcommand
    app_stop_parser: argparse.ArgumentParser = app_subparsers.add_parser('stop', help='Stop an application')
    app_stop_parser.add_argument("--app-id", type=str, required=True, help="Application ID")
    
    # App scale subcommand
    app_scale_parser: argparse.ArgumentParser = app_subparsers.add_parser('scale', help='Scale an application')
    app_scale_parser.add_argument("--app-id", type=str, required=True, help="Application ID")
    app_scale_parser.add_argument("--replicas", type=int, required=True, help="Number of replicas")

    # App server run subcommand  
    app_run_parser: argparse.ArgumentParser = app_subparsers.add_parser('run', help='Run the application server')
    app_run_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    app_run_parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    app_run_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    app_run_parser.add_argument("--use-config", action="store_true", help="Use configuration from settings file")

    # Parse the arguments
    args = parser.parse_args()
    
    """
        Example usage: 
        python src/cli.py rri map --benchmark --method threaded --mapsize 25 --testdecrypt
        python src/cli.py rri map --method default --mapsize 6 --testdecrypt
        python src/cli.py rri generate --count 20
        python src/cli.py rri decrypt
        python src/cli.py app run --use-config
    """
    
    if args.command == 'rri':
        if args.rri_command == 'generate':
            generate_test_rri_data(args.count)
            print(f"Generated {args.count} test RRI entries.")
        elif args.rri_command == 'bootstrap':
            print("Bootstrapping RRI data...")
            bootstrap_ri()
        elif args.rri_command == 'map':
            generate_test_rri_map(benchmark=args.benchmark, method=args.method, max_map_size=args.mapsize, testdecrypt=args.testdecrypt)
        elif args.rri_command == 'decrypt':
            decrypt_test_rri_map(file_path=args.file)
        elif args.rri_command == 'create':
            create_test_rri(args.ip, args.port)
            print(f"Created RRI entry with IP: {args.ip}" + (f" and port: {args.port}" if args.port else ""))
        elif args.rri_command == 'clear':
            if args.confirm:
                # Clear the RRI directory
                rri_dir = os.path.join("data", "rri")
                if os.path.exists(rri_dir):
                    shutil.rmtree(rri_dir)
                    print("Cleared all RRI data entries.")
                else:
                    print("RRI directory does not exist.")
            else:
                print("Clear command requires confirmation. Use --confirm to proceed.")
        else:
            rri_parser.print_help()
    elif args.command == 'app':
        if args.app_command == 'run':
            print(f"Starting application server on {args.host}:{args.port}")
            config: dict = read_json_from_namespace("config.settings")["server-settings"] if args.use_config else {
                "host": args.host,
                "port": args.port,
                "reload": args.reload
            }
            from main import app
            uvicorn.run(app, host=config.get("host"), port=config.get("port"), reload=config.get("reload", False))
        elif args.app_command == 'deploy':
            deploy_example_app()
        elif args.app_command == 'list':
            list_deployed_apps()
        elif args.app_command == 'status':
            get_app_status(args.app_id)
        elif args.app_command == 'stop':
            stop_app(args.app_id)
        elif args.app_command == 'scale':
            scale_app(args.app_id, args.replicas)
        else:
            app_parser.print_help()
    else:
        parser.print_help()