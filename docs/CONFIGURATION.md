# Configuration Guide

## Overview

VoxaCommunications-NetNode uses a flexible, hierarchical configuration system that allows you to customize every aspect of the node's behavior. This guide covers all configuration options, from basic setup to advanced production deployments.

## Configuration Hierarchy

The configuration system follows a priority order:

1. **Environment Variables** (highest priority)
2. **Command Line Arguments**
3. **Configuration Files**
4. **Default Values** (lowest priority)

## Configuration Files

### Main Configuration Files

#### `config/settings.json` - Core Settings
The primary configuration file containing essential node settings.

```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "testnet",
  "registry": {
    "url": "https://registry.voxacommunications.com",
    "auto_register": true,
    "heartbeat_interval": 30
  },
  "features": {
    "enable-app-deployment": true,
    "enable-dns": true,
    "enable-registry": true,
    "enable-p2p": true
  },
  "security": {
    "enable_tls": false,
    "cert_file": "",
    "key_file": "",
    "require_auth": false
  },
  "logging": {
    "level": "info",
    "file": "logs/node.log",
    "max_size_mb": 100,
    "backup_count": 5
  }
}
```

#### `config/dev.json` - Development Settings
Development-specific overrides and debugging options.

```json
{
  "reload": true,
  "log_level": "debug",
  "enable_cors": true,
  "development_mode": true,
  "disable_auth": true,
  "enable_test_endpoints": true,
  "debug_networking": true
}
```

#### `config/p2p.json` - P2P Networking
Peer-to-peer networking configuration.

```json
{
  "listen_port": 9000,
  "max_connections": 50,
  "connection_timeout": 30,
  "enable_upnp": true,
  "enable_nat_traversal": true,
  "bootstrap_nodes": [
    "bootstrap1.voxacommunications.com:9000",
    "bootstrap2.voxacommunications.com:9000"
  ],
  "protocols": {
    "kytan": {
      "enabled": true,
      "port": 9001,
      "max_clients": 100
    },
    "ssu": {
      "enabled": true,
      "port": 9002,
      "timeout": 30
    }
  }
}
```

#### `config/apps.json` - Application Deployment
Configuration for the decentralized application platform.

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
    "allowed_registries": [
      "docker.io",
      "ghcr.io",
      "quay.io"
    ],
    "blocked_registries": [],
    "scan_images": true
  },
  "load_balancer": {
    "algorithm": "round_robin",
    "health_check_path": "/health",
    "health_check_interval": 10,
    "unhealthy_threshold": 3,
    "healthy_threshold": 2
  },
  "auto_scaling": {
    "enabled": true,
    "min_replicas": 1,
    "max_replicas": 10,
    "cpu_target_percent": 70,
    "memory_target_percent": 80,
    "scale_up_cooldown": 300,
    "scale_down_cooldown": 600
  }
}
```

#### `config/discovery.json` - Network Discovery
Node and service discovery configuration.

```json
{
  "discovery_interval": 60,
  "discovery_timeout": 10,
  "max_discovery_attempts": 3,
  "enable_mdns": true,
  "enable_dns_sd": true,
  "discovery_methods": [
    "registry",
    "bootstrap",
    "mdns",
    "peer_exchange"
  ],
  "cache": {
    "enabled": true,
    "ttl": 300,
    "max_entries": 1000
  }
}
```

#### `config/data.json` - Data Storage
Distributed data storage configuration.

```json
{
  "storage_backend": "filesystem",
  "data_dir": "data/storage",
  "replication_factor": 3,
  "consistency_level": "quorum",
  "encryption": {
    "enabled": true,
    "algorithm": "AES-256-GCM",
    "key_rotation_interval": 86400
  },
  "compression": {
    "enabled": true,
    "algorithm": "zstd",
    "level": 3
  },
  "cleanup": {
    "enabled": true,
    "interval": 3600,
    "max_age_days": 30
  }
}
```

#### `config/cryptography.json` - Cryptographic Settings
Cryptographic configuration for security features.

```json
{
  "key_generation": {
    "algorithm": "RSA",
    "key_size": 2048,
    "curve": "secp256k1"
  },
  "signing": {
    "algorithm": "ECDSA",
    "hash_function": "SHA256"
  },
  "encryption": {
    "symmetric_algorithm": "AES-256-GCM",
    "asymmetric_algorithm": "RSA-OAEP"
  },
  "key_exchange": {
    "algorithm": "ECDH",
    "curve": "X25519"
  }
}
```

#### `config/kytan.json` - Kytan Protocol
Kytan networking protocol configuration.

```json
{
  "enabled": true,
  "server": {
    "host": "0.0.0.0",
    "port": 9001,
    "max_clients": 100,
    "timeout": 30
  },
  "client": {
    "connection_timeout": 10,
    "retry_attempts": 3,
    "retry_delay": 5
  },
  "protocol": {
    "version": "1.0",
    "compression": true,
    "encryption": true
  }
}
```

#### `config/storage.json` - Storage Backend
Storage system configuration.

```json
{
  "backend": "filesystem",
  "filesystem": {
    "base_path": "data",
    "create_dirs": true,
    "sync_on_write": false
  },
  "database": {
    "type": "sqlite",
    "path": "data/voxa.db",
    "connection_pool_size": 10
  },
  "cache": {
    "enabled": true,
    "type": "memory",
    "max_size_mb": 256,
    "ttl": 3600
  }
}
```

## Environment Variables

### Core Variables

```bash
# Network Configuration
export VOXA_HOST="0.0.0.0"
export VOXA_PORT=9999
export VOXA_NETWORK_LEVEL="mainnet"

# Registry Configuration
export VOXA_REGISTRY_URL="https://registry.voxacommunications.com"
export VOXA_REGISTRY_EMAIL="your-email@example.com"
export VOXA_REGISTRY_PASSWORD="your-password"
export VOXA_REGISTRY_CODE="your-2fa-code"

# Feature Flags
export VOXA_ENABLE_APP_DEPLOYMENT=true
export VOXA_ENABLE_DNS=true
export VOXA_ENABLE_REGISTRY=true

# Development
export VOXA_DEBUG=false
export VOXA_LOG_LEVEL="info"
export NODE_ENV="production"
```

### Application-Specific Variables

```bash
# App Deployment
export VOXA_MAX_APPS_PER_NODE=10
export VOXA_DEFAULT_MEMORY_LIMIT="512m"
export VOXA_DEFAULT_CPU_LIMIT="1.0"
export VOXA_DOCKER_NETWORK="voxacomms-apps"

# Security
export VOXA_ENABLE_TLS=true
export VOXA_CERT_FILE="/path/to/cert.pem"
export VOXA_KEY_FILE="/path/to/key.pem"
export VOXA_REQUIRE_AUTH=true

# Storage
export VOXA_DATA_DIR="data"
export VOXA_STORAGE_BACKEND="filesystem"
export VOXA_REPLICATION_FACTOR=3
```

## Configuration Validation

The system validates configuration using JSON schemas:

### Example Validation Schema
```json
{
  "type": "object",
  "properties": {
    "host": {
      "type": "string",
      "format": "hostname"
    },
    "port": {
      "type": "integer",
      "minimum": 1,
      "maximum": 65535
    },
    "node-network-level": {
      "type": "string",
      "enum": ["testnet", "mainnet", "devnet"]
    }
  },
  "required": ["host", "port", "node-network-level"]
}
```

### Configuration Validation CLI
```bash
# Validate configuration
python src/cli.py config validate

# Check specific config file
python src/cli.py config validate --file config/settings.json

# Show resolved configuration
python src/cli.py config show
```

## Environment-Specific Configurations

### Development Environment

#### `config/dev.json`
```json
{
  "host": "127.0.0.1",
  "port": 9999,
  "node-network-level": "testnet",
  "reload": true,
  "log_level": "debug",
  "development_mode": true,
  "features": {
    "enable-app-deployment": true,
    "enable-dns": false,
    "enable-registry": false
  }
}
```

### Testing Environment

#### `config/test.json`
```json
{
  "host": "127.0.0.1",
  "port": 0,
  "node-network-level": "testnet",
  "features": {
    "enable-app-deployment": true,
    "enable-dns": false,
    "enable-registry": false
  },
  "logging": {
    "level": "error"
  }
}
```

### Production Environment

#### `config/production.json`
```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "mainnet",
  "security": {
    "enable_tls": true,
    "cert_file": "/etc/ssl/certs/voxa.crt",
    "key_file": "/etc/ssl/private/voxa.key",
    "require_auth": true
  },
  "registry": {
    "url": "https://registry.voxacommunications.com",
    "auto_register": true,
    "heartbeat_interval": 30
  },
  "features": {
    "enable-app-deployment": true,
    "enable-dns": true,
    "enable-registry": true
  },
  "logging": {
    "level": "info",
    "file": "/var/log/voxa/node.log"
  }
}
```

## Advanced Configuration

### Load Balancing Configuration

```json
{
  "load_balancer": {
    "algorithm": "weighted_round_robin",
    "weights": {
      "node-001": 3,
      "node-002": 2,
      "node-003": 1
    },
    "health_check": {
      "enabled": true,
      "path": "/health",
      "interval": 10,
      "timeout": 5,
      "unhealthy_threshold": 3,
      "healthy_threshold": 2
    },
    "circuit_breaker": {
      "enabled": true,
      "failure_threshold": 5,
      "recovery_timeout": 60,
      "half_open_requests": 3
    }
  }
}
```

### Security Hardening

```json
{
  "security": {
    "enable_tls": true,
    "tls_version": "1.3",
    "cipher_suites": [
      "TLS_AES_256_GCM_SHA384",
      "TLS_CHACHA20_POLY1305_SHA256"
    ],
    "hsts": {
      "enabled": true,
      "max_age": 31536000,
      "include_subdomains": true
    },
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 100,
      "burst_size": 20
    },
    "firewall": {
      "enabled": true,
      "allowed_ips": ["10.0.0.0/8", "172.16.0.0/12"],
      "blocked_ips": []
    }
  }
}
```

### Monitoring and Observability

```json
{
  "monitoring": {
    "metrics": {
      "enabled": true,
      "endpoint": "/metrics",
      "interval": 30
    },
    "tracing": {
      "enabled": true,
      "jaeger_endpoint": "http://jaeger:14268/api/traces",
      "sample_rate": 0.1
    },
    "logging": {
      "structured": true,
      "format": "json",
      "level": "info",
      "outputs": ["stdout", "file"],
      "file": {
        "path": "logs/node.log",
        "max_size_mb": 100,
        "max_files": 10
      }
    }
  }
}
```

### Resource Management

```json
{
  "resources": {
    "limits": {
      "max_memory_mb": 2048,
      "max_cpu_percent": 80,
      "max_connections": 1000,
      "max_file_descriptors": 65536
    },
    "reservations": {
      "system_memory_mb": 512,
      "system_cpu_percent": 10
    },
    "cleanup": {
      "enabled": true,
      "interval": 3600,
      "max_log_age_days": 7,
      "max_temp_age_hours": 24
    }
  }
}
```

## Configuration Templates

### Minimal Configuration

```json
{
  "host": "127.0.0.1",
  "port": 9999,
  "node-network-level": "testnet"
}
```

### High-Performance Configuration

```json
{
  "host": "0.0.0.0",
  "port": 9999,
  "node-network-level": "mainnet",
  "p2p": {
    "max_connections": 200,
    "connection_timeout": 10
  },
  "apps": {
    "max_apps_per_node": 50,
    "enable_auto_scaling": true,
    "health_check_interval": 5
  },
  "resources": {
    "limits": {
      "max_memory_mb": 8192,
      "max_cpu_percent": 90
    }
  }
}
```

### Secure Configuration

```json
{
  "host": "0.0.0.0",
  "port": 443,
  "node-network-level": "mainnet",
  "security": {
    "enable_tls": true,
    "cert_file": "/etc/ssl/certs/voxa.crt",
    "key_file": "/etc/ssl/private/voxa.key",
    "require_auth": true,
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60
    }
  },
  "apps": {
    "security": {
      "allow_privileged_containers": false,
      "enable_resource_limits": true,
      "scan_images": true
    }
  }
}
```

## Configuration Management

### Configuration Backup

```bash
# Backup current configuration
cp -r config config.backup.$(date +%Y%m%d_%H%M%S)

# Restore configuration
cp -r config.backup.20250622_120000 config
```

### Configuration Validation Script

```python
#!/usr/bin/env python3
import json
import jsonschema

def validate_config(config_file, schema_file):
    with open(config_file) as f:
        config = json.load(f)
    
    with open(schema_file) as f:
        schema = json.load(f)
    
    try:
        jsonschema.validate(config, schema)
        print(f"✅ {config_file} is valid")
    except jsonschema.ValidationError as e:
        print(f"❌ {config_file} validation failed: {e}")

if __name__ == "__main__":
    validate_config("config/settings.json", "schemas/settings.schema.json")
```

### Dynamic Configuration Updates

```bash
# Update configuration via API
curl -X POST http://localhost:9999/admin/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "logging": {
      "level": "debug"
    }
  }'

# Reload configuration
curl -X POST http://localhost:9999/admin/config/reload
```

## Troubleshooting Configuration

### Common Configuration Issues

#### 1. Port Conflicts
```bash
# Check if port is in use
sudo lsof -i :9999

# Use alternative port
export VOXA_PORT=9998
```

#### 2. Permission Issues
```bash
# Fix file permissions
chmod 644 config/*.json
chmod 755 config/

# Fix directory ownership
sudo chown -R $USER:$USER config/
```

#### 3. JSON Syntax Errors
```bash
# Validate JSON syntax
python -m json.tool config/settings.json

# Use JSON linter
jq . config/settings.json
```

#### 4. Environment Variable Issues
```bash
# Check environment variables
env | grep VOXA_

# Unset problematic variables
unset VOXA_PROBLEMATIC_VAR
```

### Configuration Debugging

```bash
# Show resolved configuration
python src/cli.py config show

# Validate all configuration files
python src/cli.py config validate-all

# Debug configuration loading
python src/cli.py config debug
```

### Configuration Monitoring

```bash
# Monitor configuration changes
inotifywait -m config/ -e modify,create,delete

# Log configuration changes
python src/cli.py config watch
```

## Best Practices

### 1. Configuration Organization
- Keep environment-specific configs separate
- Use environment variables for secrets
- Document all configuration options
- Version control configuration files

### 2. Security Considerations
- Never commit secrets to version control
- Use secure defaults
- Regularly rotate encryption keys
- Enable authentication in production

### 3. Performance Optimization
- Tune resource limits based on hardware
- Configure appropriate timeouts
- Enable compression where beneficial
- Use caching strategically

### 4. Monitoring and Maintenance
- Regularly validate configuration
- Monitor configuration drift
- Backup configurations before changes
- Test configuration changes in staging

## Configuration Reference

### Complete Configuration Options

For a complete reference of all configuration options, see the [Configuration Schema](../schemas/) directory which contains JSON schemas for each configuration file.

### Environment Variable Reference

All configuration options can be overridden using environment variables with the `VOXA_` prefix. For nested options, use underscores to separate levels:

```bash
# config.registry.url
export VOXA_REGISTRY_URL="https://registry.example.com"

# config.apps.max_apps_per_node
export VOXA_APPS_MAX_APPS_PER_NODE=20

# config.security.enable_tls
export VOXA_SECURITY_ENABLE_TLS=true
```

This comprehensive configuration system provides the flexibility needed for various deployment scenarios while maintaining security and performance best practices.
