import os
from util.jsonreader import read_json_from_namespace

def detect_container() -> bool:
    """Detect if running in a container (Docker, etc.)."""
    # Check for common container indicators
    container_indicators: list[bool] = [
        os.path.exists('/.dockerenv'),  # Docker
        os.environ.get('container') is not None,  # systemd-nspawn
        os.environ.get('KUBERNETES_SERVICE_HOST') is not None,  # Kubernetes
        os.path.exists('/proc/1/cgroup') and any(
            'docker' in line or 'containerd' in line 
            for line in open('/proc/1/cgroup', 'r').readlines()
        ) if os.path.exists('/proc/1/cgroup') else False
    ]
    return any(container_indicators)

def is_test_env() -> bool:
    """Check if the environment is a test environment."""
    dev_config: dict = read_json_from_namespace("config.dev")
    return bool(dev_config.get("debug", False))