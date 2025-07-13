import random
from asyncio import gather
from collections import deque
import os
from dotenv import dotenv_values
import re
import json
from decimal import Decimal
from datetime import datetime 

from asyncpg import UniqueViolationError
from fastapi import FastAPI, Body, Query
from fastapi.responses import RedirectResponse, Response

from httpx import TimeoutException
#from icecream import ic
from starlette.background import BackgroundTasks, BackgroundTask
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from stellaris.utils.general import timestamp, sha256, transaction_to_json
from stellaris.manager import create_block, get_difficulty, Manager, get_transactions_merkle_tree, \
    split_block_content, calculate_difficulty, clear_pending_transactions, block_to_bytes, get_transactions_merkle_tree_ordered
from stellaris.node.nodes_manager import NodesManager, NodeInterface
from stellaris.node.utils import ip_is_local
from stellaris.transactions import Transaction, CoinbaseTransaction, BPFContractTransaction
from stellaris.database import Database
from stellaris.constants import VERSION, ENDIAN
from stellaris.bpf_vm import BPFExecutor, BPFContract


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
db: Database = None
NodesManager.init()
started = False
is_syncing = False
self_url = None

#print = ic

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

config = dotenv_values(".env")

async def sync_contracts_in_background():
    """Background task to sync contracts from other nodes"""
    try:
        nodes = NodesManager.get_recent_nodes()
        if not nodes:
            return
        
        # Pick a random node to sync from
        import random
        node_url = random.choice(nodes)
        
        node_interface = NodeInterface(node_url)
        response = await node_interface.request('get_contracts')
        
        if response.get('ok') and response.get('result'):
            network_contracts = response['result']
            local_contracts = await db.get_all_contracts()
            
            # Add any missing contracts
            for contract_addr, contract_data in network_contracts.items():
                if contract_addr not in local_contracts:
                    await db.add_contract(contract_addr, contract_data)
                    
    except Exception as e:
        # Silent failure for background task
        pass


async def sync_contracts_after_block():
    """Synchronize contracts after a block containing BPF transactions is processed"""
    try:
        # Give a short delay to allow the block to be fully processed
        import asyncio
        await asyncio.sleep(1)
        
        # Get all contracts from other nodes
        nodes = NodesManager.get_recent_nodes()
        
        for node_url in nodes:
            try:
                node_interface = NodeInterface(node_url)
                response = await node_interface.request('get_contracts')
                
                if response.get('ok') and response.get('result'):
                    network_contracts = response['result']
                    local_contracts = await db.get_all_contracts()
                    
                    # Add any missing contracts
                    for contract_addr, contract_data in network_contracts.items():
                        if contract_addr not in local_contracts:
                            await db.add_contract(contract_addr, contract_data)
                            
            except Exception as e:
                print(f"Failed to sync contracts from {node_url}: {e}")
                continue
                
    except Exception as e:
        print(f"Contract synchronization failed: {e}")


async def fetch_contract_from_network(contract_address: str) -> dict:
    """Fetch contract data from other nodes in the network"""
    nodes = NodesManager.get_recent_nodes()
    
    for node_url in nodes:
        try:
            node_interface = NodeInterface(node_url)
            response = await node_interface.request('get_contract', {'contract_address': contract_address})
            
            if response.get('ok') and response.get('result'):
                contract_data = response['result']
                # Store contract locally for future use
                await db.add_contract(contract_address, contract_data)
                return contract_data
        except Exception as e:
            print(f"Failed to fetch contract from {node_url}: {e}")
            continue
    
    return None


def _find_function_by_selector(selector: str, abi: List[Dict], abi_handler) -> Optional[str]:
    """Find function name by selector in ABI"""
    try:
        selector_bytes = bytes.fromhex(selector)
        
        # Handle different ABI formats
        if isinstance(abi, dict) and 'functions' in abi:
            # Old format
            for func_name, func_def in abi['functions'].items():
                expected_selector = _calculate_function_selector(func_name, func_def, abi_handler)
                if expected_selector == selector_bytes:
                    return func_name
        elif isinstance(abi, list):
            # Standard Solidity ABI format
            for item in abi:
                if item.get('type') == 'function':
                    func_name = item.get('name')
                    expected_selector = _calculate_function_selector(func_name, item, abi_handler)
                    if expected_selector == selector_bytes:
                        return func_name
        
        return None
    except Exception:
        return None


def _calculate_function_selector(func_name: str, func_def: Dict, abi_handler) -> bytes:
    """Calculate function selector for a function"""
    try:
        signature = abi_handler._get_function_signature(func_name, func_def)
        return abi_handler._keccak256(signature.encode())[:4]
    except Exception:
        return b''


def _decode_call_arguments(call_data: str, function_name: str, abi: List[Dict], abi_handler) -> List:
    """Decode call arguments from hex data"""
    try:
        if not call_data:
            return []
        
        data_bytes = bytes.fromhex(call_data)
        
        # Get function definition from ABI
        function_abi = abi_handler._get_function_abi(function_name, abi)
        inputs = function_abi.get('inputs', [])
        
        if not inputs:
            return []
        
        # Decode arguments
        return abi_handler._decode_arguments(data_bytes, inputs)
    except Exception as e:
        raise Exception(f"Failed to decode arguments: {str(e)}")


def _extract_abi_from_bytecode(bytecode: str) -> Optional[List[Dict]]:
    """Extract ABI from bytecode metadata if present"""
    try:
        # Look for common ABI patterns in bytecode metadata
        if len(bytecode) > 100:
            # Check for Solidity metadata hash at the end
            # This is a simplified extraction - real implementation would parse CBOR metadata
            return None  # Return None to use default ABI
        return None
    except Exception:
        return None


async def propagate(path: str, args: dict, ignore_url=None, nodes: list = None):
    global self_url
    self_node = NodeInterface(self_url or '')
    ignore_node = NodeInterface(ignore_url or '')
    aws = []
    for node_url in nodes or NodesManager.get_propagate_nodes():
        node_interface = NodeInterface(node_url)
        if node_interface.base_url == self_node.base_url or node_interface.base_url == ignore_node.base_url:
            continue
        aws.append(node_interface.request(path, args, self_node.url))
    for response in await gather(*aws, return_exceptions=True):
        print('node response: ', response)


async def create_blocks(blocks: list):
    _, last_block = await calculate_difficulty()
    last_block['id'] = last_block['id'] if last_block != {} else 0
    last_block['hash'] = last_block['hash'] if 'hash' in last_block else (30_06_2005).to_bytes(32, ENDIAN).hex()
    i = last_block['id'] + 1
    for block_info in blocks:
        block = block_info['block']
        txs_hex = block_info['transactions']
        txs = [await Transaction.from_hex(tx) for tx in txs_hex]
        #txs = [await Transaction.from_hex(tx, set_timestamp=True) for tx in txs_hex]
        for tx in txs:
            if isinstance(tx, CoinbaseTransaction):
                txs.remove(tx)
                break
        hex_txs = [tx.hex() for tx in txs]
        block['merkle_tree'] = get_transactions_merkle_tree(hex_txs) if i > 22500 else get_transactions_merkle_tree_ordered(hex_txs)
        block_content = block.get('content') or block_to_bytes(last_block['hash'], block)

        if i <= 22500 and sha256(block_content) != block['hash'] and i != 17972:
            from itertools import permutations
            for l in permutations(hex_txs):
                _hex_txs = list(l)
                block['merkle_tree'] = get_transactions_merkle_tree_ordered(_hex_txs)
                block_content = block_to_bytes(last_block['hash'], block)
                if sha256(block_content) == block['hash']:
                    break
        elif 131309 < i < 150000 and sha256(block_content) != block['hash']:
            for diff in range(0, 100):
                block['difficulty'] = diff / 10
                block_content = block_to_bytes(last_block['hash'], block)
                if sha256(block_content) == block['hash']:
                    break
        assert i == block['id']
        if not await create_block(block_content.hex() if isinstance(block_content, bytes) else block_content, txs, last_block):
            return False
        last_block = block
        i += 1
    return True


async def _sync_blockchain(node_url: str = None):
    print('sync blockchain')
    if not node_url:
        nodes = NodesManager.get_recent_nodes()
        if not nodes:
            return
        node_url = random.choice(nodes)
    node_url = node_url.strip('/')
    _, last_block = await calculate_difficulty()
    starting_from = i = await db.get_next_block_id()
    node_interface = NodeInterface(node_url)
    local_cache = None
    if last_block != {} and last_block['id'] > 500:
        remote_last_block = (await node_interface.get_block(i-1))['block']
        if remote_last_block['hash'] != last_block['hash']:
            print(remote_last_block['hash'])
            offset, limit = i - 500, 500
            remote_blocks = await node_interface.get_blocks(offset, limit)
            local_blocks = await db.get_blocks(offset, limit)
            local_blocks = local_blocks[:len(remote_blocks)]
            local_blocks.reverse()
            remote_blocks.reverse()
            print(len(remote_blocks), len(local_blocks))
            for n, local_block in enumerate(local_blocks):
                if local_block['block']['hash'] == remote_blocks[n]['block']['hash']:
                    print(local_block, remote_blocks[n])
                    last_common_block = local_block['block']['id']
                    local_cache = local_blocks[:n]
                    local_cache.reverse()
                    await db.remove_blocks(last_common_block + 1)
                    break

    #return
    limit = 1000
    while True:
        i = await db.get_next_block_id()
        try:
            blocks = await node_interface.get_blocks(i, limit)
        except Exception as e:
            print(e)
            #NodesManager.get_nodes().remove(node_url)
            NodesManager.sync()
            break
        try:
            _, last_block = await calculate_difficulty()
            if not blocks:
                print('syncing complete')
                if last_block['id'] > starting_from:
                    NodesManager.update_last_message(node_url)
                    if timestamp() - last_block['timestamp'] < 86400:
                        # if last block is from less than a day ago, propagate it
                        txs_hashes = await db.get_block_transaction_hashes(last_block['hash'])
                        await propagate('push_block', {'block_content': last_block['content'], 'txs': txs_hashes, 'block_no': last_block['id']}, node_url)
                break
            assert await create_blocks(blocks)
        except Exception as e:
            print(e)
            if local_cache is not None:
                print('sync failed, reverting back to previous chain')
                await db.delete_blocks(last_common_block)
                await create_blocks(local_cache)
            return


async def sync_blockchain(node_url: str = None):
    try:
        await _sync_blockchain(node_url)
    except Exception as e:
        print(e)
        return


@app.on_event("startup")
async def startup():
    global db
    global config
    db = await Database.create(
        user=config['STELLARIS_DATABASE_USER'] if 'STELLARIS_DATABASE_USER' in config else "stellaris" ,
        password=config['STELLARIS_DATABASE_PASSWORD'] if 'STELLARIS_DATABASE_PASSWORD' in config else 'stellaris',
        database=config['STELLARIS_DATABASE_NAME'] if 'STELLARIS_DATABASE_NAME' in config else "stellaris",
        host=config['STELLARIS_DATABASE_HOST'] if 'STELLARIS_DATABASE_HOST' in config else None
    )


@app.get("/")
async def root():
    return {"version": VERSION, "unspent_outputs_hash": await db.get_unspent_outputs_hash()}


async def propagate_old_transactions(propagate_txs):
    await db.update_pending_transactions_propagation_time([sha256(tx_hex) for tx_hex in propagate_txs])
    for tx_hex in propagate_txs:
        await propagate('push_tx', {'tx_hex': tx_hex})


@app.middleware("http")
async def middleware(request: Request, call_next):
    global started, self_url
    nodes = NodesManager.get_recent_nodes()
    hostname = request.base_url.hostname

    # Normalize the URL path by removing extra slashes
    normalized_path = re.sub('/+', '/', request.scope['path'])
    if normalized_path != request.scope['path']:
        url = request.url
        new_url = str(url).replace(request.scope['path'], normalized_path)
        #Redirect to normalized URL
        return RedirectResponse(new_url)

    if 'Sender-Node' in request.headers:
        NodesManager.add_node(request.headers['Sender-Node'])

    if nodes and not started or (ip_is_local(hostname) or hostname == 'localhost'):
        try:
            node_url = nodes[0]
            #requests.get(f'{node_url}/add_node', {'url': })
            j = await NodesManager.request(f'{node_url}/get_nodes')
            nodes.extend(j['result'])
            NodesManager.sync()
        except:
            pass

        if not (ip_is_local(hostname) or hostname == 'localhost'):
            started = True

            self_url = str(request.base_url).strip('/')
            try:
                nodes.remove(self_url)
            except ValueError:
                pass
            try:
                nodes.remove(self_url.replace("http://", "https://"))
            except ValueError:
                pass

            NodesManager.sync()

            try:
                await propagate('add_node', {'url': self_url})
                cousin_nodes = sum(await NodeInterface(url).get_nodes() for url in nodes)
                await propagate('add_node', {'url': self_url}, nodes=cousin_nodes)
            except:
                pass
    propagate_txs = await db.get_need_propagate_transactions()
    
    # Periodically sync contracts (every 100 requests approximately)
    import random
    if random.randint(1, 100) == 1:
        try:
            await sync_contracts_in_background()
        except:
            pass
    
    try:
        response = await call_next(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        if propagate_txs:
            response.background = BackgroundTask(propagate_old_transactions, propagate_txs)
        return response
    except:
        raise
        return {'ok': False, 'error': 'Internal error'}


@app.exception_handler(Exception)
async def exception_handler(request: Request, e: Exception):
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": f"Uncaught {type(e).__name__} exception"},
    )

transactions_cache = deque(maxlen=100)


@app.get("/push_tx")
@app.post("/push_tx")
async def push_tx(request: Request, background_tasks: BackgroundTasks, tx_hex: str = None, body=Body(False)):
    if body and tx_hex is None:
        tx_hex = body['tx_hex']
    tx = await Transaction.from_hex(tx_hex)
    if tx.hash() in transactions_cache:
        return {'ok': False, 'error': 'Transaction just added'}
    try:
        if await db.add_pending_transaction(tx):
            if 'Sender-Node' in request.headers:
                NodesManager.update_last_message(request.headers['Sender-Node'])
            background_tasks.add_task(propagate, 'push_tx', {'tx_hex': tx_hex})
            transactions_cache.append(tx.hash())
            return {'ok': True, 'result': 'Transaction has been accepted'}
        else:
            return {'ok': False, 'error': 'Transaction has not been added'}
    except UniqueViolationError:
        return {'ok': False, 'error': 'Transaction already present'}


@app.post("/push_block")
@app.get("/push_block")
async def push_block(request: Request, background_tasks: BackgroundTasks, block_content: str = '', txs='', block_no: int = None, body=Body(False)):
    if is_syncing:
        return {'ok': False, 'error': 'Node is already syncing'}
    if body:
        txs = body['txs']
        if 'block_content' in body:
            block_content = body['block_content']
        if 'id' in body:
            block_no = body['id']
        if 'block_no' in body:
            block_no = body['block_no']
    if isinstance(txs, str):
        txs = txs.split(',')
        if txs == ['']:
            txs = []
    previous_hash = split_block_content(block_content)[0]
    next_block_id = await db.get_next_block_id()
    if block_no is None:
        previous_block = await db.get_block(previous_hash)
        if previous_block is None:
            if 'Sender-Node' in request.headers:
                background_tasks.add_task(sync_blockchain, request.headers['Sender-Node'])
                return {'ok': False,
                        'error': 'Previous hash not found, had to sync according to sender node, block may have been accepted'}
            else:
                return {'ok': False, 'error': 'Previous hash not found'}
        block_no = previous_block['id'] + 1
    if next_block_id < block_no:
        background_tasks.add_task(sync_blockchain, request.headers['Sender-Node'] if 'Sender-Node' in request.headers else None)
        return {'ok': False, 'error': 'Blocks missing, had to sync according to sender node, block may have been accepted'}
    if next_block_id > block_no:
        return {'ok': False, 'error': 'Too old block'}
    final_transactions = []
    hashes = []
    for tx_hex in txs:
        if len(tx_hex) == 64:  # it's an hash
            hashes.append(tx_hex)
        else:
            final_transactions.append(await Transaction.from_hex(tx_hex))
    if hashes:
        pending_transactions = await db.get_pending_transactions_by_hash(hashes)
        if len(pending_transactions) < len(hashes):  # one or more tx not found
            if 'Sender-Node' in request.headers:
                background_tasks.add_task(sync_blockchain, request.headers['Sender-Node'])
                return {'ok': False,
                        'error': 'Transaction hash not found, had to sync according to sender node, block may have been accepted'}
            else:
                return {'ok': False, 'error': 'Transaction hash not found'}
        final_transactions.extend(pending_transactions)
    if not await create_block(block_content, final_transactions):
        return {'ok': False}

    if 'Sender-Node' in request.headers:
        NodesManager.update_last_message(request.headers['Sender-Node'])

    background_tasks.add_task(propagate, 'push_block', {
        'block_content': block_content,
        'txs': [tx.hex() for tx in final_transactions] if len(final_transactions) < 10 else txs,
        'block_no': block_no
    })
    
    # Check if block contains BPF contract transactions and sync contracts if needed
    has_contract_transactions = any(isinstance(tx, BPFContractTransaction) for tx in final_transactions)
    if has_contract_transactions:
        background_tasks.add_task(sync_contracts_after_block)
    
    return {'ok': True}


@app.get("/sync_blockchain")
@limiter.limit("10/minute")
async def sync(request: Request, node_url: str = None):
    global is_syncing
    if is_syncing:
        return {'ok': False, 'error': 'Node is already syncing'}
    is_syncing = True
    await sync_blockchain(node_url)
    is_syncing = False


async def sync_pending_transactions():
    """Sync pending transactions from other nodes if we have none"""
    if await db.get_pending_transactions_limit(1, hex_only=True):
        return  # We already have pending transactions
    
    nodes = NodesManager.get_recent_nodes()
    for node_url in nodes:
        try:
            node_interface = NodeInterface(node_url)
            response = await node_interface.request('get_pending_transactions', {})
            if response.get('ok') and response.get('result'):
                remote_txs = response['result'][:10]  # Get up to 10 transactions
                for tx_hex in remote_txs:
                    try:
                        tx = await Transaction.from_hex(tx_hex)
                        await db.add_pending_transaction(tx)
                        print(f"Synced transaction from {node_url}: {tx.hash()}")
                    except Exception as e:
                        print(f"Failed to sync transaction {tx_hex[:16]}...: {e}")
                if remote_txs:
                    print(f"Synced {len(remote_txs)} pending transactions from {node_url}")
                    break  # Stop after successfully syncing from one node
        except Exception as e:
            print(f"Failed to sync pending transactions from {node_url}: {e}")


LAST_PENDING_TRANSACTIONS_CLEAN = [0]
LAST_PENDING_SYNC = [0]


@app.get("/get_mining_info")
async def get_mining_info(background_tasks: BackgroundTasks, pretty: bool = False):
    Manager.difficulty = None
    difficulty, last_block = await get_difficulty()
    
    # Sync pending transactions if we have none and it's been a while
    if LAST_PENDING_SYNC[0] < timestamp() - 30:  # Sync every 30 seconds
        LAST_PENDING_SYNC[0] = timestamp()
        background_tasks.add_task(sync_pending_transactions)
    
    pending_transactions = await db.get_pending_transactions_limit(hex_only=True)
    pending_transactions = sorted(pending_transactions)
    if LAST_PENDING_TRANSACTIONS_CLEAN[0] < timestamp() - 600:
        print(LAST_PENDING_TRANSACTIONS_CLEAN[0])
        LAST_PENDING_TRANSACTIONS_CLEAN[0] = timestamp()
        background_tasks.add_task(clear_pending_transactions, pending_transactions)
    result = {'ok': True, 'result': {
        'difficulty': difficulty,
        'last_block': last_block,
        'pending_transactions': pending_transactions[:10],
        'pending_transactions_hashes': [sha256(tx) for tx in pending_transactions[:10]],
        'merkle_root': get_transactions_merkle_tree(pending_transactions[:10])
    }}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_address_info")
@limiter.limit("8/second")
async def get_address_info(request: Request, address: str, transactions_count_limit: int = Query(default=5, le=50), page: int = Query(default=1, ge=1), show_pending: bool = False, verify: bool = False, pretty: bool = False):    
    outputs = await db.get_spendable_outputs(address)
    balance = sum(output.amount for output in outputs)
    
     # Calculate offset for pagination
    offset = (page - 1) * transactions_count_limit
    
    # Fetch transactions with pagination
    transactions = await db.get_address_transactions(address, limit=transactions_count_limit, offset=offset, check_signatures=True) if transactions_count_limit > 0 else []

    result = {'ok': True, 'result': {
        'balance': "{:f}".format(balance),
        'spendable_outputs': [{'amount': "{:f}".format(output.amount), 'tx_hash': output.tx_hash, 'index': output.index} for output in outputs],
        'transactions': [await db.get_nice_transaction(tx.hash(), address if verify else None) for tx in transactions],
        #'transactions': [await db.get_nice_transaction(tx.hash(), address if verify else None) for tx in await db.get_address_transactions(address, limit=transactions_count_limit, check_signatures=True)] if transactions_count_limit > 0 else [],
        'pending_transactions': [await db.get_nice_transaction(tx.hash(), address if verify else None) for tx in await db.get_address_pending_transactions(address, True)] if show_pending else None,
        'pending_spent_outputs': await db.get_address_pending_spent_outputs(address) if show_pending else None
    }}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/add_node")
@limiter.limit("10/minute")
async def add_node(request: Request, url: str, background_tasks: BackgroundTasks):
    nodes = NodesManager.get_nodes()
    url = url.strip('/')
    if url == self_url:
        return {'ok': False, 'error': 'Recursively adding node'}
    if url in nodes:
        return {'ok': False, 'error': 'Node already present'}
    else:
        try:
            assert await NodesManager.is_node_working(url)
            background_tasks.add_task(propagate, 'add_node', {'url': url}, url)
            NodesManager.add_node(url)
            return {'ok': True, 'result': 'Node added'}
        except Exception as e:
            print(e)
            return {'ok': False, 'error': 'Could not add node'}


@app.get("/get_nodes")
async def get_nodes(pretty: bool = False):
    result = {'ok': True, 'result': NodesManager.get_recent_nodes()[:100]}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_pending_transactions")
async def get_pending_transactions(pretty: bool = False):
    result = {'ok': True, 'result': [tx.hex() for tx in await db.get_pending_transactions_limit(1000)]}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_transaction")
@limiter.limit("8/second")
async def get_transaction(request: Request, tx_hash: str, verify: bool = False, pretty: bool = False):
    tx = await db.get_nice_transaction(tx_hash)
    if tx is None:
        result = {'ok': False, 'error': 'Transaction not found'}
    else:
        result = {'ok': True, 'result': tx}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_block")
@limiter.limit("30/minute")
async def get_block(request: Request, block: str, full_transactions: bool = False, pretty: bool = False):
    if block.isdecimal():
        block_info = await db.get_block_by_id(int(block))
        if block_info is not None:
            block_hash = block_info['hash']
        else:
            result = {'ok': False, 'error': 'Block not found'}
    else:
        block_hash = block
        block_info = await db.get_block(block_hash)
    if block_info:
        result = {'ok': True, 'result': {
            'block': block_info,
            'transactions': await db.get_block_transactions(block_hash, hex_only=True) if not full_transactions else None,
            'full_transactions': await db.get_block_nice_transactions(block_hash) if full_transactions else None
        }}
    else:
        result = {'ok': False, 'error': 'Block not found'}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_blocks")
@limiter.limit("10/minute")
async def get_blocks(request: Request, offset: int, limit: int = Query(default=..., le=1000), pretty: bool = False):
    blocks = await db.get_blocks(offset, limit)
    result = {'ok': True, 'result': blocks}
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.post("/deploy_contract")
@limiter.limit("5/minute")
async def deploy_contract(request: Request, 
                         bytecode: str = Body(...), 
                         abi: dict = Body(...),
                         inputs: list = Body(...),
                         outputs: list = Body(...),
                         gas_limit: int = Body(default=100000),
                         contract_type: str = Body(default='bpf'),
                         private_keys: list = Body(default=[]),
                         background_tasks: BackgroundTasks = BackgroundTasks()):
    """Deploy a new BPF or EVM contract"""
    try:
        # Validate inputs
        if not bytecode or not abi:
            return {'ok': False, 'error': 'Bytecode and ABI are required'}
        
        # Validate bytecode format
        try:
            bytecode_bytes = bytes.fromhex(bytecode)
        except ValueError:
            return {'ok': False, 'error': 'Invalid bytecode format'}
        
        # Auto-detect contract type from ABI if not specified
        if contract_type == 'bpf':
            from stellaris.bpf_vm.solidity_abi import SolidityABI
            solidity_abi = SolidityABI()
            if solidity_abi.is_solidity_abi(abi):
                contract_type = 'evm'
        
        # Create transaction inputs and outputs
        from stellaris.transactions import TransactionInput, TransactionOutput
        tx_inputs = []
        tx_outputs = []
        
        for inp in inputs:
            tx_inputs.append(TransactionInput(
                tx_hash=inp['tx_hash'],
                index=inp['index'],
                private_key=inp.get('private_key')
            ))
        
        for out in outputs:
            tx_outputs.append(TransactionOutput(
                address=out['address'],
                amount=Decimal(str(out['amount']))
            ))
        
        # Create BPF contract transaction
        contract_data = {
            'bytecode': bytecode,
            'abi': abi,
            'contract_type': contract_type
        }
        
        contract_tx = BPFContractTransaction(
            inputs=tx_inputs,
            outputs=tx_outputs,
            contract_type=BPFContractTransaction.CONTRACT_DEPLOY,
            contract_data=contract_data,
            gas_limit=gas_limit
        )
        
        # Sign transaction
        if private_keys:
            contract_tx.sign(private_keys)
        
        # Add to pending transactions and propagate to network
        if await db.add_pending_transaction(contract_tx):
            # Propagate transaction to network
            background_tasks.add_task(propagate, 'push_tx', {'tx_hex': contract_tx.hex()})
            return {'ok': True, 'tx_hash': contract_tx.hash(), 'contract_type': contract_type}
        else:
            return {'ok': False, 'error': 'Failed to add contract deployment transaction'}
            
    except Exception as e:
        return {'ok': False, 'error': f'Contract deployment failed: {str(e)}'}


@app.post("/call_contract")
@limiter.limit("10/minute")
async def call_contract(request: Request,
                       contract_address: str = Body(...),
                       function_name: str = Body(...),
                       args: list = Body(default=[]),
                       inputs: list = Body(...),
                       outputs: list = Body(...),
                       gas_limit: int = Body(default=100000),
                       private_keys: list = Body(default=[]),
                       background_tasks: BackgroundTasks = BackgroundTasks()):
    """Call a BPF contract function"""
    try:
        # Validate contract exists locally, or try to fetch from network
        contract_data = await db.get_contract(contract_address)
        if not contract_data:
            # Try to fetch contract from network nodes
            contract_data = await fetch_contract_from_network(contract_address)
            if not contract_data:
                return {'ok': False, 'error': 'Contract not found on network'}
        
        # Create transaction inputs and outputs
        from stellaris.transactions import TransactionInput, TransactionOutput
        tx_inputs = []
        tx_outputs = []
        
        for inp in inputs:
            tx_inputs.append(TransactionInput(
                tx_hash=inp['tx_hash'],
                index=inp['index'],
                private_key=inp.get('private_key')
            ))
        
        for out in outputs:
            tx_outputs.append(TransactionOutput(
                address=out['address'],
                amount=Decimal(str(out['amount']))
            ))
        
        # Create BPF contract call transaction
        contract_call_data = {
            'contract_address': contract_address,
            'function_name': function_name,
            'args': args
        }
        
        contract_tx = BPFContractTransaction(
            inputs=tx_inputs,
            outputs=tx_outputs,
            contract_type=BPFContractTransaction.CONTRACT_CALL,
            contract_data=contract_call_data,
            gas_limit=gas_limit
        )
        
        # Sign transaction
        if private_keys:
            contract_tx.sign(private_keys)
        
        # Add to pending transactions and propagate to network
        if await db.add_pending_transaction(contract_tx):
            # Propagate transaction to network
            background_tasks.add_task(propagate, 'push_tx', {'tx_hex': contract_tx.hex()})
            return {'ok': True, 'tx_hash': contract_tx.hash()}
        else:
            return {'ok': False, 'error': 'Failed to add contract call transaction'}
            
    except Exception as e:
        return {'ok': False, 'error': f'Contract call failed: {str(e)}'}


@app.get("/get_contract")
@limiter.limit("20/minute")
async def get_contract(request: Request, address: str, pretty: bool = False):
    """Get contract information"""
    try:
        contract_data = await db.get_contract(address)
        if contract_data:
            result = {'ok': True, 'contract': contract_data}
        else:
            result = {'ok': False, 'error': 'Contract not found'}
        
        return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result
    except Exception as e:
        return {'ok': False, 'error': f'Failed to get contract: {str(e)}'}


@app.get("/get_contracts")
@limiter.limit("10/minute")
async def get_contracts(request: Request, pretty: bool = False):
    """Get all contracts"""
    try:
        contracts = await db.get_all_contracts()
        result = {'ok': True, 'contracts': contracts}
        return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result
    except Exception as e:
        return {'ok': False, 'error': f'Failed to get contracts: {str(e)}'}


@app.post("/estimate_gas")
@limiter.limit("20/minute")
async def estimate_gas(request: Request,
                      contract_address: str = Body(...),
                      function_name: str = Body(...),
                      args: list = Body(default=[]),
                      caller: str = Body(...)):
    """Estimate gas needed for contract execution"""
    try:
        # Load contracts from database
        contracts = await db.get_all_contracts()
        contracts_dict = {}
        for addr, contract_data in contracts.items():
            contracts_dict[addr] = BPFContract.from_dict(contract_data)
        
        # Create executor
        executor = BPFExecutor(contracts_dict)
        
        # Estimate gas
        gas_estimate = executor.estimate_gas(
            contract_address=contract_address,
            function_name=function_name,
            args=args,
            caller=caller
        )
        
        return {'ok': True, 'gas_estimate': gas_estimate}
    except Exception as e:
        return {'ok': False, 'error': f'Gas estimation failed: {str(e)}'}


@app.get("/sync_contracts")
@limiter.limit("5/minute")
async def sync_contracts(request: Request, background_tasks: BackgroundTasks):
    """Synchronize contracts from other nodes in the network"""
    try:
        nodes = NodesManager.get_recent_nodes()
        synced_contracts = 0
        
        for node_url in nodes:
            try:
                node_interface = NodeInterface(node_url)
                response = await node_interface.request('get_contracts')
                
                if response.get('ok') and response.get('result'):
                    network_contracts = response['result']
                    
                    # Check which contracts we don't have locally
                    local_contracts = await db.get_all_contracts()
                    
                    for contract_addr, contract_data in network_contracts.items():
                        if contract_addr not in local_contracts:
                            await db.add_contract(contract_addr, contract_data)
                            synced_contracts += 1
                            
            except Exception as e:
                print(f"Failed to sync contracts from {node_url}: {e}")
                continue
        
        return {'ok': True, 'synced_contracts': synced_contracts}
    except Exception as e:
        return {'ok': False, 'error': f'Contract synchronization failed: {str(e)}'}


@app.get("/push_contracts")
@app.post("/push_contracts")
async def push_contracts(request: Request, background_tasks: BackgroundTasks, 
                        contracts: dict = Body(default={})):
    """Receive contracts from other nodes"""
    try:
        if not contracts:
            return {'ok': False, 'error': 'No contracts provided'}
        
        added_contracts = 0
        local_contracts = await db.get_all_contracts()
        
        for contract_addr, contract_data in contracts.items():
            if contract_addr not in local_contracts:
                await db.add_contract(contract_addr, contract_data)
                added_contracts += 1
        
        # Propagate contracts to other nodes
        if added_contracts > 0:
            background_tasks.add_task(propagate, 'push_contracts', {'contracts': contracts})
        
        return {'ok': True, 'added_contracts': added_contracts}
    except Exception as e:
        return {'ok': False, 'error': f'Failed to receive contracts: {str(e)}'}


# Web3-compatible endpoints for Hardhat integration
@app.post("/eth_sendTransaction")
@limiter.limit("10/minute")
async def eth_send_transaction(request: Request, data: dict = Body(...)):
    """Web3-compatible transaction endpoint for Hardhat"""
    try:
        # Extract transaction data
        tx_data = data.get('data', '')
        to_address = data.get('to', '')
        gas_limit = int(data.get('gas', '100000'), 16) if data.get('gas') else 100000
        
        if not to_address:
            # This is a contract deployment
            return await _deploy_contract_web3(tx_data, gas_limit)
        else:
            # This is a contract call
            return await _call_contract_web3(to_address, tx_data, gas_limit)
            
    except Exception as e:
        return {'error': f'Transaction failed: {str(e)}'}


async def _deploy_contract_web3(bytecode: str, gas_limit: int):
    """Deploy contract via Web3-compatible interface"""
    try:
        # Extract ABI from bytecode metadata if present, otherwise create minimal ABI
        abi = _extract_abi_from_bytecode(bytecode) or [
            {
                "type": "constructor",
                "inputs": [],
                "outputs": []
            }
        ]
        
        # Generate a unique contract address based on bytecode and timestamp
        import time
        from stellaris.utils.general import sha256
        
        contract_seed = f"{bytecode}{time.time()}"
        contract_address = sha256(contract_seed.encode())[:40]
        
        # Create proper transaction inputs and outputs for contract deployment
        # In a real deployment, these would come from the calling account
        inputs = []
        outputs = [{
            'address': contract_address,
            'amount': '0'
        }]
        
        # Create contract data with extracted/generated ABI
        contract_data = {
            'bytecode': bytecode,
            'abi': abi,
            'contract_type': 'evm',
            'deployment_time': int(time.time()),
            'gas_limit': gas_limit
        }
        
        # Create BPF contract transaction
        from stellaris.transactions import BPFContractTransaction
        contract_tx = BPFContractTransaction(
            inputs=[],  # Empty inputs for deployment
            outputs=[],  # Empty outputs for deployment
            contract_type=BPFContractTransaction.CONTRACT_DEPLOY,
            contract_data=contract_data,
            gas_limit=gas_limit
        )
        
        # Store contract directly in database for immediate availability
        contract = {
            'bytecode': bytecode,
            'abi': abi,
            'creator': contract_address,
            'gas_limit': gas_limit,
            'state': {},
            'contract_type': 'evm'
        }
        
        await db.add_contract(contract_address, contract)
        
        # Add to pending transactions for network propagation
        if await db.add_pending_transaction(contract_tx):
            # Propagate transaction to network in background
            import asyncio
            asyncio.create_task(propagate('push_tx', {'tx_hex': contract_tx.hex()}))
            
            return {
                'id': 1, 
                'jsonrpc': '2.0', 
                'result': {
                    'transactionHash': contract_tx.hash(),
                    'contractAddress': f"0x{contract_address}"
                }
            }
        else:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': 'Failed to deploy contract'}}
            
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': f'Contract deployment failed: {str(e)}'}}


async def _call_contract_web3(to_address: str, data: str, gas_limit: int):
    """Call contract via Web3-compatible interface"""
    try:
        # Remove 0x prefix if present
        if to_address.startswith('0x'):
            to_address = to_address[2:]
        if data.startswith('0x'):
            data = data[2:]
        
        # Decode function selector (first 4 bytes)
        if len(data) < 8:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': 'Invalid call data'}}
        
        function_selector = data[:8]
        call_data = data[8:] if len(data) > 8 else ""
        
        # Get contract from database
        contract_data = await db.get_contract(to_address)
        if not contract_data:
            # Try to fetch from network
            contract_data = await fetch_contract_from_network(to_address)
            if not contract_data:
                return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': 'Contract not found'}}
        
        # Find matching function in ABI using selector
        from stellaris.bpf_vm.solidity_abi import SolidityABI
        abi_handler = SolidityABI()
        
        function_name = _find_function_by_selector(function_selector, contract_data.get('abi', []), abi_handler)
        if not function_name:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': 'Function not found'}}
        
        # Decode call arguments
        try:
            args = _decode_call_arguments(call_data, function_name, contract_data.get('abi', []), abi_handler)
        except Exception as e:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': f'Failed to decode arguments: {str(e)}'}}
        
        # Execute contract call
        try:
            from stellaris.bpf_vm import BPFExecutor, BPFContract
            
            # Create contract instance
            contract = BPFContract.from_dict(contract_data)
            
            # Create executor with all contracts
            contracts = await db.get_all_contracts()
            contracts_dict = {}
            for addr, cdata in contracts.items():
                contracts_dict[addr] = BPFContract.from_dict(cdata)
            
            executor = BPFExecutor(contracts_dict)
            
            # Execute function call
            result = executor.call_function(
                contract_address=to_address,
                function_name=function_name,
                args=args,
                caller='0x' + '0' * 40,  # Default caller
                gas_limit=gas_limit
            )
            
            # Encode result for Web3 response
            if result.get('success'):
                output_data = result.get('output', b'')
                if isinstance(output_data, bytes):
                    output_hex = '0x' + output_data.hex()
                else:
                    # Encode non-bytes output
                    output_hex = '0x' + str(output_data).encode().hex()
                
                return {'id': 1, 'jsonrpc': '2.0', 'result': output_hex}
            else:
                error_msg = result.get('error', 'Execution failed')
                return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': error_msg}}
                
        except Exception as e:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': f'Execution failed: {str(e)}'}}
        
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': f'Call failed: {str(e)}'}}


@app.post("/eth_call")
@limiter.limit("20/minute")
async def eth_call(request: Request, data: dict = Body(...)):
    """Web3-compatible call endpoint for Hardhat"""
    try:
        to_address = data.get('to', '')
        call_data = data.get('data', '')
        
        if not to_address:
            return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': 'No contract address provided'}}
        
        # Execute the contract call using our implementation
        result = await _call_contract_web3(to_address, call_data, 100000)
        
        # Return the result from the contract execution
        return result
        
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': str(e)}}


@app.post("/eth_getTransactionReceipt")
@limiter.limit("20/minute")
async def eth_get_transaction_receipt(request: Request, tx_hash: str = Body(...)):
    """Web3-compatible transaction receipt endpoint"""
    try:
        # Remove 0x prefix if present
        if tx_hash.startswith('0x'):
            tx_hash = tx_hash[2:]
        
        # Check if transaction exists in our database
        transaction = await db.get_transaction(tx_hash)
        
        if transaction:
            # Try to find the block containing this transaction
            block_info = None
            block_number = None
            block_hash = None
            
            # Search through recent blocks to find the transaction
            try:
                last_block = await db.get_last_block()
                if last_block:
                    current_id = last_block.get('id', 0)
                    # Search recent blocks (last 100)
                    for i in range(max(0, current_id - 100), current_id + 1):
                        try:
                            block = await db.get_block_by_id(i)
                            if block:
                                tx_hashes = await db.get_block_transaction_hashes(block['hash'])
                                if tx_hash in tx_hashes:
                                    block_info = block
                                    block_number = hex(block['id'])
                                    block_hash = '0x' + block['hash']
                                    break
                        except:
                            continue
            except:
                pass
            
            # Determine gas used based on transaction type
            gas_used = '0x5208'  # Default gas for simple transaction
            contract_address = None
            logs = []
            
            if hasattr(transaction, 'contract_type'):
                # This is a BPF contract transaction
                if hasattr(transaction, 'gas_limit') and transaction.gas_limit:
                    gas_used = hex(transaction.gas_limit)
                else:
                    gas_used = '0x186a0'  # 100000 gas default
                    
                if getattr(transaction, 'contract_type', None) == 'deploy':
                    # Generate contract address from transaction hash
                    contract_address = '0x' + sha256(f"{tx_hash}").encode().hex()[:40]
                elif getattr(transaction, 'contract_type', None) == 'call':
                    # Generate logs for contract calls if available
                    if hasattr(transaction, 'contract_data') and transaction.contract_data:
                        logs = [{
                            'address': '0x' + transaction.contract_data.get('contract_address', '0' * 40),
                            'topics': ['0x' + sha256(f"call_{transaction.contract_data.get('function_name', 'unknown')}").encode().hex()],
                            'data': '0x' + str(transaction.contract_data.get('args', [])).encode().hex()
                        }]
            
            # Get transaction input/output addresses
            from_addr = '0x' + '0' * 40  # Default
            to_addr = '0x' + '0' * 40    # Default
            
            try:
                if hasattr(transaction, 'inputs') and transaction.inputs:
                    # For regular transactions, we'd need to look up the input address
                    pass
                if hasattr(transaction, 'outputs') and transaction.outputs:
                    to_addr = '0x' + getattr(transaction.outputs[0], 'address', '0' * 40)
            except:
                pass
            
            # Return a Web3-compatible receipt with real data
            receipt = {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {
                    'transactionHash': '0x' + tx_hash,
                    'blockNumber': block_number,
                    'blockHash': block_hash,
                    'gasUsed': gas_used,
                    'status': '0x1',  # Success
                    'contractAddress': contract_address,
                    'logs': logs,
                    'logsBloom': '0x' + '0' * 512,  # Empty bloom filter
                    'transactionIndex': '0x0',
                    'from': from_addr,
                    'to': contract_address or to_addr,
                    'cumulativeGasUsed': gas_used
                }
            }
            
            return receipt
        else:
            return {'id': 1, 'jsonrpc': '2.0', 'result': None}
            
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': f'Failed to get receipt: {str(e)}'}}


@app.get("/eth_chainId")
@limiter.limit("50/minute")
async def eth_chain_id(request: Request):
    """Web3-compatible chain ID endpoint"""
    return {'id': 1, 'jsonrpc': '2.0', 'result': '0x539'}  # 1337 in hex (common dev chain ID)


@app.post("/eth_getBalance")
@limiter.limit("20/minute")
async def eth_get_balance(request: Request, address: str = Body(...)):
    """Web3-compatible balance endpoint"""
    try:
        # Remove 0x prefix if present
        if address.startswith('0x'):
            address = address[2:]
        
        # Get balance using existing address info endpoint logic
        outputs = await db.get_spendable_outputs(address)
        balance = sum(output.amount for output in outputs)
        
        if balance is None:
            balance = 0
        
        # Convert to wei (multiply by 10^18)
        balance_wei = int(float(balance) * 10**18)
        return {'id': 1, 'jsonrpc': '2.0', 'result': hex(balance_wei)}
        
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': str(e)}}


@app.post("/eth_accounts")
@limiter.limit("20/minute")
async def eth_accounts(request: Request):
    """Web3-compatible accounts endpoint"""
    # Return empty array since we don't manage accounts
    return {'id': 1, 'jsonrpc': '2.0', 'result': []}


@app.post("/net_version")
@limiter.limit("20/minute")
async def net_version(request: Request):
    """Web3-compatible network version endpoint"""
    return {'id': 1, 'jsonrpc': '2.0', 'result': '1337'}


@app.post("/eth_gasPrice")
@limiter.limit("20/minute")
async def eth_gas_price(request: Request):
    """Web3-compatible gas price endpoint"""
    return {'id': 1, 'jsonrpc': '2.0', 'result': '0x1'}  # 1 wei


@app.post("/eth_estimateGas")
@limiter.limit("20/minute")
async def eth_estimate_gas(request: Request, data: dict = Body(...)):
    """Web3-compatible gas estimation endpoint"""
    try:
        # Simple gas estimation based on transaction type
        if data.get('to'):
            # Contract call
            return {'id': 1, 'jsonrpc': '2.0', 'result': '0x5208'}  # 21000 gas
        else:
            # Contract deployment
            return {'id': 1, 'jsonrpc': '2.0', 'result': '0x186a0'}  # 100000 gas
            
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': str(e)}}


@app.post("/eth_blockNumber")
@limiter.limit("50/minute")
async def eth_block_number(request: Request):
    """Web3-compatible block number endpoint"""
    try:
        # Get current block height from last block
        last_block = await db.get_last_block()
        if last_block:
            block_height = last_block.get('id', 0)
        else:
            block_height = 0
        
        return {'id': 1, 'jsonrpc': '2.0', 'result': hex(block_height)}
        
    except Exception as e:
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -1, 'message': str(e)}}


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Decimal, datetime)):
            return str(o)  # Convert types to string to prevent serialization errors
        return super().default(o)