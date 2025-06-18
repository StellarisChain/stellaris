# CLI Testing module

import uuid
import random
import argparse
import sys
import shutil
import os
import json
import traceback
import uvicorn
import io
from copy import deepcopy
from typing import Optional
from lib.VoxaCommunications_Router.util.ri_utils import save_ri
from lib.VoxaCommunications_Router.ri.generate_maps import generate_relay_map
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routeutils import benchmark_collector, encrypt_routing_chain, encrypt_routing_chain_threaded, encrypt_routing_chain_sequential_batched, decrypt_routing_chain_block_previous, decrypt_routing_chain_block
from lib.VoxaCommunications_Router.net.net_interface import send_request, request_factory
from schema.RRISchema import RRISchema
from util.filereader import save_key_file, read_key_file
from util.jsonreader import read_json_from_namespace
from util.wrappers import deprecated
from main import app

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
        metadata={"location": "datacenter-1"},
        public_key=public_key,
        public_key_hash=keys["public_key_hash"],  # Use hash from same key generation
        private_key_debug=private_key if debug else None,
        program_version=__version__
    ).dict()
    save_ri(rri_data["relay_id"], rri_data, "rri")
    save_key_file(rri_data["relay_id"], private_key, "rri")
    
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
    app_parser: argparse.ArgumentParser = subparsers.add_parser('app', help='Application-related operations')
    app_subparsers = app_parser.add_subparsers(dest='app_command', help='App commands')
    
    # App run subcommand
    app_run_parser: argparse.ArgumentParser = app_subparsers.add_parser('run', help='Run the application server')
    app_run_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    app_run_parser.add_argument("--port", type=int, default=9999, help="Port to bind the server to (default: 9999)")
    app_run_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    app_run_parser.add_argument("--log-level", type=str, default="info", choices=["critical", "error", "warning", "info", "debug", "trace"], 
                               help="Set the logging level (default: info)")
    app_run_parser.add_argument("--use-config", action="store_true", help="Configuration file to use")
    
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
            uvicorn.run(app, host=config.get("host"), port=config.get("port"), reload=config.get("reload", False))
        else:
            app_parser.print_help()
    else:
        parser.print_help()