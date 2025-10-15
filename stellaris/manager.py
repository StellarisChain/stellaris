import hashlib
from decimal import Decimal
from io import BytesIO
from math import ceil, floor, log
from typing import Tuple, List, Union

from stellaris.database import Database, OLD_BLOCKS_TRANSACTIONS_ORDER
from stellaris.constants import MAX_SUPPLY, ENDIAN, MAX_BLOCK_SIZE_HEX, BLOCK_CONFIG
from stellaris.utils.general import sha256, timestamp, bytes_to_string, string_to_bytes
from stellaris.transactions import CoinbaseTransaction, TreasuryTransaction, Transaction, SmartContractTransaction
from stellaris.utils.block_utils import calculate_difficulty, difficulty_to_hashrate, BLOCK_TIME, BLOCKS_COUNT, START_DIFFICULTY

async def get_difficulty() -> Tuple[Decimal, dict]:
    if Manager.difficulty is None:
        Manager.difficulty = await calculate_difficulty()
    return Manager.difficulty


async def _process_smart_contract_transactions(transactions: List[Transaction], block_no: int, block_hash: str):
    """
    Process smart contract transactions when they are mined into a block.
    This ensures contract state is properly persisted.
    """
    try:
        # Try to import VM components
        from stellaris.svm.vm_manager import StellarisVMManager
        from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
        
        # Count smart contract transactions
        sc_transactions = [tx for tx in transactions if isinstance(tx, SmartContractTransaction)]
        if not sc_transactions:
            return  # No smart contract transactions to process
        
        print(f"📋 Processing {len(sc_transactions)} smart contract transaction(s) in block {block_no}")
        
        # Get or create VM manager instance
        database = Database.instance
        vm_manager = StellarisVMManager(database=database)
        
        for transaction in sc_transactions:
            try:
                # Get sender address from transaction inputs
                sender = await transaction.inputs[0].get_address() if transaction.inputs else "unknown"
                
                if transaction.is_deployment():
                    # For deployments, check if contract already exists (in case it was processed during API call)
                    contract_address = transaction.contract_address
                    existing_contract = await database.get_contract_state(contract_address) if contract_address else None
                    
                    if existing_contract:
                        print(f"✅ Contract already deployed (from API call): {contract_address}")
                        # Update deployment block if needed
                        if existing_contract.get('deployment_block', 0) == 0:
                            existing_contract['deployment_block'] = block_no
                            await database.save_contract_state(contract_address, existing_contract)
                    else:
                        print(f"🚀 Deploying contract in block {block_no}")
                        # Re-execute deployment to persist state
                        result = await vm_manager.deploy_contract(transaction, sender)
                        if result.success:
                            print(f"✅ Contract deployed at: {result.result}")
                            # Update with block info
                            contract_state = await database.get_contract_state(result.result)
                            if contract_state:
                                contract_state['deployment_block'] = block_no
                                await database.save_contract_state(result.result, contract_state)
                        else:
                            print(f"❌ Contract deployment failed: {result.error}")
                else:
                    print(f"📞 Executing contract call in block {block_no}: {transaction.contract_address}.{transaction.method_name}")
                    # Re-execute call to persist state changes
                    result = await vm_manager.call_contract(transaction, sender)
                    if result.success:
                        print(f"✅ Contract call successful")
                    else:
                        print(f"❌ Contract call failed: {result.error}")
                        
            except Exception as e:
                print(f"❌ Error processing smart contract transaction {transaction.hash()}: {e}")
                # Don't fail the entire block for SC errors, just log them
                continue
        
        print(f"✅ Finished processing smart contract transactions in block {block_no}")
                    
    except ImportError:
        # VM components not available, skip smart contract processing
        print("⚠️  Smart contract VM not available, skipping SC transaction processing")
        pass
    except Exception as e:
        print(f"⚠️  Error during smart contract processing: {e}")
        # Don't fail block creation for SC processing errors
        pass


async def check_block_is_valid(block_content: str, mining_info: tuple = None) -> bool:
    if mining_info is None:
        mining_info = await get_difficulty()
    difficulty, last_block = mining_info

    block_hash = sha256(block_content)

    if 'hash' not in last_block:
        return True

    last_block_hash = last_block['hash']

    decimal = difficulty % 1
    difficulty = floor(difficulty)
    if decimal > 0:
        charset = '0123456789abcdef'
        count = ceil(16 * (1 - decimal))
        return block_hash.startswith(last_block_hash[-difficulty:]) and block_hash[difficulty] in charset[:count]
    return block_hash.startswith(last_block_hash[-difficulty:])


def get_block_reward(number: int) -> Decimal:
    """
    Calculate block reward using the new power-of-two halving schedule.
    
    Initial Reward: 64 DNR (2^6)
    Halving Interval: 262,144 blocks (2^18)
    Maximum halvings: 64 (2^6)
    Maximum Supply: 33,554,432 DNR (2^25)
    """
    # Check if XML configuration is loaded and if block is after activation point
    activation_block = BLOCK_CONFIG.get('activation_block', 0)
    
    if number < activation_block:
        # Legacy reward schedule for blocks before activation
        divider = floor(number / 150000)
        if divider == 0:
            return Decimal(100)
        if divider > 8:
            if number < 150000 * 9 + 458732 - 150000:
                return Decimal('0.390625')
            elif number < 150000 * 9 + 458733 - 150000 + 320:
                return Decimal('0.3125')
            return Decimal(0)
        return Decimal(100) / (2 ** Decimal(divider))
    
    # New power-of-two reward schedule
    
    # Constants
    INITIAL_REWARD = Decimal(64)  # 2^6
    HALVING_INTERVAL = 262144     # 2^18
    MAX_HALVINGS = 64             # 2^6
    
    # Calculate halvings that have occurred
    halvings = min(number // HALVING_INTERVAL, MAX_HALVINGS)
    
    # If we've reached maximum halvings, reward is zero
    if halvings >= MAX_HALVINGS:
        return Decimal(0)
    
    # Calculate reward using binary right shift (division by powers of 2)
    reward = INITIAL_REWARD / (2 ** halvings)
    
    return reward


def __check():
    i = 1
    r = 0
    index = {}
    while n := get_block_reward(i):
        if n not in index:
            index[n] = 0
        index[n] += 1
        i += 1
        r += n

    print(r)
    print(MAX_SUPPLY - r)
    print(index)


async def clear_pending_transactions(transactions=None):
    """
    Normalizes inputs, removes duplicates, and prunes pending transactions with conflicting inputs.
    Parses hex strings into Transaction objects without signature checks.
    """
    database: Database = Database.instance
    await database.clear_duplicate_pending_transactions()
    
    # Get pending transactions if not provided
    transactions = transactions or await database.get_pending_transactions_limit(hex_only=True)
    
    # Track used inputs to detect conflicts
    used_inputs = []
    parsed_transactions = []
    
    # Parse all transactions first to normalize
    for transaction in transactions:
        if isinstance(transaction, str):
            try:
                tx = await Transaction.from_hex(transaction, check_signatures=False)
                tx_hash = sha256(transaction)
            except Exception:
                # Skip invalid transactions
                continue
        else:
            tx = transaction
            tx_hash = tx.hash()
            
        parsed_transactions.append((tx, tx_hash))
    
    # Process transactions to remove conflicts
    for tx, tx_hash in parsed_transactions:
        tx_inputs = [(tx_input.tx_hash, tx_input.index) for tx_input in tx.inputs]
        
        # Check if any input conflicts with already processed transactions
        if any(used_input in tx_inputs for used_input in used_inputs):
            await database.remove_pending_transaction(tx_hash)
            print(f'Removed conflicting transaction {tx_hash}')
            # Don't recurse anymore, just continue with next transaction
        else:
            # Add these inputs to used set
            used_inputs.extend(tx_inputs)
    unspent_outputs = await database.get_unspent_outputs(used_inputs)
    double_spend_inputs = set(used_inputs) - set(unspent_outputs)
    if double_spend_inputs == set(used_inputs):
        await database.remove_pending_transactions()
    elif double_spend_inputs:
        await database.remove_pending_transactions_by_contains([tx_input[0] + bytes([tx_input[1]]).hex() for tx_input in double_spend_inputs])


def get_transactions_merkle_tree(transactions: List[Union[Transaction, str]]):
    """
    Compute a deterministic Merkle root from sorted transaction hash hex strings.
    Concatenates the sorted hashes and applies a single SHA-256 operation.
    Returns the resulting hash as a hex string.
    """
    # Collect transaction hashes
    tx_hashes = []
    for transaction in transactions:
        if isinstance(transaction, Transaction):
            tx_hashes.append(transaction.hash())
        else:
            # If it's already a hex string, hash it to get the transaction hash
            tx_hashes.append(sha256(transaction))
    
    # Sort the hashes for deterministic ordering
    tx_hashes.sort()
    
    # Concatenate the sorted hashes and hash the result
    concat_hashes = ''.join(tx_hashes)
    return sha256(concat_hashes)


def get_transactions_size(transactions: List[Transaction]):
    return sum(len(transaction.hex()) for transaction in transactions)


def block_to_bytes(last_block_hash: str, block: dict) -> bytes:
    address_bytes = string_to_bytes(block['address'])
    version = bytes([])
    if len(address_bytes) != 64:
        version = bytes([2])
    return version + \
           bytes.fromhex(last_block_hash) + \
           address_bytes + \
           bytes.fromhex(block['merkle_tree']) + \
           block['timestamp'].to_bytes(4, byteorder=ENDIAN) + \
           int(float(block['difficulty']) * 10).to_bytes(2, ENDIAN) \
           + block['random'].to_bytes(4, ENDIAN)


def split_block_content(block_content: str):
    """
    Parse block content hex string into components.
    Infers version 1 from total length or reads a version byte.
    Returns (previous_hash, address, merkle_tree, timestamp, difficulty, random)
    """
    _bytes = bytes.fromhex(block_content)
    stream = BytesIO(_bytes)
    
    # Infer version from content length
    if len(_bytes) == 138:
        version = 1
    else:
        # Read version byte
        version = int.from_bytes(stream.read(1), ENDIAN)
    
    # Read block components
    previous_hash = stream.read(32).hex()
    address = bytes_to_string(stream.read(64 if version == 1 else 33))
    merkle_tree = stream.read(32).hex()
    timestamp = int.from_bytes(stream.read(4), ENDIAN)
    difficulty = int.from_bytes(stream.read(2), ENDIAN) / Decimal(10)
    random = int.from_bytes(stream.read(4), ENDIAN)
    
    return previous_hash, address, merkle_tree, timestamp, difficulty, random


async def check_block(block_content: str, transactions: List[Transaction], mining_info: tuple = None):
    if mining_info is None:
        mining_info = await calculate_difficulty()
    difficulty, last_block = mining_info
    
    # First validate PoW
    if not await check_block_is_valid(block_content, mining_info):
        print('Block PoW validation failed')
        return False
    
    # Extract block components
    block_no = last_block['id'] + 1 if last_block != {} else 1
    previous_hash, address, merkle_tree, content_time, content_difficulty, random = split_block_content(block_content)
    block_hash = sha256(block_content)
    content_time = int(content_time)
    
    # Verify previous hash link
    if last_block != {} and previous_hash != last_block['hash']:
        print('Previous hash does not match the last block hash')
        return False

    # Validate timestamp
    last_block_time = last_block.get('timestamp', 0)
    if last_block_time >= content_time:
        print('Timestamp not strictly increasing from previous block')
        return False
    
    current_time = timestamp()
    if content_time > current_time + 120:  # Allow at most 120 seconds in the future
        print(f'Timestamp too far in the future: {content_time} vs {current_time}')
        return False

    # Filter regular transactions and check size limits
    transactions = [tx for tx in transactions if isinstance(tx, Transaction)]
    if get_transactions_size(transactions) > MAX_BLOCK_SIZE_HEX:
        print('Block is too big')
        return False
    
    # Content size check
    if len(block_content) > MAX_BLOCK_SIZE_HEX * 2:  # *2 for hex representation
        print('Block content is too large')
        return False

    # Validate inputs and double-spend protection
    database: Database = Database.instance
    if transactions:
        # Collect all inputs as (tx_hash, index) pairs
        check_inputs = sum([[(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs] 
                           for transaction in transactions], [])
        
        # Check for in-block duplicate inputs
        if len(set(check_inputs)) != len(check_inputs):
            print('Duplicate inputs detected in block')
            return False
            
        # Verify all inputs correspond to available UTXOs
        unspent_outputs = await database.get_unspent_outputs(check_inputs)
        if set(check_inputs) - set(unspent_outputs) != set():
            print('Some inputs reference spent or non-existent outputs')
            return False
            
        # Load input transactions for verification
        input_txs_hash = sum([[tx_input.tx_hash for tx_input in transaction.inputs] 
                             for transaction in transactions], [])
        input_txs = await database.get_transactions_info(input_txs_hash)
        
        # Fill transaction inputs with referenced outputs
        for transaction in transactions:
            await transaction._fill_transaction_inputs(input_txs)

    # Verify each transaction individually
    for transaction in transactions:
        if not await transaction.verify(check_double_spend=False):
            print(f'Transaction {transaction.hash()} failed verification')
            return False

    # Compute and validate Merkle root
    transactions_merkle_tree = get_transactions_merkle_tree(transactions)
    if merkle_tree != transactions_merkle_tree:
        print('Merkle tree does not match')
        return False

    return True


async def create_block(block_content: str, transactions: List[Transaction], last_block: dict = None):
    # Reset cached difficulty
    Manager.difficulty = None
    
    # Get current difficulty for validation
    if last_block is None or last_block['id'] % BLOCKS_COUNT == 0:
        difficulty, last_block = await calculate_difficulty()
    else:
        difficulty, last_block = await get_difficulty()
    
    # Validate the candidate block
    if not await check_block(block_content, transactions, (difficulty, last_block)):
        return False

    database: Database = Database.instance
    block_no = last_block['id'] + 1 if last_block != {} else 1
    block_hash = sha256(block_content)
    previous_hash, address, merkle_tree, content_time, content_difficulty, random = split_block_content(block_content)
    
    # Calculate fees from regular transactions
    fees = sum(transaction.fees for transaction in transactions)

    # Compute block reward based on updated schedule
    block_reward = get_block_reward(block_no)
    
    # Treasury tax handling with improved precision and validation
    treasury_config = BLOCK_CONFIG.get('treasury', {})
    tax_rate = Decimal(str(treasury_config.get('tax_rate', 0.25)))
    treasury_address = treasury_config.get('wallet_address')
    
    # Validate tax rate is within bounds
    if tax_rate < 0 or tax_rate > Decimal('1.0'):
        print(f"Warning: Invalid tax rate {tax_rate}, using default 0.25")
        tax_rate = Decimal('0.25')
    
    # Check if this is a treasury distribution block
    treasury_transaction = None
    if await database.is_treasury_distribution_block(block_no):
        # Calculate treasury distribution amount
        accumulated_fees = await database.get_accumulated_treasury_fees()
        treasury_amount = accumulated_fees
        
        if treasury_amount > 0 and treasury_address:
            # Calculate the period for this distribution
            tax_interval = treasury_config.get('tax_interval', 25000)
            start_block = max(1, block_no - tax_interval + 1)  # Ensure start_block >= 1
            end_block = block_no
            
            # Create treasury transaction
            treasury_transaction = TreasuryTransaction(
                block_hash, treasury_address, treasury_amount, start_block, end_block
            )
            
            # Record the distribution
            try:
                await database.distribute_treasury_funds(block_no, treasury_amount)
                print(f"Treasury distribution: {treasury_amount} to {treasury_address} for blocks {start_block}-{end_block}")
            except ValueError as e:
                print(f"Treasury distribution failed: {e}")
                treasury_transaction = None
    
    # Calculate tax portion of current fees for accumulation
    if fees > 0:
        # Use proper Decimal arithmetic to maintain precision
        treasury_tax = (fees * tax_rate).quantize(Decimal('0.000001'))
        miner_fees = fees - treasury_tax
        
        # Accumulate treasury portion (with validation in database method)
        try:
            await database.accumulate_treasury_fees(treasury_tax)
        except ValueError as e:
            print(f"Treasury accumulation failed: {e}")
            # If accumulation fails, give all fees to miner
            miner_fees = fees
    else:
        miner_fees = fees
    
    # Create coinbase transaction (miner gets reward + reduced fees)
    coinbase_transaction = CoinbaseTransaction(block_hash, address, block_reward + miner_fees)
    if not coinbase_transaction.outputs[0].verify():
        print("Coinbase output verification failed")
        return False

    # Perform a grouped commit for the entire block with a single try/except
    try:
        # Add block (use total fees for block record)
        await database.add_block(block_no, block_hash, block_content, address, random, 
                                content_difficulty, block_reward + fees, content_time)
        
        # Add coinbase transaction
        await database.add_transaction(coinbase_transaction, block_hash)
        
        # Add treasury transaction if this is a distribution block
        if treasury_transaction:
            await database.add_transaction(treasury_transaction, block_hash)
        
        # Add regular transactions
        await database.add_transactions(transactions, block_hash)
        
        # Process smart contract transactions in the block
        await _process_smart_contract_transactions(transactions, block_no, block_hash)
        
    except Exception as e:
        print(f'a transaction has not been added in block', e)
        await database.delete_block(block_no)
        return False
    
    # Prepare transactions for unspent outputs
    all_special_transactions = [coinbase_transaction]
    if treasury_transaction:
        all_special_transactions.append(treasury_transaction)
    
    await database.add_unspent_transactions_outputs(transactions + all_special_transactions)
    if transactions:
        await database.remove_pending_transactions_by_hash([transaction.hash() for transaction in transactions])
        await database.remove_unspent_outputs(transactions)
        await database.remove_pending_spent_outputs(transactions)

        treasury_info = f", Treasury: {treasury_tax if fees > 0 else 0}" if fees > 0 else ""
        treasury_dist_info = f", Treasury Distribution: {treasury_transaction.amount}" if treasury_transaction else ""
        print(f'Added {len(transactions)} transactions in block {block_no}. Reward: {block_reward}, Miner Fees: {miner_fees}{treasury_info}{treasury_dist_info}')
    Manager.difficulty = None
    return True


class Manager:
    difficulty: Tuple[float, dict] = None