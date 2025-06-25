#!/usr/bin/env python3
"""
Fix sync issues by manually connecting your local node to the main network
and pushing your mined blocks
"""
import requests
import json
import sys
import time

def check_nodes_connectivity():
    """Check what nodes your local node knows about"""
    try:
        local_url = "http://localhost:3006"
        response = requests.get(f"{local_url}/get_nodes", timeout=10)
        result = response.json()
        if result['ok']:
            print(f"Known nodes: {result['result']}")
            return result['result']
        else:
            print(f"Error getting nodes: {result}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def add_main_node_to_local():
    """Add the main network node to your local node's peer list"""
    try:
        local_url = "http://localhost:3006"
        main_node = "https://stellaris-node.connor33341.dev"
        
        print(f"Adding {main_node} to local node...")
        response = requests.get(f"{local_url}/add_node?url={main_node}", timeout=10)
        result = response.json()
        print(f"Add node result: {result}")
        return result.get('ok', False)
    except Exception as e:
        print(f"Error adding node: {e}")
        return False

def force_sync_with_main_network():
    """Force sync local node with main network"""
    try:
        local_url = "http://localhost:3006"
        main_node = "https://stellaris-node.connor33341.dev"
        
        print(f"Forcing sync with {main_node}...")
        response = requests.get(f"{local_url}/sync_blockchain?node_url={main_node}", timeout=30)
        result = response.json() if response.content else None
        print(f"Sync result: {result}")
        return True
    except Exception as e:
        print(f"Error during sync: {e}")
        return False

def get_local_blocks(start_block=1, count=100):
    """Get blocks from local node to push to main network"""
    local_url = "http://localhost:3006"
    blocks = []
    
    print(f"Getting local blocks {start_block} to {start_block + count}...")
    for block_id in range(start_block, start_block + count):
        try:
            response = requests.get(f"{local_url}/get_block?block={block_id}", timeout=5)
            result = response.json()
            if result['ok']:
                block_data = result['result']
                blocks.append({
                    'id': block_id,
                    'block': block_data['block'],
                    'transactions': block_data['transactions'] or []
                })
                print(f"  ✓ Got block {block_id}")
            else:
                print(f"  ✗ Block {block_id} not found")
                break
        except Exception as e:
            print(f"  ✗ Error getting block {block_id}: {e}")
            break
    
    return blocks

def push_blocks_to_main_network(blocks):
    """Push local blocks to main network"""
    main_node = "https://stellaris-node.connor33341.dev"
    success_count = 0
    
    print(f"Pushing {len(blocks)} blocks to main network...")
    for block_data in blocks:
        try:
            block_id = block_data['id']
            block_content = block_data['block']['content']
            transactions = block_data['transactions']
            
            push_data = {
                'block_content': block_content,
                'txs': transactions,
                'id': block_id
            }
            
            print(f"  Pushing block {block_id}...")
            response = requests.post(f"{main_node}/push_block", 
                                   json=push_data, 
                                   headers={'Content-Type': 'application/json'},
                                   timeout=20)
            result = response.json()
            
            if result.get('ok', False):
                print(f"  ✓ Block {block_id} accepted by main network")
                success_count += 1
            else:
                print(f"  ✗ Block {block_id} rejected: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ✗ Error pushing block {block_data['id']}: {e}")
    
    return success_count

def manual_propagate_recent_blocks():
    """Manually propagate recent blocks to main network"""
    print("=== MANUAL BLOCK PROPAGATION ===")
    
    # Get recent blocks (last 10 blocks)
    try:
        local_response = requests.get("http://localhost:3006/get_mining_info", timeout=10)
        local_info = local_response.json()['result']
        current_block = local_info['last_block']['id']
        start_block = max(1, current_block - 9)  # Last 10 blocks
        
        print(f"Current local block: {current_block}")
        print(f"Will try to push blocks {start_block} to {current_block}")
        
        blocks = get_local_blocks(start_block, current_block - start_block + 1)
        if blocks:
            success_count = push_blocks_to_main_network(blocks)
            print(f"\n✅ Successfully pushed {success_count}/{len(blocks)} blocks to main network")
            return success_count > 0
        else:
            print("No blocks to push")
            return False
            
    except Exception as e:
        print(f"Error in manual propagation: {e}")
        return False

def check_sync_status_after_fix():
    """Check if the sync worked"""
    print("\n=== CHECKING SYNC STATUS ===")
    
    try:
        # Get local info
        local_response = requests.get("http://localhost:3006/get_mining_info", timeout=10)
        local_info = local_response.json()['result']
        local_block = local_info['last_block']['id']
        
        # Get main network info  
        main_response = requests.get("https://stellaris-node.connor33341.dev/get_mining_info", timeout=10)
        main_info = main_response.json()['result']
        main_block = main_info['last_block']['id']
        
        print(f"Local node: Block {local_block}")
        print(f"Main network: Block {main_block}")
        
        if main_block >= local_block:
            print("✅ Sync appears successful - main network caught up!")
            return True
        else:
            print(f"⚠️  Main network still behind by {local_block - main_block} blocks")
            return False
            
    except Exception as e:
        print(f"Error checking sync status: {e}")
        return False

def main():
    print("🔧 VoxaCommunications Sync Fixer")
    print("=" * 50)
    
    # Step 1: Check current nodes
    print("\n1. Checking current node connectivity...")
    known_nodes = check_nodes_connectivity()
    
    # Step 2: Add main node if not present
    main_node = "https://stellaris-node.connor33341.dev"
    if main_node not in known_nodes:
        print("\n2. Adding main network node...")
        if add_main_node_to_local():
            print("✓ Main node added successfully")
        else:
            print("✗ Failed to add main node")
    else:
        print("\n2. Main node already known")
    
    # Step 3: Force sync
    print("\n3. Forcing sync with main network...")
    if force_sync_with_main_network():
        print("✓ Sync command sent")
    else:
        print("✗ Sync command failed")
    
    # Wait a bit for sync
    print("\n4. Waiting for sync to complete...")
    time.sleep(5)
    
    # Step 4: Manual block propagation
    print("\n5. Manually propagating recent blocks...")
    if manual_propagate_recent_blocks():
        print("✓ Block propagation completed")
    else:
        print("✗ Block propagation failed")
    
    # Step 5: Check final status
    time.sleep(3)
    if check_sync_status_after_fix():
        print("\n🎉 SYNC FIXED! Your mining rewards should now appear on the main network.")
        print("💡 Update your wallet to connect to the main network to see your balance.")
    else:
        print("\n❌ Sync issue persists. The main network may have a different blockchain.")
        print("💡 Your local mining rewards are safe - keep your wallet pointed to localhost:3006")

if __name__ == "__main__":
    main()
