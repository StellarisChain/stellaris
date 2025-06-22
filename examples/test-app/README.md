# VoxaCommunications Test App

A simple test application for demonstrating the VoxaCommunications decentralized app deployment system.

## Features

- **Web Interface**: Simple HTML dashboard showing app status
- **Health Check Endpoint**: `/health` for monitoring
- **Metrics Endpoint**: `/metrics` for performance data
- **Info Endpoint**: `/info` for app metadata
- **Environment Integration**: Displays VoxaCommunications environment variables

## Building

```bash
cd examples/test-app
docker build -t voxa-test-app .
```

## Running Locally

```bash
docker run -p 8080:8080 \
  -e VOXA_APP_ID=test-app-123 \
  -e VOXA_INSTANCE_ID=instance-456 \
  -e VOXA_NODE_ID=node-789 \
  voxa-test-app
```

Then visit http://localhost:8080

## Deploying via VoxaCommunications

```bash
curl -X POST http://localhost:9999/api/apps/deploy_app \
  -H "Content-Type: application/json" \
  -d '{
    "name": "voxa-test-app",
    "version": "1.0.0",
    "image": "voxa-test-app:latest",
    "replicas": 2,
    "resource_requirements": {
        "memory": "128m",
        "cpu": "0.2"
    },
    "network_config": {
        "ports": {"8080/tcp": {"HostPort": "8080"}}
    }
  }'
```

## Endpoints

- `/` - Main dashboard
- `/health` - Health check (JSON)
- `/metrics` - Performance metrics (JSON)  
- `/info` - Application information (JSON)

## Environment Variables

The app responds to these VoxaCommunications environment variables:

- `VOXA_APP_ID` - Application identifier
- `VOXA_INSTANCE_ID` - Instance identifier
- `VOXA_NODE_ID` - Node identifier
- `HOST` - Bind host (default: 0.0.0.0)
- `PORT` - Bind port (default: 8080)
