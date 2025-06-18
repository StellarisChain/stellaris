#!/bin/bash

# Multi-Node Development Environment
# Runs multiple VoxaCommunications-NetNode instances for testing

set -e

# Configuration
DEFAULT_NODE_COUNT=3
BASE_API_PORT=9999
BASE_P2P_PORT=9000
NODE_COUNT=${1:-$DEFAULT_NODE_COUNT}

# Timing configuration for slow startup nodes
NODE_STARTUP_DELAY=5        # Delay between starting each node
HEALTH_CHECK_DELAY=70       # Wait time before starting health checks (45-60s + buffer)
HEALTH_CHECK_TIMEOUT=10     # Timeout for each health check attempt
HEALTH_CHECK_RETRIES=5      # Number of retry attempts per node

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== VoxaCommunications Multi-Node Development Environment ===${NC}"
echo -e "${YELLOW}Starting $NODE_COUNT development nodes...${NC}"
echo -e "${CYAN}Note: Nodes take 45-60 seconds to fully initialize${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Create dev-configs directory if it doesn't exist
DEV_CONFIG_DIR="$PROJECT_ROOT/dev-configs"
mkdir -p "$DEV_CONFIG_DIR"

# Array to store process IDs
declare -a NODE_PIDS=()
declare -a NODE_PORTS=()

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down all nodes...${NC}"
    for pid in "${NODE_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}Killing process $pid${NC}"
            kill "$pid" 2>/dev/null || true
        fi
    done
    
    # Clean up config directories
    echo -e "${YELLOW}Cleaning up temporary configurations...${NC}"
    rm -rf "$DEV_CONFIG_DIR"
    
    echo -e "${GREEN}All nodes stopped.${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Function to create node configuration
create_node_config() {
    local node_id=$1
    local api_port=$2
    local p2p_port=$3
    local config_dir="$DEV_CONFIG_DIR/node-$node_id"
    
    echo -e "${BLUE}Creating configuration for Node $node_id (API: $api_port, P2P: $p2p_port)${NC}"
    
    # Create node-specific config directory
    mkdir -p "$config_dir"
    
    # Copy base configurations
    cp -r "$PROJECT_ROOT/config/"* "$config_dir/"
    
    # Update settings.json
    cat > "$config_dir/settings.json" << EOF
{
    "node-network-level": "testnet",
    "node-autoupdate-config": true,
    "node-id": "dev-node-$node_id",
    "server-settings": {
        "host": "0.0.0.0",
        "port": $api_port
    },
    "features": {
        "enable-transaction-fee": true,
        "enable-transaction-signing": true,
        "enable-block-validation": true,
        "enable-async-operations": true,
        "enable-transaction-history": true,
        "enable-network-sync": true,
        "enable-wallet-management": true,
        "enable-smart-contracts": false,
        "enable-multi-signature": false,
        "enable-kytan-vpn": true,
        "enable-upnpc-port-forwarding": false,
        "enable-ssu": true,
        "enable-dns": true
    }
}
EOF

    # Update p2p.json
    cat > "$config_dir/p2p.json" << EOF
{
    "host": "0.0.0.0",
    "port": $p2p_port,
    "max_peers": 100,
    "max_ssu_loop_index": 5,
    "max_connections": 50,
    "topics": [
        "voxacomms-discovery",
        "voxacomms-relay", 
        "voxacomms-node"
    ],
    "stun_servers": [],
    "replication_factor": 3,
    "routing_table_size": 1000,
    "heartbeat_interval": 30,
    "topology_update_interval": 60,
    "message_ttl": 30,
    "connection_timeout": 10,
    "dht_k_bucket_size": 20,
    "dht_alpha": 3,
    "enable_dht": true,
    "max_file_size": 1048576,
    "auto_discovery": true,
    "security": {
        "enable_encryption": true,
        "allow_anonymous": true,
        "max_message_rate": 100
    }
}
EOF

    # Update discovery.json for better multi-node testing
    cat > "$config_dir/discovery.json" << EOF
{
    "enabled": true,
    "timeout": 3.0,
    "max_workers": 20,
    "cache_duration": 300,
    "scan_local_only": true,
    "allow_public_ip_discovery": false,
    "rate_limit_public_scans": true,
    "public_scan_delay_ms": 100,
    "max_public_hosts_per_range": 50,
    "node_ports": [9000, 9001, 9002, 9003, 9004],
    "relay_ports": [8080, 8081, 3000, 3001, 3002],
    "networks_to_scan": ["127.0.0.0/24", "192.168.0.0/24", "10.0.0.0/24"]
}
EOF
}

# Function to start a node
start_node() {
    local node_id=$1
    local api_port=$2
    local p2p_port=$3
    local config_dir="$DEV_CONFIG_DIR/node-$node_id"
    
    echo -e "${GREEN}Starting Node $node_id...${NC}"
    
    # Set environment variables for this node
    export NODE_ID="dev-node-$node_id"
    export CONFIG_DIR="$config_dir"
    export PYTHONPATH="${PYTHONPATH}:$PROJECT_ROOT:$PROJECT_ROOT/src"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        python -m venv .venv
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Install requirements
    python -m pip install -r requirements.txt > /dev/null 2>&1
    
    # Start the node in background
    cd "$PROJECT_ROOT"
    
    # Use a custom config path
    UVICORN_CMD="uvicorn src.main:app --host 0.0.0.0 --port $api_port"
    
    # Set config path environment variable
    export VOXA_CONFIG_PATH="$config_dir"
    
    echo -e "${BLUE}Node $node_id command: $UVICORN_CMD${NC}"
    echo -e "${BLUE}Node $node_id config: $config_dir${NC}"
    
    # Start node and capture PID
    $UVICORN_CMD > "logs/node-$node_id.log" 2>&1 &
    local node_pid=$!
    
    NODE_PIDS+=("$node_pid")
    NODE_PORTS+=("$api_port:$p2p_port")
    
    echo -e "${GREEN}Node $node_id started with PID $node_pid${NC}"
    echo -e "${GREEN}  API Port: $api_port${NC}"
    echo -e "${GREEN}  P2P Port: $p2p_port${NC}"
    echo -e "${GREEN}  Log: logs/node-$node_id.log${NC}"
    
    # Check if process started successfully
    sleep 2
    if ! kill -0 "$node_pid" 2>/dev/null; then
        echo -e "${RED}✗ Node $node_id failed to start!${NC}"
        echo -e "${RED}Check logs/node-$node_id.log for details${NC}"
        return 1
    fi
    
    echo -e "${CYAN}Node $node_id process is running (initializing...)${NC}"
}

# Enhanced function to check node health with retries
check_node_health() {
    local node_id=$1
    local api_port=$2
    local retries=$3
    
    echo -e "${YELLOW}Checking Node $node_id health (may take up to $((retries * HEALTH_CHECK_TIMEOUT)) seconds)...${NC}"
    
    for ((attempt=1; attempt<=retries; attempt++)); do
        echo -e "${CYAN}  Attempt $attempt/$retries for Node $node_id...${NC}"
        
        # Try multiple endpoints to check if node is responding
        local endpoints=("/status/health" "/info/program_stats" "/" "/docs")
        local node_responding=false
        
        for endpoint in "${endpoints[@]}"; do
            if timeout "$HEALTH_CHECK_TIMEOUT" curl -s -f "http://127.0.0.1:$api_port$endpoint" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Node $node_id is responding on $endpoint${NC}"
                node_responding=true
                break
            fi
        done
        
        if [ "$node_responding" = true ]; then
            return 0
        fi
        
        if [ $attempt -lt $retries ]; then
            echo -e "${YELLOW}  Node $node_id not ready yet, waiting 10 seconds...${NC}"
            sleep 10
        fi
    done
    
    echo -e "${RED}✗ Node $node_id health check failed after $retries attempts${NC}"
    echo -e "${RED}  Check logs/node-$node_id.log for startup issues${NC}"
    return 1
}

# Function to display startup progress
show_startup_progress() {
    local total_wait=$1
    local interval=5
    
    echo -e "\n${CYAN}Waiting for nodes to initialize (${total_wait}s total)...${NC}"
    
    for ((i=interval; i<=total_wait; i+=interval)); do
        local remaining=$((total_wait - i))
        echo -e "${YELLOW}Startup progress: ${i}s/${total_wait}s (${remaining}s remaining)${NC}"
        sleep $interval
    done
    
    echo -e "${GREEN}Startup wait period complete, beginning health checks...${NC}"
}

# Main execution
echo -e "${YELLOW}Setting up $NODE_COUNT development nodes...${NC}"

# Create logs directory
mkdir -p logs

# Start nodes with delays between each
for ((i=1; i<=NODE_COUNT; i++)); do
    api_port=$((BASE_API_PORT + i - 1))
    p2p_port=$((BASE_P2P_PORT + i - 1))
    
    create_node_config "$i" "$api_port" "$p2p_port"
    start_node "$i" "$api_port" "$p2p_port"
    
    # Add delay between node starts (except for the last node)
    if [ $i -lt $NODE_COUNT ]; then
        echo -e "${CYAN}Waiting ${NODE_STARTUP_DELAY}s before starting next node...${NC}"
        sleep $NODE_STARTUP_DELAY
    fi
done

echo -e "\n${GREEN}All $NODE_COUNT nodes started!${NC}"

# Show progress during startup wait
show_startup_progress $HEALTH_CHECK_DELAY

# Health checks with retries
echo -e "\n${YELLOW}Performing health checks with retries...${NC}"
healthy_nodes=0
for ((i=1; i<=NODE_COUNT; i++)); do
    api_port=$((BASE_API_PORT + i - 1))
    if check_node_health "$i" "$api_port" "$HEALTH_CHECK_RETRIES"; then
        ((healthy_nodes++))
    fi
done

# Display final status
echo -e "\n${BLUE}=== Development Network Status ===${NC}"
echo -e "${GREEN}Healthy nodes: $healthy_nodes/$NODE_COUNT${NC}"

if [ $healthy_nodes -eq $NODE_COUNT ]; then
    echo -e "${GREEN}🎉 All nodes are healthy and ready!${NC}"
elif [ $healthy_nodes -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Some nodes may still be initializing. Check logs for details.${NC}"
else
    echo -e "${RED}❌ No nodes are responding. Check logs for startup issues.${NC}"
fi

echo -e "\n${YELLOW}Node Information:${NC}"
for ((i=1; i<=NODE_COUNT; i++)); do
    api_port=$((BASE_API_PORT + i - 1))
    p2p_port=$((BASE_P2P_PORT + i - 1))
    echo -e "${GREEN}Node $i:${NC}"
    echo -e "  API:    http://127.0.0.1:$api_port"
    echo -e "  P2P:    127.0.0.1:$p2p_port"
    echo -e "  Health: http://127.0.0.1:$api_port/status/health"
    echo -e "  Stats:  http://127.0.0.1:$api_port/info/program_stats"
    echo -e "  Logs:   tail -f logs/node-$i.log"
done

echo -e "\n${YELLOW}Useful commands:${NC}"
echo -e "${BLUE}# Test discovery between nodes:${NC}"
echo -e "python test_discovery.py"
echo -e "\n${BLUE}# Check all node APIs:${NC}"
for ((i=1; i<=NODE_COUNT; i++)); do
    api_port=$((BASE_API_PORT + i - 1))
    echo -e "curl http://127.0.0.1:$api_port/status/health"
done

echo -e "\n${BLUE}# Monitor all logs:${NC}"
echo -e "tail -f logs/node-*.log"

echo -e "\n${BLUE}# Check process status:${NC}"
echo -e "ps aux | grep uvicorn"

echo -e "\n${RED}Press Ctrl+C to stop all nodes${NC}"

# Keep script running and monitor node health
echo -e "\n${CYAN}Monitoring nodes... (Press Ctrl+C to stop)${NC}"
while true; do
    sleep 30
    
    # Check if any nodes have died
    dead_nodes=0
    for i in "${!NODE_PIDS[@]}"; do
        pid="${NODE_PIDS[$i]}"
        if ! kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}Node $((i+1)) (PID: $pid) has stopped unexpectedly${NC}"
            unset NODE_PIDS[$i]
            ((dead_nodes++))
        fi
    done
    
    # If all nodes are dead, exit
    if [ ${#NODE_PIDS[@]} -eq 0 ]; then
        echo -e "${RED}All nodes have stopped. Exiting...${NC}"
        cleanup
    elif [ $dead_nodes -gt 0 ]; then
        echo -e "${YELLOW}$dead_nodes node(s) have stopped. Remaining: ${#NODE_PIDS[@]}${NC}"
    fi
done