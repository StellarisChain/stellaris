# Installation Guide

## Overview

This guide will help you install and set up VoxaCommunications-NetNode on your system. The platform supports multiple installation methods to accommodate different deployment scenarios.

## System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+), macOS 10.15+, Windows 10+
- **CPU**: 2 cores (4 cores recommended)
- **RAM**: 2GB (4GB recommended)
- **Storage**: 10GB free space (20GB+ recommended)
- **Network**: Internet connection for registry communication

### Recommended Requirements
- **OS**: Linux (Ubuntu 20.04+ or Debian 11+)
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD
- **Network**: Stable internet connection with public IP (optional UPnP support)

### Software Dependencies
- **Python**: 3.8+ (Python 3.12 recommended)
- **Git**: For source code management
- **Docker**: For containerized applications (optional but recommended)
- **curl/wget**: For testing and API calls

## Installation Methods

### Method 1: Quick Start (Recommended)

The quickest way to get started with VoxaCommunications-NetNode:

```bash
# Clone the repository
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# Make run script executable
chmod +x run.sh

# Start the application (creates virtual environment and installs dependencies)
./run.sh
```

This method:
- Automatically creates a Python virtual environment
- Installs all required dependencies
- Starts the application with default settings
- Enables development mode with auto-reload

### Method 2: Manual Installation

For more control over the installation process:

#### Step 1: Clone Repository
```bash
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode
```

#### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Rust dependencies (if using Rust components)
cargo build --release
```

#### Step 4: Configuration
```bash
# Copy example configuration
cp config/settings.json.example config/settings.json
cp config/dev.json.example config/dev.json

# Edit configuration files as needed
nano config/settings.json
```

#### Step 5: Start Application
```bash
# Start with Python directly
python src/main.py

# Or use uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 9999 --reload
```

### Method 3: Docker Installation

Run VoxaCommunications-NetNode in a Docker container:

#### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### Build and Run
```bash
# Clone repository
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# Build Docker image
docker build -t voxa-netnode .

# Run container
docker run -d \
  --name voxa-node \
  -p 9999:9999 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  voxa-netnode

# Or use Docker Compose
docker-compose up -d
```

#### Docker Compose Setup
Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  voxa-node:
    build: .
    ports:
      - "9999:9999"
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - NODE_ENV=production
    restart: unless-stopped
```

### Method 4: Development Container (VS Code)

For development with VS Code Dev Containers:

#### Prerequisites
- VS Code with Dev Containers extension
- Docker Desktop

#### Setup
```bash
# Clone repository
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# Open in VS Code
code .

# When prompted, click "Reopen in Container"
# Or use Command Palette: "Dev Containers: Reopen in Container"
```

The dev container includes:
- Pre-configured Python environment
- All dependencies installed
- Development tools and extensions
- Debugging configuration

### Method 5: Production Installation

For production deployments on Linux servers:

#### Step 1: System Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3 python3-pip python3-venv git curl wget htop

# Create dedicated user
sudo useradd -m -s /bin/bash voxa
sudo usermod -aG docker voxa
```

#### Step 2: Application Setup
```bash
# Switch to voxa user
sudo su - voxa

# Clone repository
git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
cd VoxaCommunications-NetNode

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configuration
```bash
# Copy production configuration
cp config/settings.json.example config/settings.json

# Edit configuration
nano config/settings.json
```

Example production configuration:
```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "mainnet",
  "features": {
    "enable-app-deployment": true,
    "enable-dns": true,
    "enable-registry": true
  },
  "registry": {
    "url": "https://registry.voxacommunications.com",
    "auto_register": true
  }
}
```

#### Step 4: Systemd Service
Create `/etc/systemd/system/voxa-netnode.service`:
```ini
[Unit]
Description=VoxaCommunications NetNode
After=network.target

[Service]
Type=simple
User=voxa
Group=voxa
WorkingDirectory=/home/voxa/VoxaCommunications-NetNode
Environment=PATH=/home/voxa/VoxaCommunications-NetNode/.venv/bin
ExecStart=/home/voxa/VoxaCommunications-NetNode/.venv/bin/python src/main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

#### Step 5: Start Service
```bash
# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable voxa-netnode
sudo systemctl start voxa-netnode

# Check status
sudo systemctl status voxa-netnode
```

## Post-Installation Setup

### 1. Verify Installation

Test that the installation is working:

```bash
# Check service health
curl http://localhost:9999/status/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2025-06-22T12:00:00Z",
  "version": "0.5.241"
}
```

### 2. CLI Setup

Configure the command-line interface:

```bash
# Test CLI
python src/cli.py --help

# Run a node test
python src/cli.py app run --host 0.0.0.0 --port 9999
```

### 3. Network Configuration

Configure networking for your environment:

#### For Development (Default)
```json
{
  "host": "127.0.0.1",
  "port": 9999,
  "node-network-level": "testnet"
}
```

#### For Production
```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "mainnet",
  "registry": {
    "url": "https://registry.voxacommunications.com"
  }
}
```

### 4. Firewall Configuration

Configure firewall rules for network access:

```bash
# Ubuntu/Debian with ufw
sudo ufw allow 9999/tcp
sudo ufw allow 9000/tcp  # For P2P communication

# CentOS/RHEL with firewalld
sudo firewall-cmd --permanent --add-port=9999/tcp
sudo firewall-cmd --permanent --add-port=9000/tcp
sudo firewall-cmd --reload
```

### 5. SSL/TLS Setup (Production)

For production deployments, set up SSL/TLS:

#### Using Let's Encrypt
```bash
# Install certbot
sudo apt install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Configure nginx reverse proxy
sudo apt install nginx
```

Nginx configuration (`/etc/nginx/sites-available/voxa-node`):
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:9999;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Multi-Node Development Setup

For testing distributed functionality:

```bash
# Make the script executable
chmod +x run_dev_nodes.sh

# Start multiple nodes
./run_dev_nodes.sh

# This starts 3 nodes on different ports:
# Node 1: http://localhost:9999
# Node 2: http://localhost:9998
# Node 3: http://localhost:9997
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process using port 9999
sudo lsof -i :9999

# Kill process if needed
sudo kill -9 <PID>
```

#### Permission Denied
```bash
# Fix permissions
sudo chown -R $USER:$USER /path/to/VoxaCommunications-NetNode
chmod +x run.sh
```

#### Python Module Not Found
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### Docker Issues
```bash
# Restart Docker service
sudo systemctl restart docker

# Check Docker status
sudo systemctl status docker

# View container logs
docker logs voxa-node
```

### Log Files

Check log files for debugging:
```bash
# Application logs
tail -f logs/*.log

# System logs (if using systemd)
sudo journalctl -u voxa-netnode -f

# Docker logs
docker logs -f voxa-node
```

### Getting Help

If you encounter issues:

1. **Check the logs** for error messages
2. **Review configuration** files for syntax errors
3. **Verify dependencies** are properly installed
4. **Check network connectivity** and firewall settings
5. **Consult documentation** for specific error messages
6. **Join our community** on Discord or Telegram for help
7. **Open an issue** on GitHub with detailed information

## Next Steps

After successful installation:

1. **Read the [Getting Started Guide](GETTING_STARTED.md)** for basic usage
2. **Explore the [API Reference](API_REFERENCE.md)** for development
3. **Review [Configuration Guide](CONFIGURATION.md)** for customization
4. **Check out [Examples](../examples/)** for practical applications
5. **Join the community** to stay updated on developments

## Updating

To update VoxaCommunications-NetNode:

```bash
# Pull latest changes
git pull origin main

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart voxa-netnode
```

For Docker installations:
```bash
# Pull latest image
docker pull voxacommunications/netnode:latest

# Restart container
docker-compose down && docker-compose up -d
```
