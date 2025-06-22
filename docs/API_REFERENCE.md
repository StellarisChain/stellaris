# VoxaCommunications-NetNode API Reference

## Overview

VoxaCommunications-NetNode provides a comprehensive REST API for managing the decentralized network, deploying applications, and accessing system information. The API is built using FastAPI and provides automatic documentation, validation, and type safety.

## Base URLs

- **Development**: `http://localhost:9999`
- **Production**: Configured via `config/settings.json`

## Authentication

Currently, the API uses token-based authentication for production deployments. Development mode may have authentication disabled for testing purposes.

## API Endpoints

### Application Management APIs

#### Deploy Application
**POST** `/apps/add_app/`

Deploy a new application to the VoxaCommunications network.

**Request Body:**
```json
{
  "name": "my-app",
  "image": "nginx:latest",
  "replicas": 2,
  "resources": {
    "memory": "512m",
    "cpu": "0.5"
  },
  "environment": {
    "NODE_ENV": "production"
  },
  "ports": [
    {
      "container_port": 80,
      "protocol": "tcp"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Application deployed successfully",
  "app_id": "app-12345",
  "deployment_details": {
    "nodes_deployed": 2,
    "instances_created": 2,
    "status": "deploying"
  }
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid request data
- `401`: Authentication required
- `500`: Internal server error

#### List Applications
**GET** `/apps/list_apps/`

Retrieve a list of all deployed applications.

**Query Parameters:**
- `status` (optional): Filter by application status (`running`, `stopped`, `deploying`)
- `node_id` (optional): Filter by specific node
- `limit` (optional): Maximum number of results (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "success": true,
  "applications": [
    {
      "app_id": "app-12345",
      "name": "my-app",
      "status": "running",
      "replicas": {
        "desired": 2,
        "running": 2,
        "healthy": 2
      },
      "created_at": "2025-06-22T10:30:00Z",
      "last_updated": "2025-06-22T11:15:00Z",
      "nodes": ["node-001", "node-002"]
    }
  ],
  "total_count": 1,
  "pagination": {
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

#### Get Application Status
**GET** `/apps/get_app_status/`

Get detailed status information for a specific application.

**Query Parameters:**
- `app_id` (required): Application identifier

**Response:**
```json
{
  "success": true,
  "app_id": "app-12345",
  "name": "my-app",
  "status": "running",
  "health": "healthy",
  "replicas": {
    "desired": 2,
    "running": 2,
    "healthy": 2,
    "unhealthy": 0
  },
  "instances": [
    {
      "instance_id": "inst-001",
      "node_id": "node-001",
      "status": "running",
      "health": "healthy",
      "created_at": "2025-06-22T10:30:00Z",
      "last_health_check": "2025-06-22T12:00:00Z",
      "resource_usage": {
        "cpu_percent": 15.2,
        "memory_mb": 128,
        "network_rx_bytes": 1024000,
        "network_tx_bytes": 512000
      }
    }
  ],
  "metrics": {
    "total_requests": 1500,
    "avg_response_time_ms": 45,
    "error_rate_percent": 0.1
  }
}
```

#### Stop Application
**POST** `/apps/add_stop_app/`

Stop a running application and remove all instances.

**Request Body:**
```json
{
  "app_id": "app-12345",
  "force": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Application stopped successfully",
  "app_id": "app-12345",
  "instances_stopped": 2
}
```

#### Scale Application
**POST** `/apps/add_scale_app/`

Scale an application up or down by adjusting the number of replicas.

**Request Body:**
```json
{
  "app_id": "app-12345",
  "replicas": 5
}
```

**Response:**
```json
{
  "success": true,
  "message": "Application scaled successfully",
  "app_id": "app-12345",
  "previous_replicas": 2,
  "new_replicas": 5,
  "scaling_status": "in_progress"
}
```

### Data Management APIs

#### Network Discovery
**GET** `/data/discover_nodes/`

Discover available nodes in the network.

**Response:**
```json
{
  "success": true,
  "nodes": [
    {
      "node_id": "node-001",
      "address": "192.168.1.100:9999",
      "status": "online",
      "capabilities": ["app-deployment", "relay"],
      "load": {
        "cpu_percent": 25.5,
        "memory_percent": 40.0,
        "active_apps": 3
      },
      "last_seen": "2025-06-22T12:00:00Z"
    }
  ],
  "total_nodes": 1,
  "online_nodes": 1
}
```

#### Store Data
**POST** `/data/store/`

Store data in the distributed network.

**Request Body:**
```json
{
  "key": "user-settings-123",
  "value": {
    "theme": "dark",
    "language": "en"
  },
  "ttl": 3600,
  "replicas": 3
}
```

**Response:**
```json
{
  "success": true,
  "key": "user-settings-123",
  "storage_nodes": ["node-001", "node-002", "node-003"],
  "expires_at": "2025-06-22T13:00:00Z"
}
```

#### Retrieve Data
**GET** `/data/retrieve/`

Retrieve data from the distributed network.

**Query Parameters:**
- `key` (required): Data key to retrieve

**Response:**
```json
{
  "success": true,
  "key": "user-settings-123",
  "value": {
    "theme": "dark",
    "language": "en"
  },
  "metadata": {
    "created_at": "2025-06-22T12:00:00Z",
    "expires_at": "2025-06-22T13:00:00Z",
    "replicas": 3,
    "source_node": "node-001"
  }
}
```

### System Information APIs

#### Health Check
**GET** `/status/health`

Check the health status of the node.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-06-22T12:00:00Z",
  "version": "0.5.241",
  "uptime_seconds": 3600,
  "components": {
    "api": "healthy",
    "networking": "healthy",
    "storage": "healthy",
    "registry": "healthy"
  }
}
```

#### System Status
**GET** `/status/system`

Get detailed system status information.

**Response:**
```json
{
  "node_id": "node-001",
  "status": "running",
  "version": "0.5.241",
  "uptime_seconds": 3600,
  "system_info": {
    "os": "Linux",
    "architecture": "x86_64",
    "cpu_cores": 4,
    "total_memory_mb": 8192,
    "available_memory_mb": 4096,
    "disk_usage": {
      "total_gb": 100,
      "used_gb": 25,
      "available_gb": 75
    }
  },
  "network_info": {
    "connected_peers": 5,
    "total_connections": 12,
    "bytes_sent": 1024000,
    "bytes_received": 2048000
  },
  "applications": {
    "total_deployed": 3,
    "running": 3,
    "stopped": 0,
    "failed": 0
  }
}
```

#### Program Statistics
**GET** `/info/program_stats`

Get program execution statistics.

**Response:**
```json
{
  "statistics": {
    "requests_processed": 5000,
    "average_response_time_ms": 45,
    "error_count": 5,
    "success_rate_percent": 99.9,
    "memory_usage_mb": 256,
    "cpu_usage_percent": 15.5
  },
  "runtime_info": {
    "start_time": "2025-06-22T10:00:00Z",
    "uptime_seconds": 7200,
    "python_version": "3.12.0",
    "process_id": 12345
  }
}
```

#### Version Information
**GET** `/info/version`

Get version and build information.

**Response:**
```json
{
  "version": "0.5.241",
  "build_date": "2025-06-22",
  "git_commit": "abc123def456",
  "build_environment": "production",
  "features": {
    "app_deployment": true,
    "dns_management": true,
    "p2p_networking": true,
    "registry_integration": true
  }
}
```

### Test APIs

#### Connection Test
**GET** `/test/connection`

Test network connectivity and response times.

**Response:**
```json
{
  "success": true,
  "response_time_ms": 15,
  "node_id": "node-001",
  "timestamp": "2025-06-22T12:00:00Z",
  "network_tests": {
    "registry_connection": "ok",
    "peer_connectivity": "ok",
    "dns_resolution": "ok"
  }
}
```

## Error Handling

### Standard Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request contains invalid parameters",
    "details": {
      "field": "replicas",
      "issue": "must be a positive integer"
    }
  },
  "timestamp": "2025-06-22T12:00:00Z",
  "request_id": "req-12345"
}
```

### Common Error Codes

- `INVALID_REQUEST`: Request validation failed
- `AUTHENTICATION_REQUIRED`: Authentication token missing or invalid
- `AUTHORIZATION_FAILED`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource does not exist
- `RESOURCE_CONFLICT`: Resource already exists or conflict detected
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Internal server error
- `SERVICE_UNAVAILABLE`: Service temporarily unavailable
- `NETWORK_ERROR`: Network connectivity issues
- `DEPLOYMENT_FAILED`: Application deployment failed

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Default**: 100 requests per minute per IP
- **App Management**: 10 deployments per hour
- **Data Operations**: 1000 requests per minute
- **Status Checks**: No limit (monitoring purposes)

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## WebSocket APIs

### Real-time Application Monitoring
**WebSocket** `/ws/apps/{app_id}/logs`

Stream real-time logs from application instances.

**Connection Example:**
```javascript
const ws = new WebSocket('ws://localhost:9999/ws/apps/app-12345/logs');
ws.onmessage = function(event) {
    const logEntry = JSON.parse(event.data);
    console.log(logEntry);
};
```

**Message Format:**
```json
{
  "timestamp": "2025-06-22T12:00:00Z",
  "level": "info",
  "message": "Request processed successfully",
  "instance_id": "inst-001",
  "node_id": "node-001",
  "metadata": {
    "request_id": "req-12345",
    "duration_ms": 45
  }
}
```

### Network Events
**WebSocket** `/ws/network/events`

Stream network-wide events and status changes.

**Event Types:**
- `node_joined`: New node joined the network
- `node_left`: Node left the network
- `app_deployed`: Application deployed
- `app_failed`: Application deployment failed
- `load_rebalanced`: Traffic rebalanced

## SDK and Client Libraries

### Python Client
```python
from voxacommunications_client import VoxaClient

client = VoxaClient("http://localhost:9999")
client.authenticate(token="your-auth-token")

# Deploy an application
app = client.apps.deploy(
    name="my-app",
    image="nginx:latest",
    replicas=2
)

# Monitor application
status = client.apps.get_status(app.id)
print(f"App status: {status.health}")
```

### CLI Tool
```bash
# Deploy application
voxa-cli app deploy --name my-app --image nginx:latest --replicas 2

# List applications
voxa-cli app list

# Scale application
voxa-cli app scale --app-id app-12345 --replicas 5

# Monitor logs
voxa-cli app logs --app-id app-12345 --follow
```

## OpenAPI Documentation

The API provides automatic OpenAPI (Swagger) documentation:

- **Interactive Docs**: `http://localhost:9999/docs`
- **OpenAPI JSON**: `http://localhost:9999/openapi.json`
- **ReDoc**: `http://localhost:9999/redoc`

## Examples and Tutorials

For practical examples and step-by-step tutorials, see:
- [Application Deployment Guide](APP_DEPLOYMENT.md)
- [Network Setup Tutorial](NETWORK_SETUP.md)
- [CLI Usage Examples](../examples/)

## Support and Community

- **GitHub Issues**: Report bugs and request features
- **Discord**: Join our community chat
- **Telegram**: Developer discussions
- **Documentation**: Comprehensive guides and references
