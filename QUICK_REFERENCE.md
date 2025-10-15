# Quick Reference - Treasury Tax & Network Decentralization

## ✅ What Was Fixed

### Treasury Tax System
- ✅ **Decimal Precision**: All amounts stored as strings to prevent precision loss
- ✅ **Validation**: Checks for negative amounts and sufficient funds
- ✅ **Edge Cases**: Handles invalid tax rates, block 0, and interval changes
- ✅ **Error Recovery**: Graceful handling of distribution failures

### Network Decentralization
- ✅ **Multiple Bootstrap Nodes**: Support for 5+ bootstrap nodes (no single point of failure)
- ✅ **Peer Discovery**: Automatic discovery from bootstrap nodes
- ✅ **Gossip Protocol**: Peer exchange mechanism for distributed discovery
- ✅ **Background Discovery**: Runs every 10 minutes, increases frequency when low on peers
- ✅ **Decentralized Sync**: No longer depends on single main node

## 🚀 Quick Start

### Set Bootstrap Nodes
```bash
export STELLARIS_BOOTSTRAP_NODES="https://node1.stellaris.network,https://node2.stellaris.network,https://node3.stellaris.network"
```

### Set Treasury Configuration
```bash
export TREASURY_WALLET="E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH"
export TREASURY_TAX_RATE="0.25"
export TREASURY_TAX_INTERVAL="25000"
```

### Run Tests
```bash
# Test treasury tax system
python test_treasury_tax.py

# Test peer discovery
python test_peer_discovery.py
```

## 📊 Monitoring

### Check Peer Count
```bash
curl http://localhost:8000/get_nodes | jq '.result | length'
```
- Healthy: 20+ peers
- Warning: 10-20 peers  
- Critical: < 10 peers

### Check Treasury Status
```bash
# View accumulated fees
curl http://localhost:8000/get_treasury_status

# View distribution history
curl http://localhost:8000/get_treasury_distributions
```

## 🔧 Key Files Modified

1. `stellaris/database.py` - Treasury fee handling with validation
2. `stellaris/manager.py` - Tax calculation with proper Decimals
3. `stellaris/node/nodes_manager.py` - Peer discovery and gossip protocol
4. `stellaris/node/main.py` - Background peer discovery loop

## 📈 Production Checklist

- [ ] Deploy 5-10 bootstrap nodes across different regions
- [ ] Configure all nodes with bootstrap node list
- [ ] Set appropriate treasury tax rate (0.10-0.25)
- [ ] Set distribution interval (25,000 blocks for mainnet)
- [ ] Enable monitoring for peer count and treasury
- [ ] Set up alerts for low peer count (< 10)
- [ ] Configure DDoS protection for bootstrap nodes
- [ ] Test peer discovery in staging environment
- [ ] Verify treasury distributions work correctly
- [ ] Document node URLs and configuration

## 🎯 Key Metrics

| Metric | Target | Critical |
|--------|--------|----------|
| Peer Count | 20+ | < 10 |
| Bootstrap Nodes | 5+ | < 2 |
| Peer Discovery Rate | 10+/hour | 0/hour |
| Treasury Tax Rate | 0.25 | N/A |
| Distribution Interval | 25,000 blocks | N/A |

## 🔐 Security Features

- ✅ Peer reputation system
- ✅ Rate limiting on API endpoints
- ✅ Validation on all treasury operations
- ✅ No single point of failure
- ✅ Automatic peer banning for bad behavior

## 📚 Documentation

- `IMPROVEMENTS_SUMMARY.md` - Detailed changes and test results
- `MAINNET_CONFIG_GUIDE.md` - Complete configuration guide
- `test_treasury_tax.py` - Treasury tax test suite
- `test_peer_discovery.py` - Network decentralization tests

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| No peers | Check bootstrap nodes configured and accessible |
| Treasury not distributing | Verify tax_interval and accumulated fees > 0 |
| Precision errors | Already fixed - using string storage |
| Sync failing | Will try multiple peers automatically |

## ✨ Benefits

**Before:**
- ❌ Single main node (centralized)
- ❌ Manual peer management
- ❌ Potential precision loss in treasury
- ❌ No automatic peer discovery

**After:**
- ✅ Multiple bootstrap nodes (decentralized)
- ✅ Automatic peer discovery and maintenance
- ✅ Precise treasury calculations
- ✅ Gossip-based peer propagation
- ✅ Production-ready and scalable
