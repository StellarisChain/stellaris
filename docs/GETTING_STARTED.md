# Getting Started with VoxaCommunications-NetNode

## Welcome to VoxaCommunications!

This guide will help you get up and running with VoxaCommunications-NetNode quickly. Whether you're a developer looking to contribute, a network operator wanting to run a node, or someone interested in deploying applications on the decentralized network, this guide has you covered.

## What is VoxaCommunications-NetNode?

VoxaCommunications-NetNode is a decentralized networking platform that enables:

- **Secure Communication**: Privacy-focused messaging and data transfer
- **Request Splitting**: Advanced security through distributed request processing
- **Decentralized Applications**: Deploy and run applications across the network
- **P2P Networking**: Direct peer-to-peer communication without central servers
- **Crypto Integration**: Built-in blockchain capabilities for trust and incentives

## Quick Start (5 Minutes)

### Prerequisites

- Python 3.8+ (Python 3.12 recommended)
- Git
- 4GB RAM minimum
- Internet connection

### 1. Install VoxaCommunications-NetNode

```bash
# Clone the repository
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# Start the application (auto-installs dependencies)
chmod +x run.sh
./run.sh
```

### 2. Verify Installation

Open a new terminal and test the API:

```bash
# Check node health
curl http://localhost:9999/status/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-06-22T12:00:00Z",
  "version": "0.5.241"
}
```

### 3. Explore the Web Interface

Open your browser and visit:
- **API Documentation**: http://localhost:9999/docs
- **Health Status**: http://localhost:9999/status/health
- **System Info**: http://localhost:9999/info/program_stats

🎉 **Congratulations!** You now have a running VoxaCommunications node.

## Basic Usage

### Using the Command Line Interface

VoxaCommunications includes a powerful CLI for managing your node:

```bash
# Navigate to the project directory
cd VoxaCommunications-NetNode

# View available commands
python src/cli.py --help

# Start the server
python src/cli.py app run

# Deploy a test application
python src/cli.py app deploy

# List deployed applications
python src/cli.py app list

# Check application status
python src/cli.py app status --app-id <app-id>
```

### Deploying Your First Application

Let's deploy the included example application:

#### Step 1: Start the Node
```bash
./run.sh
```

#### Step 2: Deploy the Example App
```bash
# In a new terminal
python src/cli.py app deploy
```

#### Step 3: Check Deployment Status
```bash
python src/cli.py app list
```

#### Step 4: Test the Application
```bash
# Get the app status to find the access URL
python src/cli.py app status --app-id <app-id>

# Test the deployed app
curl http://localhost:<app-port>/
```

### Understanding the Network

VoxaCommunications operates on different network levels:

- **`testnet`**: Development and testing (default)
- **`mainnet`**: Production network
- **`devnet`**: Experimental features

You can configure the network level in `config/settings.json`:

```json
{
  "node-network-level": "testnet",
  "host": "127.0.0.1",
  "port": 9999
}
```

## Core Concepts

### 1. Nodes and Relays

- **Nodes**: Full participants that can route traffic, deploy apps, and store data
- **Relays**: Lightweight forwarders that help with traffic distribution
- **Registry**: Directory service for discovering nodes (centralized, moving to decentralized)

### 2. Request Splitting

VoxaCommunications enhances security by splitting requests:

```
Original Request → [Part 1] [Part 2] [Part 3]
                     ↓        ↓        ↓
                  Node A   Node B   Node C
                     ↓        ↓        ↓
                  [Reassemble at Destination]
```

Each part includes cryptographic hashes for verification.

### 3. Decentralized Applications

Applications run in isolated containers distributed across the network:

- **Automatic Distribution**: Apps deploy to multiple nodes
- **Load Balancing**: Traffic automatically routed to healthy instances
- **Auto-scaling**: Replicas adjust based on demand
- **Health Monitoring**: Failed instances automatically replaced

## Development Workflow

### Setting Up Development Environment

For active development, use the development configuration:

```bash
# Copy development config
cp config/dev.json.example config/dev.json

# Edit for your needs
nano config/dev.json
```

Example `config/dev.json`:
```json
{
  "reload": true,
  "log_level": "debug",
  "enable_cors": true,
  "development_mode": true
}
```

### Running Multiple Nodes

Test distributed functionality with multiple local nodes:

```bash
# Start 3 nodes on different ports
chmod +x run_dev_nodes.sh
./run_dev_nodes.sh

# Nodes will start on:
# - http://localhost:9999
# - http://localhost:9998
# - http://localhost:9997
```

### Making Changes

The development setup includes auto-reload:

1. Edit source code files
2. Save changes
3. Server automatically restarts
4. Test your changes

## Configuration

### Basic Configuration

Edit `config/settings.json` for basic settings:

```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "testnet",
  "features": {
    "enable-app-deployment": true,
    "enable-dns": true,
    "enable-registry": true
  }
}
```

### Advanced Configuration

For production deployments, configure additional settings:

#### Registry Configuration
```json
{
  "registry": {
    "url": "https://registry.voxacommunications.com",
    "auto_register": true,
    "heartbeat_interval": 30
  }
}
```

#### Application Deployment
```json
{
  "apps": {
    "max_apps_per_node": 10,
    "default_memory_limit": "512m",
    "default_cpu_limit": "1.0",
    "enable_auto_scaling": true
  }
}
```

#### Networking
```json
{
  "p2p": {
    "listen_port": 9000,
    "max_connections": 50,
    "enable_upnp": true
  }
}
```

## Common Tasks

### 1. Deploying Applications

#### Using the CLI
```bash
python src/cli.py app deploy
```

#### Using the API
```bash
curl -X POST http://localhost:9999/apps/add_app/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "image": "nginx:latest",
    "replicas": 2
  }'
```

### 2. Monitoring Applications

#### CLI Monitoring
```bash
# List all apps
python src/cli.py app list

# Get detailed app status
python src/cli.py app status --app-id <app-id>

# Scale an application
python src/cli.py app scale --app-id <app-id> --replicas 3
```

#### API Monitoring
```bash
# Get app status
curl http://localhost:9999/apps/get_app_status/?app_id=<app-id>

# List all apps
curl http://localhost:9999/apps/list_apps/
```

### 3. Network Discovery

#### Find Available Nodes
```bash
curl http://localhost:9999/data/discover_nodes/
```

#### Check Node Status
```bash
curl http://localhost:9999/status/system
```

### 4. Data Storage

#### Store Data
```bash
curl -X POST http://localhost:9999/data/store/ \
  -H "Content-Type: application/json" \
  -d '{
    "key": "test-data",
    "value": {"message": "Hello, VoxaCommunications!"},
    "ttl": 3600
  }'
```

#### Retrieve Data
```bash
curl http://localhost:9999/data/retrieve/?key=test-data
```

## Testing

### Running Tests

```bash
# Run the test suite
python -m pytest tests/

# Run specific test
python tests/test_compression.py

# Run network diagnostics
python network_diagnostics.test.py
```

### Test Application Deployment

```bash
# Run the deployment test script
python test_app_deployment.py
```

### Manual Testing

Test individual components:

```bash
# Test registry connection
python src/cli.py bootstrap-ri

# Test data compression
python tests/test_compression.py

# Test network connectivity
curl http://localhost:9999/test/connection
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find what's using port 9999
sudo lsof -i :9999

# Kill the process
sudo kill -9 <PID>
```

#### 2. Module Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### 3. Permission Errors
```bash
# Fix file permissions
chmod +x run.sh
chmod +x run_dev_nodes.sh

# Fix directory permissions
sudo chown -R $USER:$USER .
```

#### 4. Network Connectivity Issues
```bash
# Check firewall settings
sudo ufw status

# Allow VoxaCommunications ports
sudo ufw allow 9999/tcp
sudo ufw allow 9000/tcp
```

### Debugging

#### Enable Debug Logging
Edit `config/dev.json`:
```json
{
  "log_level": "debug",
  "reload": true,
  "development_mode": true
}
```

#### View Logs
```bash
# Application logs
tail -f logs/*.log

# Real-time log following
python src/cli.py app run --log-level debug
```

#### Check System Status
```bash
# Node health
curl http://localhost:9999/status/health

# Detailed system info
curl http://localhost:9999/status/system

# Program statistics
curl http://localhost:9999/info/program_stats
```

## Next Steps

Now that you have VoxaCommunications-NetNode running, explore these advanced topics:

### 1. Application Development
- **[App Deployment Guide](APP_DEPLOYMENT.md)**: Learn to deploy complex applications
- **[API Reference](API_REFERENCE.md)**: Comprehensive API documentation
- **[Examples](../examples/)**: Ready-to-use application examples

### 2. Network Operation
- **[Configuration Guide](CONFIGURATION.md)**: Advanced configuration options
- **[Installation Guide](INSTALLATION.md)**: Production deployment
- **[Architecture Overview](ARCHITECTURE.md)**: Understanding the system design

### 3. Development and Contribution
- **[Contributing Guide](../CONTRIBUTING.md)**: How to contribute to the project
- **[Testing Guide](../TESTING.md)**: Comprehensive testing information
- **GitHub Issues**: Report bugs or request features

### 4. Community and Support

Join our community:
- **Discord**: Real-time chat and support
- **Telegram**: Developer discussions
- **GitHub Discussions**: Long-form technical discussions
- **Documentation**: Comprehensive guides and references

## Example Workflows

### Workflow 1: Developer Setup
```bash
# 1. Clone and setup
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# 2. Development environment
./run.sh

# 3. Deploy test app
python src/cli.py app deploy

# 4. Make changes and test
# Edit source files, server auto-reloads
curl http://localhost:9999/status/health
```

### Workflow 2: Multi-Node Testing
```bash
# 1. Start multiple nodes
./run_dev_nodes.sh

# 2. Deploy app to network
python src/cli.py app deploy

# 3. Test load balancing
for i in {1..10}; do
  curl http://localhost:9999/test/connection
done
```

### Workflow 3: Production Deployment
```bash
# 1. Production setup
cp config/settings.json.example config/settings.json
nano config/settings.json  # Configure for production

# 2. Install as service
sudo cp voxa-netnode.service /etc/systemd/system/
sudo systemctl enable voxa-netnode
sudo systemctl start voxa-netnode

# 3. Verify deployment
curl http://your-domain.com:9999/status/health
```

## Performance Tips

### Optimization for Different Use Cases

#### High-Throughput Applications
```json
{
  "apps": {
    "max_apps_per_node": 20,
    "enable_auto_scaling": true,
    "health_check_interval": 10
  },
  "p2p": {
    "max_connections": 100,
    "connection_timeout": 5
  }
}
```

#### Resource-Constrained Environments
```json
{
  "apps": {
    "max_apps_per_node": 5,
    "default_memory_limit": "256m",
    "default_cpu_limit": "0.5"
  },
  "features": {
    "enable-app-deployment": true,
    "enable-dns": false
  }
}
```

#### Development and Testing
```json
{
  "node-network-level": "testnet",
  "features": {
    "enable-app-deployment": true,
    "enable-dns": true,
    "enable-registry": false
  }
}
```

You're now ready to start using VoxaCommunications-NetNode! Remember to check the documentation for specific features and join our community for support and updates.
