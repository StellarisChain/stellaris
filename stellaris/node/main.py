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
from stellaris.transactions import Transaction, CoinbaseTransaction, SmartContractTransaction
from stellaris.database import Database
from stellaris.constants import VERSION, ENDIAN
from typing import List, Dict, Optional

# Smart Contract imports
try:
    from stellaris.svm.vm_manager import StellarisVMManager, ExecutionResult
    from stellaris.svm.vm import StellarisVM
    from stellaris.svm.exceptions import SVMError, SVMContractError
    VM_AVAILABLE = True
except ImportError:
    # VM components not available
    StellarisVMManager = None
    ExecutionResult = None
    SVMError = Exception
    SVMContractError = Exception
    VM_AVAILABLE = False


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
db: Database = None
NodesManager.init()
started = False
is_syncing = False
self_url = None
vm_manager = None  # Will be StellarisVMManager when initialized
# Initialize VM Manager (will be set when database is ready)
vm_manager: StellarisVMManager = None

#print = ic

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

config = dotenv_values(".env")

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
        #node_url = "https://stellaris-node.connor33341.dev/"
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
            NodesManager.sync()
            break
        try:
            _, last_block = await calculate_difficulty()
            if not blocks:
                print('syncing complete')
                if last_block['id'] > starting_from:
                    NodesManager.update_last_message(node_url)
                    if timestamp() - last_block['timestamp'] < 86400:
                        txs_hashes = await db.get_block_transaction_hashes(last_block['hash'])
                        await propagate('push_block', {'block_content': last_block['content'], 'txs': txs_hashes, 'block_no': last_block['id']}, node_url)
                # --- Fetch and import remote pending transactions ---
                import httpx
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(f"{node_url}/get_pending_transactions")
                        if resp.status_code == 200:
                            remote_pending = resp.json().get('result', [])
                            for tx_hex in remote_pending:
                                try:
                                    tx = await Transaction.from_hex(tx_hex)
                                    tx_hash = tx.hash()
                                    # Only add if not in chain or local pending
                                    if tx_hash not in db._pending_transactions and not await db.get_transaction(tx_hash, check_signatures=False):
                                        await db.add_pending_transaction(tx, verify=False)
                                except Exception as e:
                                    print(f"Failed to import remote pending tx: {e}")
                except Exception as e:
                    print(f"Failed to fetch remote pending transactions: {e}")
                break
            assert await create_blocks(blocks)
            # Optionally clear duplicates
            # await db.clear_duplicate_pending_transactions()
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
    
    # Initialize VM Manager after database is ready
    await initialize_vm_manager()


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


LAST_PENDING_TRANSACTIONS_CLEAN = [0]


@app.get("/get_mining_info")
async def get_mining_info(background_tasks: BackgroundTasks, pretty: bool = False):
    Manager.difficulty = None
    difficulty, last_block = await get_difficulty()
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
        'pending_transactions_hashes': [sha256(tx) for tx in pending_transactions],
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


# ==================== SMART CONTRACT ENDPOINTS ====================

@app.post("/deploy_contract")
@limiter.limit("5/minute")
async def deploy_contract(request: Request, data: dict = Body(...)):
    """Deploy a smart contract from hex transaction"""
    global vm_manager
    
    if not VM_AVAILABLE:
        return {'ok': False, 'error': 'Smart contract functionality not available'}
    
    if not vm_manager:
        return {'ok': False, 'error': 'VM Manager not initialized'}
    
    try:
        # Extract transaction hex
        tx_hex = data.get('transaction_hex')
        if not tx_hex:
            return {'ok': False, 'error': 'transaction_hex is required'}
        
        # Validate hex format
        try:
            # Remove 0x prefix if present for validation
            clean_hex = tx_hex[2:] if tx_hex.startswith('0x') else tx_hex
            bytes.fromhex(clean_hex)
        except ValueError:
            return {'ok': False, 'error': 'Invalid hex format'}
        
        # Parse the smart contract transaction
        try:
            sc_transaction = await SmartContractTransaction.from_hex(tx_hex)
        except Exception as e:
            return {'ok': False, 'error': f'Invalid transaction format: {str(e)}'}
        
        # Validate it's a deployment transaction
        if not sc_transaction.is_deployment():
            return {'ok': False, 'error': 'Transaction is not a contract deployment'}
        
        # Get sender from transaction inputs
        if not sc_transaction.inputs:
            return {'ok': False, 'error': 'Transaction must have inputs to determine sender'}
        
        sender = await sc_transaction.inputs[0].get_address()
        
        # Validate gas limit
        if sc_transaction.gas_limit <= 0:
            return {'ok': False, 'error': 'Gas limit must be positive'}
        
        if sc_transaction.gas_limit > StellarisVM.MAX_GAS_LIMIT:  # 10M gas limit
            return {'ok': False, 'error': f'Gas limit too high (max: {StellarisVM.MAX_GAS_LIMIT})'}
        
        # Execute deployment
        result = await vm_manager.deploy_contract(sc_transaction, sender)
        
        if result.success:
            # Calculate transaction hash
            tx_hash = sc_transaction.hash()
            
            # Add transaction to pending pool
            tx_added = await db.add_pending_transaction(sc_transaction)
            
            if not tx_added:
                return {
                    'ok': False,
                    'error': 'Failed to add transaction to pending pool - transaction verification failed',
                    'gas_used': result.gas_used
                }
            
            # Calculate gas fee
            gas_fee = sc_transaction.calculate_gas_fee()
            
            return {
                'ok': True,
                'result': {
                    'contract_address': result.result,
                    'gas_used': result.gas_used,
                    'gas_fee': str(gas_fee),
                    'transaction_hash': tx_hash,
                    'status': 'pending',
                    'block_number': None  # Will be set when mined
                }
            }
        else:
            return {
                'ok': False,
                'error': result.error,
                'gas_used': result.gas_used
            }
            
    except Exception as e:
        return {'ok': False, 'error': f'Internal server error: {str(e)}'}


@app.post("/call_contract")
@limiter.limit("10/minute")
async def call_contract(request: Request, data: dict = Body(...)):
    """Call a smart contract method from hex transaction"""
    global vm_manager
    
    if not VM_AVAILABLE:
        return {'ok': False, 'error': 'Smart contract functionality not available'}
    
    if not vm_manager:
        return {'ok': False, 'error': 'VM Manager not initialized'}
    
    try:
        # Extract transaction hex
        tx_hex = data.get('transaction_hex')
        if not tx_hex:
            return {'ok': False, 'error': 'transaction_hex is required'}
        
        # Validate hex format
        try:
            # Remove 0x prefix if present for validation
            clean_hex = tx_hex[2:] if tx_hex.startswith('0x') else tx_hex
            bytes.fromhex(clean_hex)
        except ValueError:
            return {'ok': False, 'error': 'Invalid hex format'}
        
        # Parse the smart contract transaction
        try:
            sc_transaction = await SmartContractTransaction.from_hex(tx_hex)
        except Exception as e:
            return {'ok': False, 'error': f'Invalid transaction format: {str(e)}'}
        
        # Validate it's a call transaction
        if not sc_transaction.is_call():
            return {'ok': False, 'error': 'Transaction is not a contract call'}
        
        # Get sender from transaction inputs
        if not sc_transaction.inputs:
            return {'ok': False, 'error': 'Transaction must have inputs to determine sender'}
        
        sender =  await sc_transaction.inputs[0].get_address()
        
        # Validate gas limit
        if sc_transaction.gas_limit <= 0:
            return {'ok': False, 'error': 'Gas limit must be positive'}
        
        # Validate contract exists
        contract_exists = await db.contract_exists(sc_transaction.contract_address)
        if not contract_exists:
            return {'ok': False, 'error': f'Contract not found at address {sc_transaction.contract_address}'}
        
        # Execute call
        result = await vm_manager.call_contract(sc_transaction, sender)
        
        if result.success:
            # Calculate transaction hash
            tx_hash = sc_transaction.hash()
            
            # Add transaction to pending pool
            tx_added = await db.add_pending_transaction(sc_transaction)
            
            if not tx_added:
                return {
                    'ok': False,
                    'error': 'Failed to add transaction to pending pool - transaction verification failed',
                    'gas_used': result.gas_used
                }
            
            # Calculate gas fee
            gas_fee = sc_transaction.calculate_gas_fee()
            
            return {
                'ok': True,
                'result': {
                    'return_value': result.result,
                    'gas_used': result.gas_used,
                    'gas_fee': str(gas_fee),
                    'transaction_hash': tx_hash,
                    'status': 'pending',
                    'block_number': None  # Will be set when mined
                }
            }
        else:
            return {
                'ok': False,
                'error': result.error,
                'gas_used': result.gas_used
            }
            
    except Exception as e:
        return {'ok': False, 'error': f'Internal server error: {str(e)}'}


@app.get("/get_contract_info")
@limiter.limit("20/minute")
async def get_contract_info(request: Request, contract_address: str, pretty: bool = False):
    """Get contract information"""
    global vm_manager
    
    if not vm_manager:
        result = {'ok': False, 'error': 'VM Manager not initialized'}
    else:
        try:
            contract_info = await vm_manager.get_contract_info(contract_address)
            if contract_info:
                result = {'ok': True, 'result': contract_info}
            else:
                result = {'ok': False, 'error': 'Contract not found'}
        except Exception as e:
            result = {'ok': False, 'error': str(e)}
    
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.post("/estimate_gas")
@limiter.limit("30/minute")
async def estimate_gas(request: Request):
    """Estimate gas for contract operation"""
    global vm_manager
    
    if not VM_AVAILABLE:
        return {'success': False, 'error': 'Smart contract functionality not available'}
    elif not vm_manager:
        return {'success': False, 'error': 'VM Manager not initialized'}
    
    try:
        # Parse request body
        body = await request.json()
        transaction_hex = body.get('transaction_hex')
        
        if not transaction_hex:
            return {'success': False, 'error': 'transaction_hex required'}
        
        # Parse transaction from hex
        from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
        transaction = await SmartContractTransaction.from_hex(transaction_hex)
        
        # Estimate gas based on transaction type
        if transaction.is_deployment():
            # Deployment estimation
            code_size = len(transaction.contract_code.encode('utf-8'))
            base_gas = 21000  # Base transaction cost
            deployment_gas = 32000  # Base deployment cost
            code_gas = code_size * 200  # Per byte cost
            estimated_gas = base_gas + deployment_gas + code_gas
            
            operation_type = "deployment"
        elif transaction.is_call():
            # Call estimation
            base_gas = 21000  # Base transaction cost
            call_gas = 9000   # Base call cost
            estimated_gas = base_gas + call_gas
            
            operation_type = "call"
        else:
            return {'success': False, 'error': 'Invalid transaction type'}
        
        # Ensure estimated gas doesn't exceed the transaction's gas limit
        final_estimate = min(estimated_gas, transaction.gas_limit)
        
        return {
            'success': True,
            'gas_estimate': final_estimate,
            'gas_limit': transaction.gas_limit,
            'operation_type': operation_type
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Gas estimation failed: {str(e)}'}


@app.get("/get_vm_stats")
@limiter.limit("10/minute")
async def get_vm_stats(request: Request, pretty: bool = False):
    """Get VM pool statistics"""
    global vm_manager
    
    if not VM_AVAILABLE:
        result = {'ok': False, 'error': 'Smart contract functionality not available'}
    elif not vm_manager:
        result = {'ok': False, 'error': 'VM Manager not initialized'}
    else:
        try:
            stats = vm_manager.get_stats()
            
            # Calculate additional metrics
            total_contracts = len(await db.get_all_contracts()) if hasattr(db, 'get_all_contracts') else 0
            
            result = {
                'ok': True,
                'result': {
                    'vm_pool': {
                        'total_vms': stats.total_vms,
                        'active_vms': stats.active_vms,
                        'available_vms': stats.total_vms - stats.active_vms
                    },
                    'execution_stats': {
                        'total_executions': stats.total_executions,
                        'pending_executions': stats.pending_executions,
                        'avg_execution_time': round(stats.avg_execution_time, 4),
                        'total_gas_used': stats.total_gas_used
                    },
                    'blockchain_stats': {
                        'total_contracts': total_contracts,
                        'vm_enabled': True
                    }
                }
            }
        except Exception as e:
            result = {'ok': False, 'error': f'Internal server error: {str(e)}'}
    
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_gas_price")
@limiter.limit("30/minute")
async def get_gas_price(request: Request, pretty: bool = False):
    """Get current gas price"""
    global vm_manager
    
    if not VM_AVAILABLE:
        result = {'ok': False, 'error': 'Smart contract functionality not available'}
    elif not vm_manager:
        result = {'ok': False, 'error': 'VM Manager not initialized'}
    else:
        try:
            gas_price = await vm_manager.blockchain_interface.get_gas_price()
            result = {
                'ok': True,
                'result': {
                    'gas_price': str(gas_price),
                    'unit': 'tokens_per_gas'
                }
            }
        except Exception as e:
            result = {'ok': False, 'error': f'Internal server error: {str(e)}'}
    
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_contracts_by_deployer")
@limiter.limit("10/minute")
async def get_contracts_by_deployer(request: Request, deployer_address: str, pretty: bool = False):
    """Get all contracts deployed by a specific address"""
    try:
        contracts = await db.get_contracts_by_deployer(deployer_address)
        result = {'ok': True, 'result': contracts}
    except Exception as e:
        result = {'ok': False, 'error': str(e)}
    
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


@app.get("/get_all_contracts")
@limiter.limit("5/minute")
async def get_all_contracts(request: Request, pretty: bool = False):
    """Get list of all contract addresses"""
    try:
        contracts = await db.get_all_contracts()
        result = {'ok': True, 'result': contracts}
    except Exception as e:
        result = {'ok': False, 'error': str(e)}
    
    return Response(content=json.dumps(result, indent=4, cls=CustomJSONEncoder), media_type="application/json") if pretty else result


# Initialize VM Manager when database is ready
async def initialize_vm_manager():
    """Initialize the VM Manager"""
    global vm_manager, db
    
    if not VM_AVAILABLE:
        print("⚠️  VM components not available, smart contract functionality disabled")
        return
    
    if db and not vm_manager:
        try:
            vm_manager = StellarisVMManager(
                database=db, 
                max_workers=4, 
                vm_pool_size=8,
                enable_caching=True
            )
            print("✅ VM Manager initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize VM Manager: {e}")
            import traceback
            traceback.print_exc()


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Decimal, datetime)):
            return str(o)  # Convert types to string to prevent serialization errors
        return super().default(o)