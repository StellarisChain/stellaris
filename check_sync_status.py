#!/usr/bin/env python3
"""
Check synchronization status between local and main nodes
"""
import requests
import sys
import time

def get_node_info(node_url):
    """Get basic info from a node"""
    try:
        # Get last block info
        mining_info = requests.get(f"{node_url}/get_mining_info", timeout=10).json()
        last_block = mining_info['result']['last_block']
        
        # Get a few recent blocks
        recent_blocks = []
        for i in range(max(0, last_block['id'] - 5), last_block['id'] + 1):
            try:
                block_info = requests.get(f"{node_url}/get_block?block={i}", timeout=5).json()
                if block_info['ok']:
                    recent_blocks.append({
                        'id': i,
                        'hash': block_info['result']['block']['hash'][:16] + '...',
                        'address': block_info['result']['block']['address'][:20] + '...',
                        'timestamp': block_info['result']['block']['timestamp']
                    })
            except:
                pass
        
        return {
            'status': 'online',
            'last_block_id': last_block['id'],
            'last_block_hash': last_block['hash'][:16] + '...',
            'difficulty': mining_info['result']['difficulty'],
            'recent_blocks': recent_blocks
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def check_address_balance(node_url, address):
    """Check address balance on a specific node"""
    try:
        response = requests.get(f"{node_url}/get_address_info?address={address}", timeout=10)
        result = response.json()
        if result['ok']:
            return {
                'status': 'found',
                'balance': result['result']['balance'],
                'outputs_count': len(result['result']['spendable_outputs']),
                'transactions_count': len(result['result']['transactions'])
            }
        else:
            return {'status': 'not_found', 'error': result.get('error', 'Unknown error')}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def main():
    # Node URLs
    local_node = "http://localhost:3006"
    main_node = input("Enter main node URL (or press Enter for default): ").strip()
    if not main_node:
        main_node = "https://stellaris-node.connor33341.dev"
    
    mining_address = input("Enter your mining address: ").strip()
    
    print("=" * 80)
    print("SYNCHRONIZATION STATUS CHECK")
    print("=" * 80)
    
    # Check local node
    print(f"\n🔍 Checking LOCAL node: {local_node}")
    local_info = get_node_info(local_node)
    if local_info['status'] == 'online':
        print(f"✅ Status: Online")
        print(f"📊 Last Block ID: {local_info['last_block_id']}")
        print(f"🔗 Last Block Hash: {local_info['last_block_hash']}")
        print(f"⚡ Difficulty: {local_info['difficulty']}")
        print(f"📈 Recent blocks:")
        for block in local_info['recent_blocks'][-3:]:
            print(f"   Block {block['id']}: {block['hash']} (miner: {block['address']})")
    else:
        print(f"❌ Status: {local_info['error']}")
    
    # Check main node
    print(f"\n🔍 Checking MAIN node: {main_node}")
    main_info = get_node_info(main_node)
    if main_info['status'] == 'online':
        print(f"✅ Status: Online")
        print(f"📊 Last Block ID: {main_info['last_block_id']}")
        print(f"🔗 Last Block Hash: {main_info['last_block_hash']}")
        print(f"⚡ Difficulty: {main_info['difficulty']}")
        print(f"📈 Recent blocks:")
        for block in main_info['recent_blocks'][-3:]:
            print(f"   Block {block['id']}: {block['hash']} (miner: {block['address']})")
    else:
        print(f"❌ Status: {main_info['error']}")
    
    # Compare sync status
    print(f"\n📊 SYNC COMPARISON")
    print("-" * 50)
    if local_info['status'] == 'online' and main_info['status'] == 'online':
        local_height = local_info['last_block_id']
        main_height = main_info['last_block_id']
        height_diff = local_height - main_height
        
        if height_diff > 0:
            print(f"⚠️  Local node is {height_diff} blocks AHEAD of main node")
            print(f"   This means your mined blocks haven't synced to main network yet")
        elif height_diff < 0:
            print(f"⚠️  Local node is {abs(height_diff)} blocks BEHIND main node")
            print(f"   Your local node needs to sync with the main network")
        else:
            print(f"✅ Both nodes are at the same height (block {local_height})")
            
        # Check if last block hashes match
        if local_info['last_block_hash'] == main_info['last_block_hash']:
            print(f"✅ Last block hashes match - nodes are in sync")
        else:
            print(f"❌ Last block hashes differ - potential fork or sync issue")
            print(f"   Local:  {local_info['last_block_hash']}")
            print(f"   Main:   {main_info['last_block_hash']}")
    
    # Check address balance on both nodes
    if mining_address:
        print(f"\n💰 ADDRESS BALANCE CHECK: {mining_address[:20]}...")
        print("-" * 50)
        
        # Local node balance
        local_balance = check_address_balance(local_node, mining_address)
        print(f"Local node balance:")
        if local_balance['status'] == 'found':
            print(f"   ✅ Balance: {local_balance['balance']} STE")
            print(f"   📦 Spendable outputs: {local_balance['outputs_count']}")
            print(f"   📋 Transactions: {local_balance['transactions_count']}")
        else:
            print(f"   ❌ {local_balance.get('error', 'Address not found')}")
        
        # Main node balance
        main_balance = check_address_balance(main_node, mining_address)
        print(f"Main node balance:")
        if main_balance['status'] == 'found':
            print(f"   ✅ Balance: {main_balance['balance']} STE")
            print(f"   📦 Spendable outputs: {main_balance['outputs_count']}")
            print(f"   📋 Transactions: {main_balance['transactions_count']}")
        else:
            print(f"   ❌ {main_balance.get('error', 'Address not found')}")
        
        # Balance comparison
        if (local_balance['status'] == 'found' and main_balance['status'] == 'found'):
            local_bal = float(local_balance['balance'])
            main_bal = float(main_balance['balance'])
            if local_bal > main_bal:
                print(f"\n⚠️  SYNC ISSUE: Local has {local_bal - main_bal} more STE than main node")
                print(f"   Your mining rewards haven't synced to the main network yet")
            elif main_bal > local_bal:
                print(f"\n⚠️  SYNC ISSUE: Main has {main_bal - local_bal} more STE than local node")
                print(f"   Your local node is missing some transactions")
            else:
                print(f"\n✅ Balances match on both nodes")
    
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if local_info['status'] == 'online' and main_info['status'] == 'online':
        if local_info['last_block_id'] > main_info['last_block_id']:
            print("🔄 Your local node has blocks that aren't on the main network.")
            print("   Try triggering a sync from your local node to the main network:")
            print(f"   curl '{local_node}/sync_blockchain'")
            print("   Or check if your node is properly connected to the main network.")
        elif local_info['last_block_id'] < main_info['last_block_id']:
            print("🔄 Your local node is behind. Sync with the main network:")
            print(f"   curl '{local_node}/sync_blockchain?node_url={main_node}'")
        
        if mining_address and local_balance.get('status') == 'found' and main_balance.get('status') != 'found':
            print("💡 Update your wallet to connect to your local node instead of main network:")
            print(f"   Point your wallet to {local_node} instead of the main network")
    
    print("\n📞 Your wallet should connect to whichever node shows your correct balance.")

if __name__ == "__main__":
    main()
