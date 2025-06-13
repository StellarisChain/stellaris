# Generates some testing data
import uuid
import random
import argparse
import sys
import os
import io
from lib.VoxaCommunications_Router.util.ri_utils import save_ri
from lib.VoxaCommunications_Router.ri.generate_maps import generate_relay_map
from lib.VoxaCommunications_Router.cryptography.keyutils import RSAKeyGenerator
from lib.VoxaCommunications_Router.routing.routing_map import RoutingMap
from lib.VoxaCommunications_Router.routing.request import Request
from lib.VoxaCommunications_Router.routing.routeutils import benchmark_collector
from schema.RRISchema import RRISchema

def generate_random_ip() -> str:
    """Generate a random IP address."""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

# Clear your RRI after doing this, if you are using a production environment
def generate_test_rri_data(count: int = 10) -> None:
    for _ in range(count):
        key_generator = RSAKeyGenerator()
        public_key, private_key = key_generator.generate_keys()["public_key"], key_generator.generate_keys()["private_key"]
        rri_data = RRISchema(
            relay_id=str(uuid.uuid4()),
            relay_ip=generate_random_ip(),
            relay_port=random.randint(8000, 9000),
            relay_type="standard",
            capabilities=["routing", "forwarding"],
            metadata={"location": "datacenter-1"},
            public_key=public_key,
            public_key_hash=f"none"
        ).dict()
        save_ri(str(uuid.uuid4()), rri_data, "rri")

def generate_test_rri_map(benchmark: bool = False) -> None:
    relay_map: RoutingMap = generate_relay_map(max_map_size=20)
    request: Request = Request(routing_map=relay_map, target="example.com")
    routing_chain = request.generate_routing_chain()
    file_name = os.path.join("testoutput", f"test_rri_map_{str(uuid.uuid4())}.json")
    with open(file_name, 'w') as f:
        f.write(str(routing_chain))
    print(f"Generated RRI map saved to {file_name}")
    benchmark_stats = benchmark_collector.get_stats()
    if benchmark:
        for name, stats in benchmark_stats.items():
            print(f"  {name}: {stats.total_calls} calls, "
              f"avg {stats.avg_time*1000:.2f}ms")

if __name__ == "__main__":
    os.makedirs("testoutput", exist_ok=True)  # Ensure the testoutput directory exists
    # CLI interface with subparsers for different data generation tasks
    parser = argparse.ArgumentParser(description="Generate test data for VoxaCommunications.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # RRI subparser
    rri_parser = subparsers.add_parser('rri', help='RRI-related test data generation')
    rri_subparsers = rri_parser.add_subparsers(dest='rri_command', help='RRI commands')
    
    # RRI data generation subcommand
    rri_data_parser = rri_subparsers.add_parser('generate', help='Generate test RRI data entries')
    rri_data_parser.add_argument("--count", type=int, default=10, help="Number of RRI entries to generate.")
    
    # RRI map generation subcommand
    rri_map_parser = rri_subparsers.add_parser('map', help='Generate and display RRI relay map')
    rri_map_parser.add_argument("--benchmark", action="store_true", help="Enable benchmarking output for the map generation")
    
    args = parser.parse_args()
    
    if args.command == 'rri':
        if args.rri_command == 'generate':
            generate_test_rri_data(args.count)
            print(f"Generated {args.count} test RRI entries.")
        elif args.rri_command == 'map':
            generate_test_rri_map(benchmark=args.benchmark)
        else:
            rri_parser.print_help()
    else:
        parser.print_help()