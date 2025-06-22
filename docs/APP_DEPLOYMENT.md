# Decentralized App Deployment Platform

## Overview

The VoxaCommunications network now supports deploying and running decentralized applications across the node network. This system allows you to deploy containerized applications, source code, or pre-built binaries that will be distributed and executed across multiple nodes automatically.

## Architecture

### Core Components

1. **App Manager** (`app_manager.py`) - Central orchestrator for app lifecycle management
2. **Security & Sandboxing** (`security.py`) - Provides isolation and security controls
3. **Load Balancer** (`load_balancer.py`) - Routes traffic to app instances
4. **Integration Layer** (`integration.py`) - Integrates with the main VoxaCommunications node

### How Apps Run

Apps can be deployed in several ways:

#### 1. Container-based Deployment
- **Docker containers** are the primary deployment method
- Apps are packaged as Docker images
- Automatically distributed across available nodes
- Full isolation and resource limits

#### 2. Source Code Deployment
- Upload source code that gets built automatically
- Supports multiple runtimes (Python, Node.js, Go, Rust, Java)
- Automatic Dockerfile generation if needed
- Built images are cached and reused

#### 3. Binary Deployment
- Pre-compiled binaries can be deployed directly
- Wrapped in minimal containers for isolation
- Useful for compiled languages or existing executables

## Key Features

### 🔒 Security & Isolation
- **Sandboxed execution** with resource limits
- **Non-privileged containers** by default
- **Network isolation** and controlled external access
- **Filesystem isolation** with read-only root filesystem
- **Resource limits** (CPU, memory, storage, processes)

### ⚖️ Load Balancing & High Availability
- **Multiple load balancing strategies**:
  - Round-robin
  - Least connections
  - Weighted round-robin
  - Health-based routing
  - Latency-based routing
- **Automatic failover** when instances fail
- **Health checking** with circuit breaker pattern
- **Auto-scaling** based on demand

### 🌐 Decentralized Operation
- **P2P app discovery** via existing network protocols
- **Distributed deployment** across multiple nodes
- **Geographic distribution** for better performance
- **Node capability matching** (CPU, memory, features)

### 📊 Monitoring & Management
- **Real-time health monitoring**
- **Resource usage tracking**
- **Performance metrics collection**
- **Centralized logging aggregation**

## Configuration

### Enable App Deployment

Add to `config/settings.json`:
```json
{
    "features": {
        "enable-app-deployment": true
    }
}
```

### App Configuration

Create `config/apps.json`:
```json
{
    "app_data_dir": "data/apps",
    "max_apps_per_node": 10,
    "default_memory_limit": "512m",
    "default_cpu_limit": "1.0",
    "health_check_interval": 30,
    "enable_auto_scaling": true,
    "docker_network": "voxacomms-apps",
    "security": {
        "allow_privileged_containers": false,
        "enable_resource_limits": true,
        "allowed_registries": ["docker.io", "ghcr.io"]
    }
}
```

## API Endpoints

### Deploy an Application
```http
POST /api/apps/deploy_app

{
    "name": "my-web-app",
    "version": "1.0.0",
    "image": "nginx:alpine",
    "replicas": 3,
    "resource_requirements": {
        "memory": "256m",
        "cpu": "0.5"
    },
    "network_config": {
        "ports": {
            "80/tcp": {"HostPort": "8080"}
        }
    }
}
```

### List Applications
```http
GET /api/apps/list_apps
```

### Get App Status
```http
GET /api/apps/get_app_status?app_id=<app_id>
```

### Stop Application
```http
POST /api/apps/stop_app

{
    "app_id": "<app_id>"
}
```

### Scale Application
```http
POST /api/apps/scale_app

{
    "app_id": "<app_id>",
    "replicas": 5
}
```

## Usage Examples

### 1. Deploy a Simple Web Server
```bash
curl -X POST http://localhost:9999/api/apps/deploy_app \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-world",
    "version": "1.0.0",
    "image": "nginx:alpine",
    "replicas": 2,
    "network_config": {
        "ports": {"80/tcp": {"HostPort": "8080"}}
    }
  }'
```

### 2. Deploy a Python Application from Source
```bash
curl -X POST http://localhost:9999/api/apps/deploy_app \
  -H "Content-Type: application/json" \
  -d '{
    "name": "python-api",
    "version": "1.0.0",
    "source_code_hash": "sha256:abc123...",
    "build_config": {
        "runtime": "python",
        "version": "3.12"
    },
    "replicas": 3,
    "resource_requirements": {
        "memory": "512m",
        "cpu": "1.0"
    }
  }'
```

### 3. Deploy with Advanced Configuration
```bash
curl -X POST http://localhost:9999/api/apps/deploy_app \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database-app",
    "version": "2.1.0",
    "image": "postgres:15-alpine",
    "replicas": 1,
    "resource_requirements": {
        "memory": "1G",
        "cpu": "2.0",
        "storage": "5G"
    },
    "runtime_config": {
        "environment": {
            "POSTGRES_DB": "myapp",
            "POSTGRES_USER": "appuser",
            "POSTGRES_PASSWORD": "secretpassword"
        }
    },
    "network_config": {
        "ports": {"5432/tcp": {"HostPort": "5432"}}
    }
  }'
```

## CLI Commands

You can also manage apps via CLI:

```bash
# Deploy example app
python src/cli.py app deploy

# List deployed apps
python src/cli.py app list

# Get app status
python src/cli.py app status --app-id <app_id>

# Stop app
python src/cli.py app stop --app-id <app_id>
```

## Network Integration

### P2P App Discovery
Apps are automatically registered with the network discovery system:
- **Service advertisements** via existing P2P protocols
- **Capability broadcasting** (available resources, supported runtimes)
- **Load balancing** across geographical regions

### Request Routing
The system integrates with VoxaCommunications' existing routing:
- **Split requests** can be routed to different app instances
- **Route optimization** based on latency and load
- **Failover routing** when instances become unavailable

### Data Synchronization
Apps can leverage the network's data sync capabilities:
- **Distributed state management**
- **Event streaming** between app instances
- **Database replication** across nodes

## Security Considerations

### Container Security
- **Read-only root filesystem** by default
- **Non-root user execution**
- **Minimal capabilities** granted
- **Network isolation** from host and other containers
- **Resource limits** prevent resource exhaustion

### Network Security
- **Internal-only networking** by default
- **Controlled port exposure**
- **Traffic encryption** via existing VoxaCommunications protocols
- **Rate limiting** on API endpoints

### Code Security
- **Source code verification** via hashing
- **Registry allowlisting** for container images
- **Build sandboxing** for source deployments
- **Vulnerability scanning** (planned feature)

## Performance & Scaling

### Automatic Scaling
The system monitors app performance and can automatically scale:
- **CPU utilization** threshold-based scaling
- **Memory pressure** scaling
- **Request queue length** scaling
- **Custom metrics** scaling (planned)

### Resource Management
- **Dynamic resource allocation** based on demand
- **Node affinity** for data locality
- **Anti-affinity** for high availability
- **Resource reservation** for critical apps

### Load Distribution
Apps are distributed considering:
- **Geographic proximity** to users
- **Node capacity** and current load
- **Network connectivity** quality
- **Compliance requirements** (data locality)

## Monitoring & Debugging

### Health Monitoring
- **Application health checks** via HTTP endpoints
- **Resource usage monitoring**
- **Performance metrics collection**
- **Log aggregation** across instances

### Debugging Tools
- **Live logs streaming** from app instances
- **Performance profiling** integration
- **Distributed tracing** (planned feature)
- **Debug container access** (with proper permissions)

## Roadmap

### Short Term
- [ ] WebAssembly (WASM) runtime support
- [ ] GPU resource management
- [ ] Advanced networking (service mesh)
- [ ] Persistent volume management

### Medium Term
- [ ] Multi-cloud deployment
- [ ] AI/ML model serving
- [ ] Event-driven autoscaling
- [ ] Advanced security scanning

### Long Term
- [ ] Edge computing integration
- [ ] Blockchain-based app marketplace
- [ ] Decentralized CI/CD pipelines
- [ ] Self-healing infrastructure

## Getting Started

1. **Enable the feature** in your node configuration
2. **Install Docker** if using container deployments
3. **Test with example apps** using the CLI
4. **Deploy your first application** via the API
5. **Monitor and scale** as needed

For more detailed examples and troubleshooting, see the [Testing Guide](../../../TESTING.md#app-deployment-testing).

## Support

For questions or issues with app deployment:
- Check the logs in `logs/` directory
- Use the health check endpoints for diagnostics
- Review resource usage via the monitoring APIs
- Join our [Discord](https://discord.gg/EDtPX5E4D4) for community support
