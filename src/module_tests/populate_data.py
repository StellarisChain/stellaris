# Generates some testing data
import uuid
import random
import argparse
from ..lib.VoxaCommunications_Router.util.ri_utils import save_ri
from ..schema.RRISchema import RRISchema

def generate_random_ip() -> str:
    """Generate a random IP address."""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

# Clear your RRI after doing this, if you are using a production environment
def generate_test_rri_data(count: int = 10) -> None:
    for _ in range(count):
        rri_data = RRISchema(
            relay_id=str(uuid.uuid4()),
            relay_ip=generate_random_ip(),
            relay_port=random.randint(8000, 9000),
            relay_type="relay",
            capabilities=["routing", "forwarding"],
            metadata={"location": "datacenter-1"},
            public_key=f"none",
            public_key_hash=f"none"
        ).dict()
        save_ri(str(uuid.uuid4()), rri_data, "rri")

if __name__ == "__main__":
    # CLI interface to generate test RRI data
    parser = argparse.ArgumentParser(description="Generate test RRI data.")
    parser.add_argument("--count", type=int, default=10, help="Number of RRI entries to generate.")
    args = parser.parse_args()
    generate_test_rri_data(args.count)
    print(f"Generated {args.count} test RRI entries.")