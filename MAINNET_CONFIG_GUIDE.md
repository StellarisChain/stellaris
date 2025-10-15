# Stellaris Chain - Mainnet Configuration Guide

## Overview
This guide provides recommended configurations for deploying Stellaris Chain in a production/mainnet environment with proper decentralization and treasury tax settings.

## Treasury Tax Configuration

### Via XML Configuration File
Edit `stellaris/config/block_config.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<BlockConfig>
    <ActivationBlock>0</ActivationBlock>
    
    <Treasury>
        <WalletAddress>E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH</WalletAddress>
        <TaxRate>0.25</TaxRate>        <!-- 25% tax rate -->
        <TaxInterval>25000</TaxInterval> <!-- Distribute every 25,000 blocks -->
    </Treasury>
    
    <Range minIndex="0" maxIndex="2500000">
        <Reward>64</Reward>
        <MaxDifficulty>100000</MaxDifficulty>
    </Range>
    <!-- Add more ranges as needed -->
</BlockConfig>
```

### Via Environment Variables (Fallback)
```bash
# These are used if XML configuration is not available
export TREASURY_WALLET="E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH"
export TREASURY_TAX_RATE="0.25"
export TREASURY_TAX_INTERVAL="25000"
```

### Tax Rate Recommendations
- **Testnet**: 0.25 (25%) - Current setting
- **Mainnet**: 0.10-0.25 (10-25%) - Adjust based on governance
- **Valid Range**: 0.0 to 1.0 (0% to 100%)

### Distribution Interval Recommendations
- **Fast Testing**: 100 blocks (~10 minutes)
- **Testnet**: 2,500 blocks (~4 hours at 6s/block)
- **Mainnet**: 25,000 blocks (~2 days at 6s/block)

## Network Decentralization Configuration

### Bootstrap Nodes Setup

#### Option 1: Environment Variable (Recommended for Production)
```bash
# Set multiple bootstrap nodes (comma-separated)
export STELLARIS_BOOTSTRAP_NODES="https://node1.stellaris.network,https://node2.stellaris.network,https://node3.stellaris.network,https://node4.stellaris.network,https://node5.stellaris.network"
```

#### Option 2: Code Configuration
Edit `stellaris/node/nodes_manager.py`:

```python
DEFAULT_BOOTSTRAP_NODES = [
    'https://node1.stellaris.network',
    'https://node2.stellaris.network',
    'https://node3.stellaris.network',
    'https://node4.stellaris.network',
    'https://node5.stellaris.network',
]
```

### Recommended Bootstrap Node Deployment

#### Geographic Distribution
Deploy bootstrap nodes across multiple regions:
- **North America**: 2 nodes
- **Europe**: 2 nodes
- **Asia**: 2 nodes
- **Other regions**: 1+ nodes

#### Infrastructure Requirements per Bootstrap Node
```
CPU: 4+ cores
RAM: 8+ GB
Storage: 100+ GB SSD
Network: 1 Gbps
Uptime: 99.9%+
```

#### Bootstrap Node URLs Format
```
https://bootstrap1.stellaris.network
https://bootstrap2.stellaris.network
https://bootstrap3.stellaris.network
```

### Node Configuration

#### Self URL Configuration
Each node should know its own public URL:

```bash
export STELLARIS_SELF_URL="https://your-node.example.com"
```

#### Peer Discovery Settings
Configured in `stellaris/node/nodes_manager.py`:

```python
ACTIVE_NODES_DELTA = 60 * 60 * 24 * 7  # Consider nodes active for 7 days
MAX_PEERS_COUNT = 200                    # Maximum peers to maintain
PEER_EXCHANGE_INTERVAL = 60 * 10        # Peer exchange every 10 minutes
PEER_EXCHANGE_COUNT = 20                 # Peers to exchange per request
MIN_PEERS_FOR_DISCOVERY = 5             # Min peers before bootstrap discovery
```

### Docker Compose Example for Multi-Node Setup

```yaml
version: '3.8'

services:
  node1:
    build: .
    environment:
      - STELLARIS_SELF_URL=http://node1:8000
      - STELLARIS_BOOTSTRAP_NODES=http://node1:8000,http://node2:8000,http://node3:8000
      - TREASURY_WALLET=E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH
      - TREASURY_TAX_RATE=0.25
      - TREASURY_TAX_INTERVAL=25000
    ports:
      - "8001:8000"
    volumes:
      - node1_data:/app/data

  node2:
    build: .
    environment:
      - STELLARIS_SELF_URL=http://node2:8000
      - STELLARIS_BOOTSTRAP_NODES=http://node1:8000,http://node2:8000,http://node3:8000
      - TREASURY_WALLET=E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH
      - TREASURY_TAX_RATE=0.25
      - TREASURY_TAX_INTERVAL=25000
    ports:
      - "8002:8000"
    volumes:
      - node2_data:/app/data

  node3:
    build: .
    environment:
      - STELLARIS_SELF_URL=http://node3:8000
      - STELLARIS_BOOTSTRAP_NODES=http://node1:8000,http://node2:8000,http://node3:8000
      - TREASURY_WALLET=E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH
      - TREASURY_TAX_RATE=0.25
      - TREASURY_TAX_INTERVAL=25000
    ports:
      - "8003:8000"
    volumes:
      - node3_data:/app/data

volumes:
  node1_data:
  node2_data:
  node3_data:
```

## Monitoring and Maintenance

### Health Checks

#### Peer Count Check
```bash
curl http://your-node:8000/get_nodes | jq '.result | length'
```
- **Healthy**: 20+ peers
- **Warning**: 10-20 peers
- **Critical**: < 10 peers

#### Treasury Status Check
```bash
# Check accumulated fees
curl http://your-node:8000/get_treasury_status | jq '.result.accumulated_fees'

# Check last distribution
curl http://your-node:8000/get_treasury_status | jq '.result.last_distribution_block'
```

### Monitoring Metrics

Track these metrics in your monitoring system:
1. **Peer Count**: Current number of active peers
2. **Peer Discovery Rate**: New peers discovered per hour
3. **Treasury Accumulated Fees**: Total fees awaiting distribution
4. **Treasury Distributions**: Number and amount of distributions
5. **Network Propagation Time**: Time for blocks/transactions to propagate
6. **Bootstrap Node Availability**: Uptime of bootstrap nodes

### Alerting Rules

```yaml
alerts:
  - name: LowPeerCount
    condition: peer_count < 10
    severity: warning
    
  - name: CriticalPeerCount
    condition: peer_count < 5
    severity: critical
    
  - name: BootstrapNodeDown
    condition: bootstrap_node_up == 0
    severity: critical
    
  - name: TreasuryDistributionFailed
    condition: treasury_distribution_error == 1
    severity: warning
```

## Security Considerations

### Rate Limiting
Current limits (can be adjusted in `stellaris/node/main.py`):
```python
@limiter.limit("30/minute")  # API endpoint limits
```

### Peer Reputation
The system includes peer reputation tracking:
- Good behavior increases reputation
- Bad behavior (failures, timeouts) decreases reputation
- Banned peers are automatically excluded

### DDoS Protection
Recommendations:
1. Use a reverse proxy (nginx, Caddy) with rate limiting
2. Enable fail2ban for repeated failed requests
3. Use CloudFlare or similar DDoS protection for bootstrap nodes
4. Implement connection limits per IP

## Upgrade Path

### From Centralized to Decentralized

1. **Phase 1**: Add bootstrap nodes to environment variable
```bash
export STELLARIS_BOOTSTRAP_NODES="https://main.stellaris.dev,https://node2.stellaris.dev"
```

2. **Phase 2**: Deploy additional bootstrap nodes
   - Set up 3-5 additional nodes
   - Add them to the bootstrap list
   - Update all nodes with new list

3. **Phase 3**: Monitor peer discovery
   - Check peer counts increase
   - Verify gossip protocol working
   - Ensure blocks/transactions propagate

4. **Phase 4**: Remove main node dependency
   - Remove hardcoded main node references
   - Rely fully on peer discovery

## Testing Before Mainnet

### Test Scenarios

1. **Treasury Tax Test**
```bash
python test_treasury_tax.py
```

2. **Peer Discovery Test**
```bash
python test_peer_discovery.py
```

3. **Multi-Node Network Test**
```bash
docker-compose up -d
# Wait for nodes to connect
docker-compose logs -f
# Verify peer exchange
curl http://localhost:8001/get_nodes
curl http://localhost:8002/get_nodes
curl http://localhost:8003/get_nodes
```

4. **Load Test**
- Generate transactions
- Monitor propagation time
- Check network stays synchronized

## Support and Troubleshooting

### Common Issues

#### Issue: Node has no peers
**Solution**: 
- Check STELLARIS_BOOTSTRAP_NODES is set correctly
- Verify bootstrap nodes are accessible
- Check firewall allows outbound connections

#### Issue: Peers not propagating
**Solution**:
- Check peer discovery loop is running
- Verify nodes have public URLs set
- Check network connectivity between nodes

#### Issue: Treasury distribution not happening
**Solution**:
- Verify tax_interval configuration
- Check accumulated fees > 0
- Ensure treasury wallet address is valid

### Debug Mode
Enable debug logging:
```bash
export STELLARIS_LOG_LEVEL=DEBUG
```

## Conclusion

Following this configuration guide will ensure your Stellaris Chain deployment is:
- ✅ Properly decentralized with no single point of failure
- ✅ Configured with accurate treasury tax collection
- ✅ Ready for production/mainnet deployment
- ✅ Monitored and maintainable

For additional support, refer to the main documentation or open an issue on GitHub.
