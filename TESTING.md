# VoxaCommunications-NetNode Testing Guide

This guide covers the various testing methods and scripts available for the VoxaCommunications-NetNode project.

## Quick Start

The project provides several testing scripts and methods:

1. **Single Node Testing** - `./run.sh`
2. **Multi-Node Development Environment** - `./run_dev_nodes.sh`
3. **CLI Testing and Data Generation** - `python src/cli.py`
4. **Discovery System Testing** - `http://localhost:9999/api/data/discover_*.py`
5. **Compression Library Testing** - `python tests/test_compression.py`

## Prerequisites

- Python 3.8+ (recommended: 3.12)
- Virtual environment support
- Git (for cloning and version control)
- curl (for API testing)

## Testing Methods

### 1. Single Node Testing with `./run.sh`

The main application runner that starts a single VoxaCommunications node.

```bash
# Make the script executable
chmod +x run.sh

# Run the application
./run.sh
```

**What it does:**
- Creates a Python virtual environment (`.venv`) if it doesn't exist
- Installs dependencies from `requirements.txt`
- Reads configuration from `config/settings.json` and `config/dev.json`
- Starts the FastAPI application with uvicorn
- Supports auto-reload for development (configurable in `config/dev.json`)

**Default endpoints:**
- Health check: `http://localhost:9999/status/health`
- API documentation: `http://localhost:9999/docs`
- Program stats: `http://localhost:9999/info/program_stats`

**Configuration:**
- Host/port settings: `config/settings.json`
- Auto-reload setting: `config/dev.json`

### 2. Multi-Node Development Environment with `./run_dev_nodes.sh`

Runs multiple VoxaCommunications nodes simultaneously for testing distributed functionality.

```bash
# Make the script executable
chmod +x run_dev_nodes.sh

# Run with default 3 nodes
./run_dev_nodes.sh

# Run with custom number of nodes (e.g., 5 nodes)
./run_dev_nodes.sh 5
```

**What it does:**
- Creates separate configuration directories for each node in `dev-configs/`
- Starts multiple nodes with sequential port assignments
- Performs health checks on all nodes
- Monitors node status and provides cleanup on exit
- Creates individual log files for each node in `logs/`

**Default port assignments:**
- Node 1: API port 9999, P2P port 9000
- Node 2: API port 10000, P2P port 9001
- Node 3: API port 10001, P2P port 9002
- etc.

**Monitoring commands:**
```bash
# Check all node health
for port in 9999 10000 10001; do
    curl http://127.0.0.1:$port/status/health
done

# Monitor all logs
tail -f logs/node-*.log

# Check running processes
ps aux | grep uvicorn
```

**Important notes:**
- Nodes take 45-60 seconds to fully initialize
- Press Ctrl+C to stop all nodes and clean up
- Each node gets its own configuration and log file

### 3. CLI Testing and Data Generation with `src/cli.py`

The CLI module provides testing utilities and data generation capabilities.

```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src"

# Run the CLI with various commands
python src/cli.py --help
```

**Available commands:**

#### RRI (Relay Routing Information) Testing:
```bash
# Generate test RRI map with benchmarking
python src/cli.py rri map --benchmark --method all --mapsize 25

# Generate with specific method
python src/cli.py rri map --method threaded --mapsize 10 --testdecrypt

# Generate RRI data entries
python src/cli.py rri generate --count 50

# Create single RRI entry
python src/cli.py rri create --ip 192.168.1.100 --port 8080
```

#### Application Server:
```bash
# Run the application server directly
python src/cli.py app run --host 0.0.0.0 --port 9999 --reload
```

**Output:**
- Test data is saved to `testoutput/` directory
- Benchmark results are displayed in console
- Generated files include routing maps and test data


**What it tests:**
- Network scanner functionality
- Node discovery on local networks
- Relay discovery capabilities
- Discovery manager integration
- Public IP discovery configuration (with safety measures)
- API endpoint integration

**Test coverage:**
- Local network scanning (127.0.0.0/24)
- Service probing and health checks
- Configuration management
- Cache functionality
- Rate limiting and security features

### 5. Compression Library Testing

Tests the JSON compression functionality used throughout the application.

```bash
# Run compression tests
python tests/test_compression.py
```

**Test coverage:**
- Basic compression/decompression
- Base64 encoding/decoding
- File compression operations
- Error handling
- Performance analysis
- Real-world scenario testing

### 6. Additional Testing Scripts

#### Basic Test Runner:
```bash
# Simple test runner
./test.sh
```

#### Startup Testing:
```bash
# Test application startup (used in CI/CD)
bash tests/test_startup.sh
```

## Configuration Files

Key configuration files for testing:

- `config/settings.json` - Main application settings
- `config/dev.json` - Development-specific settings
- `config/p2p.json` - P2P networking configuration
- `config/discovery.json` - Network discovery settings
- `requirements.txt` - Python dependencies

## Troubleshooting

### Common Issues:

1. **Port conflicts:** If ports are already in use, modify the base ports in the scripts
2. **Permission errors:** Ensure scripts have execute permissions (`chmod +x script.sh`)
3. **Virtual environment issues:** Delete `.venv` folder and let scripts recreate it
4. **Node startup failures:** Check individual log files in `logs/` directory

### Debugging:

1. **Check logs:**
   ```bash
   # Single node
   tail -f logs/*.log
   
   # Multi-node
   tail -f logs/node-*.log
   ```

2. **Verify configuration:**
   ```bash
   # Check config syntax
   python -c "import json; print(json.load(open('config/settings.json')))"
   ```

3. **Test API endpoints:**
   ```bash
   # Health check
   curl http://localhost:9999/status/health
   
   # Program stats
   curl http://localhost:9999/info/program_stats
   ```

### Health Check Endpoints:

Each node provides several endpoints for testing:
- `/status/health` - Basic health check
- `/info/program_stats` - Detailed application statistics
- `/docs` - Interactive API documentation
- `/` - Root endpoint

## CI/CD Integration

The project includes GitHub Actions workflows:
- `.github/workflows/test-run.yml` - Automated testing on push/PR
- Tests include syntax validation, startup testing, and configuration validation

## Performance Testing

For performance testing and benchmarking:

```bash
# Generate benchmark data
bash benchmark.sh

# RRI map performance testing
python src/cli.py rri map --benchmark --method all
```

## Security Considerations

- Public IP discovery is disabled by default for security
- Local network scanning only by default
- Rate limiting is enforced for network operations
- Use test IP ranges (like 203.0.113.0/28) for public IP testing

---

**Note**: This testing documentation is continuously evolving. Please contribute improvements and report any issues you encounter while testing the VoxaCommunications-NetNode project.