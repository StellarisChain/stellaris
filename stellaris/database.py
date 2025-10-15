import os
import json
import gzip
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
from typing import List, Union, Tuple, Dict
from pathlib import Path

import pickledb

from stellaris.constants import MAX_BLOCK_SIZE_HEX, SMALLEST
from stellaris.utils.general import sha256, point_to_string, string_to_point, point_to_bytes, AddressFormat, normalize_block
from stellaris.transactions import Transaction, CoinbaseTransaction, TreasuryTransaction, TransactionInput

dir_path = os.path.dirname(os.path.realpath(__file__))
OLD_BLOCKS_TRANSACTIONS_ORDER = pickledb.load(dir_path + '/old_block_transactions_order.json', True)


class Database:
    instance = None
    
    async def _parse_transaction_from_hex(self, tx_hex: str, check_signatures: bool = True) -> Transaction:
        """
        Parse a transaction from hex, handling both regular and smart contract transactions.
        """
        try:
            # Check if this is a smart contract transaction (version 4)
            clean_hex = tx_hex[2:] if tx_hex.startswith('0x') else tx_hex
            tx_bytes = bytes.fromhex(clean_hex)
            version = int.from_bytes(tx_bytes[:1], 'big')
            
            if version == 4:
                # This is a smart contract transaction
                from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
                return await SmartContractTransaction.from_hex(tx_hex, check_signatures)
            else:
                # Regular transaction
                return await Transaction.from_hex(tx_hex, check_signatures)
        except Exception:
            # Fallback to regular transaction parsing
            return await Transaction.from_hex(tx_hex, check_signatures)
    
    def __init__(self):
        self.data_dir = None
        self.blocks_file = None
        self.transactions_file = None
        self.pending_transactions_file = None
        self.unspent_outputs_file = None
        self.pending_spent_outputs_file = None
        # Smart contract related storage
        self.contracts_file = None
        self.contract_storage_file = None
        # Treasury tracking
        self.treasury_file = None
        
        self._blocks = {}
        self._transactions = {}
        self._pending_transactions = {}
        self._unspent_outputs = set()
        self._pending_spent_outputs = set()
        self._transaction_block_map = {}
        # Smart contract storage
        self._contracts = {}
        self._contract_storage = {}
        # Treasury data: accumulated fees and distributions
        self._treasury_data = {
            'accumulated_fees': '0',  # Store as string for precision
            'total_distributed': '0',
            'distributions': {},  # block_number -> amount
            'last_distribution_block': 0
        }
        
        self.is_indexed = True
        self._lock = asyncio.Lock()

    @staticmethod
    async def create(data_dir='./data/database', **kwargs):
        self = Database()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.blocks_file = self.data_dir / 'blocks.json.gz'
        self.transactions_file = self.data_dir / 'transactions.json.gz'
        self.pending_transactions_file = self.data_dir / 'pending_transactions.json.gz'
        self.unspent_outputs_file = self.data_dir / 'unspent_outputs.json.gz'
        self.pending_spent_outputs_file = self.data_dir / 'pending_spent_outputs.json.gz'
        # Smart contract files
        self.contracts_file = self.data_dir / 'contracts.json.gz'
        self.contract_storage_file = self.data_dir / 'contract_storage.json.gz'
        # Treasury file
        self.treasury_file = self.data_dir / 'treasury.json.gz'
        
        await self._load_data()
        Database.instance = self
        return self

    @staticmethod
    async def get():
        if Database.instance is None:
            await Database.create()
        return Database.instance

    async def _save_to_file_unlocked(self, file_path: Path, data):
        """Save data to compressed JSON file without acquiring lock (lock should already be held)"""
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    async def _save_to_file(self, file_path: Path, data):
        """Save data to compressed JSON file"""
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=5.0)
            try:
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
            finally:
                self._lock.release()
        except asyncio.TimeoutError:
            raise Exception(f"Database deadlock detected for {file_path}")
        except Exception as e:
            raise

    async def _load_from_file(self, file_path: Path):
        """Load data from compressed JSON file with advanced recovery for corrupted files"""
        if not file_path.exists():
            return {}
            
        # First try normal loading
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, EOFError) as e:
            print(f"Error loading {file_path.name}: {str(e)}. Attempting recovery...")
            
            # Create a backup of the corrupted file
            import shutil
            import datetime
            import io
            import zlib
            
            backup_path = file_path.with_name(f"{file_path.stem}_corrupted_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz.bak")
            try:
                shutil.copy2(file_path, backup_path)
                print(f"Created backup of corrupted file at {backup_path}")
            except Exception as backup_error:
                print(f"Failed to create backup: {backup_error}")
            
            # Advanced recovery attempts
            recovered_data = {}
            
            # Attempt 1: Try to decompress as much as possible using binary reading
            try:
                print(f"Recovery attempt 1: Extracting partial gzip data from {file_path.name}...")
                
                with open(file_path, 'rb') as f_in:
                    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)  # gzip format
                    decompressed_data = b''
                    
                    # Read and decompress in chunks to get as much as possible
                    chunk_size = 1024
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        
                        try:
                            decompressed_data += decompressor.decompress(chunk)
                        except Exception:
                            # Reached corrupted part, try to use what we have
                            break
                    
                    # Try to get any remaining data
                    try:
                        decompressed_data += decompressor.flush()
                    except Exception:
                        pass
                    
                # Try to parse as JSON
                if decompressed_data:
                    try:
                        # Try to clean the data by finding the last valid JSON object closing
                        text_data = decompressed_data.decode('utf-8')
                        
                        # Find the last complete JSON object
                        last_closing_brace = text_data.rfind('}')
                        if last_closing_brace > 0:
                            # Count opening and closing braces to ensure we have valid JSON
                            open_count = text_data[:last_closing_brace+1].count('{')
                            close_count = text_data[:last_closing_brace+1].count('}')
                            
                            # If we have balanced braces, try to parse the truncated JSON
                            if open_count == close_count:
                                recovered_data = json.loads(text_data[:last_closing_brace+1])
                                print(f"Successfully recovered data with {len(recovered_data)} entries!")
                                return recovered_data
                            else:
                                # Try more aggressive recovery by finding balanced JSON
                                print("Trying advanced JSON structure recovery...")
                                
                                # Extract individual JSON objects if this is a collection of objects
                                if text_data.lstrip().startswith('{'):
                                    brace_level = 0
                                    start_idx = 0
                                    objects = []
                                    
                                    for i, char in enumerate(text_data):
                                        if char == '{':
                                            if brace_level == 0:
                                                start_idx = i
                                            brace_level += 1
                                        elif char == '}':
                                            brace_level -= 1
                                            if brace_level == 0:
                                                try:
                                                    obj = json.loads(text_data[start_idx:i+1])
                                                    if isinstance(obj, dict) and len(obj) > 0:
                                                        key = next(iter(obj.keys()))
                                                        objects.append((key, obj))
                                                except:
                                                    pass
                                    
                                    if objects:
                                        recovered_data = dict(objects)
                                        print(f"Advanced recovery successful: recovered {len(recovered_data)} transactions!")
                                        return recovered_data
                    except Exception as json_err:
                        print(f"JSON recovery failed: {json_err}")
                        
            except Exception as recovery_err:
                print(f"Recovery attempt 1 failed: {recovery_err}")
                
            # Attempt 2: Try to recover individual transactions from the file
            try:
                print(f"Recovery attempt 2: Searching for valid JSON objects in {file_path.name}...")
                # Use external tool if available or fallback to manual extraction
                import subprocess
                import tempfile
                
                with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_out:
                    temp_name = temp_out.name
                
                # Try using zcat to extract what it can
                try:
                    subprocess.run(['zcat', '-f', str(file_path)], stdout=open(temp_name, 'w'), stderr=subprocess.PIPE)
                    
                    with open(temp_name, 'r') as f:
                        text = f.read()
                        
                    if text and '{' in text:
                        # Try to find complete JSON objects
                        try:
                            # This may be a JSON object collection, try to parse individual items
                            parsed_data = {}
                            
                            # Process each potential object
                            i = 0
                            while i < len(text):
                                start = text.find('{', i)
                                if start == -1:
                                    break
                                    
                                # Find matching closing brace
                                brace_count = 1
                                j = start + 1
                                while j < len(text) and brace_count > 0:
                                    if text[j] == '{':
                                        brace_count += 1
                                    elif text[j] == '}':
                                        brace_count -= 1
                                    j += 1
                                
                                if brace_count == 0:  # Found complete object
                                    try:
                                        obj = json.loads(text[start:j])
                                        if isinstance(obj, dict) and len(obj) >= 2 and 'tx_hash' in obj:
                                            # This is likely a transaction record
                                            parsed_data[obj.get('tx_hash', f'recovered_{len(parsed_data)}')] = obj
                                    except:
                                        pass
                                
                                i = j
                            
                            if parsed_data:
                                print(f"Recovered {len(parsed_data)} transactions!")
                                return parsed_data
                        except Exception as parse_err:
                            print(f"JSON parsing in recovery attempt 2 failed: {parse_err}")
                except Exception as zcat_err:
                    print(f"zcat recovery failed: {zcat_err}")
                
                # Clean up temp file
                try:
                    import os
                    os.unlink(temp_name)
                except:
                    pass
                    
            except Exception as recovery2_err:
                print(f"Recovery attempt 2 failed: {recovery2_err}")
            
            # If we got some data but not all, warn the user
            if recovered_data:
                print(f"Partial recovery successful: recovered {len(recovered_data)} entries. Some data may be lost.")
                return recovered_data
            
            print(f"All recovery attempts failed for {file_path.name}. Using empty data. Some transactions may be lost.")
            return {}

    async def _load_data(self):
        """Load all data from files"""
        self._blocks = await self._load_from_file(self.blocks_file)
        self._transactions = await self._load_from_file(self.transactions_file)
        self._pending_transactions = await self._load_from_file(self.pending_transactions_file)
        
        # Load smart contract data
        self._contracts = await self._load_from_file(self.contracts_file)
        self._contract_storage = await self._load_from_file(self.contract_storage_file)
        
        # Load treasury data
        treasury_data = await self._load_from_file(self.treasury_file)
        if treasury_data:
            self._treasury_data.update(treasury_data)
        
        unspent_data = await self._load_from_file(self.unspent_outputs_file)
        self._unspent_outputs = set(tuple(item) for item in unspent_data.get('outputs', []))
        
        pending_spent_data = await self._load_from_file(self.pending_spent_outputs_file)
        self._pending_spent_outputs = set(tuple(item) for item in pending_spent_data.get('outputs', []))
        
        # Build transaction to block mapping
        for tx_hash, tx_data in self._transactions.items():
            if 'block_hash' in tx_data:
                self._transaction_block_map[tx_hash] = tx_data['block_hash']

    async def _save_blocks(self):
        await self._save_to_file(self.blocks_file, self._blocks)

    async def _save_transactions(self):
        await self._save_to_file(self.transactions_file, self._transactions)

    async def _save_pending_transactions(self):
        await self._save_to_file(self.pending_transactions_file, self._pending_transactions)

    async def _save_unspent_outputs(self):
        data = {'outputs': list(self._unspent_outputs)}
        await self._save_to_file(self.unspent_outputs_file, data)

    async def _save_pending_spent_outputs(self):
        data = {'outputs': list(self._pending_spent_outputs)}
        await self._save_to_file(self.pending_spent_outputs_file, data)
    
    async def _save_treasury_data(self):
        await self._save_to_file(self.treasury_file, self._treasury_data)

    async def add_pending_transaction(self, transaction: Transaction, verify: bool = True):
        if isinstance(transaction, CoinbaseTransaction):
            print(f"Debug: Cannot add coinbase transaction to pending pool")
            return False
        tx_hex = transaction.hex()
        if verify:
            print(f"Debug: Verifying transaction before adding to pending pool...")
            verification_result = await transaction.verify_pending()
            print(f"Debug: Verification result: {verification_result}")
            if not verification_result:
                print(f"Debug: Verification failed for tx {tx_hex[:100]}...")
                return False
        
        tx_hash = sha256(tx_hex)
        utc_datetime = datetime.now(timezone.utc)
        
        self._pending_transactions[tx_hash] = {
            'tx_hash': tx_hash,
            'tx_hex': tx_hex,
            'inputs_addresses': [point_to_string(await tx_input.get_public_key()) for tx_input in transaction.inputs],
            'fees': transaction.fees,
            'time_received': utc_datetime.isoformat(),
            'propagation_time': utc_datetime.isoformat()
        }
        
        await self._save_pending_transactions()
        await self.add_transactions_pending_spent_outputs([transaction])
        return True

    async def remove_pending_transaction(self, tx_hash: str):
        if tx_hash in self._pending_transactions:
            del self._pending_transactions[tx_hash]
            await self._save_pending_transactions()

    async def remove_pending_transactions_by_hash(self, tx_hashes: List[str]):
        for tx_hash in tx_hashes:
            if tx_hash in self._pending_transactions:
                del self._pending_transactions[tx_hash]
        await self._save_pending_transactions()

    async def remove_pending_transactions(self):
        self._pending_transactions.clear()
        await self._save_pending_transactions()

    async def delete_blockchain(self):
        self._blocks.clear()
        self._transactions.clear()
        self._transaction_block_map.clear()
        await self._save_blocks()
        await self._save_transactions()

    async def delete_block(self, id: int):
        block_to_remove = None
        for block_hash, block_data in self._blocks.items():
            if block_data.get('id') == id:
                block_to_remove = block_hash
                break
        
        if block_to_remove:
            # Remove transactions for this block
            txs_to_remove = []
            for tx_hash, tx_data in self._transactions.items():
                if tx_data.get('block_hash') == block_to_remove:
                    txs_to_remove.append(tx_hash)
            
            for tx_hash in txs_to_remove:
                del self._transactions[tx_hash]
                if tx_hash in self._transaction_block_map:
                    del self._transaction_block_map[tx_hash]
            
            del self._blocks[block_to_remove]
            await self._save_blocks()
            await self._save_transactions()

    async def delete_blocks(self, offset: int):
        blocks_to_remove = []
        for block_hash, block_data in self._blocks.items():
            if block_data.get('id', 0) > offset:
                blocks_to_remove.append(block_hash)
        
        for block_hash in blocks_to_remove:
            await self.delete_block(self._blocks[block_hash]['id'])

    async def remove_blocks(self, block_no: int):
        blocks_to_remove = await self.get_blocks(block_no, 500)
        transactions_to_remove = []
        transactions_hashes = []
        
        for block_data in blocks_to_remove:
            block = block_data['block']
            transactions = block_data['transactions']
            transactions_to_remove.extend([await Transaction.from_hex(tx, False) for tx in transactions])
            transactions_hashes.extend([sha256(tx) for tx in transactions])
        
        outputs_to_be_restored = []
        for transaction in transactions_to_remove:
            if isinstance(transaction, Transaction):
                outputs_to_be_restored.extend([(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs if tx_input.tx_hash not in transactions_hashes])
        
        # Remove blocks and their transactions
        for block_data in blocks_to_remove:
            block = block_data['block']
            block_hash = block['hash']
            if block_hash in self._blocks:
                del self._blocks[block_hash]
                
            # Remove transactions for this block
            txs_to_remove = []
            for tx_hash, tx_data in self._transactions.items():
                if tx_data.get('block_hash') == block_hash:
                    txs_to_remove.append(tx_hash)
            
            for tx_hash in txs_to_remove:
                del self._transactions[tx_hash]
                if tx_hash in self._transaction_block_map:
                    del self._transaction_block_map[tx_hash]
        
        await self._save_blocks()
        await self._save_transactions()
        await self.add_unspent_outputs(outputs_to_be_restored)

    async def get_pending_transactions_limit(self, limit: int = MAX_BLOCK_SIZE_HEX, hex_only: bool = False, check_signatures: bool = True) -> List[Union[Transaction, str]]:
        # Sort by fee efficiency (fees per byte), then by size, then by tx_hex
        pending_txs = list(self._pending_transactions.values())
        def safe_fee(tx):
            fee = tx.get('fees', 0)
            if fee is None:
                fee = 0
            # Ensure fee is numeric (convert from string if necessary due to JSON serialization)
            try:
                fee = float(fee) if isinstance(fee, str) else fee
            except (ValueError, TypeError):
                fee = 0
            return -fee / len(tx['tx_hex']), len(tx['tx_hex']), tx['tx_hex']
        pending_txs.sort(key=safe_fee)
        
        return_txs = []
        size = 0
        for tx_data in pending_txs:
            tx_hex = tx_data['tx_hex']
            if size + len(tx_hex) > limit:
                break
            return_txs.append(tx_hex)
            size += len(tx_hex)
        
        if hex_only:
            return return_txs
        return [await Transaction.from_hex(tx_hex, check_signatures) for tx_hex in return_txs]

    async def get_need_propagate_transactions(self, last_propagation_delta: int = 600, limit: int = MAX_BLOCK_SIZE_HEX) -> List[Union[Transaction, str]]:
        current_time = datetime.now(timezone.utc)
        pending_txs = list(self._pending_transactions.values())
        from decimal import Decimal, InvalidOperation
        def safe_fee(tx):
            fee = tx.get('fees', 0)
            if fee is None:
                fee = 0
            # Ensure fee is numeric (convert from string if necessary due to JSON serialization)
            try:
                fee = Decimal(str(fee)) if not isinstance(fee, Decimal) else fee
            except (ValueError, TypeError, InvalidOperation):
                fee = Decimal(0)
            return -fee / len(tx['tx_hex']), len(tx['tx_hex']), tx['tx_hex']
        pending_txs.sort(key=safe_fee)
        
        return_txs = []
        size = 0
        for tx_data in pending_txs:
            tx_hex = tx_data['tx_hex']
            if size + len(tx_hex) > limit:
                break
            size += len(tx_hex)
            
            propagation_time = datetime.fromisoformat(tx_data['propagation_time'].replace('Z', '+00:00'))
            if (current_time - propagation_time).total_seconds() > last_propagation_delta:
                return_txs.append(tx_hex)
        
        return return_txs

    async def update_pending_transactions_propagation_time(self, txs_hash: List[str]):
        current_time = datetime.now(timezone.utc)
        for tx_hash in txs_hash:
            if tx_hash in self._pending_transactions:
                self._pending_transactions[tx_hash]['propagation_time'] = current_time.isoformat()
        await self._save_pending_transactions()

    async def get_next_block_average_fee(self):
        limit = MAX_BLOCK_SIZE_HEX
        pending_txs = list(self._pending_transactions.values())
        pending_txs.sort(key=lambda tx: (-float(tx['fees']) / len(tx['tx_hex']), len(tx['tx_hex'])))
        
        fees = []
        size = 0
        for tx_data in pending_txs:
            tx_size = len(tx_data['tx_hex'])
            if size + tx_size > limit:
                break
            fees.append(tx_data['fees'])
            size += tx_size
        
        if not fees:
            return 0
        return int(mean(fees) * SMALLEST) // Decimal(SMALLEST)

    async def get_pending_blocks_count(self):
        total_size = sum(len(tx_data['tx_hex']) for tx_data in self._pending_transactions.values())
        return int(total_size / MAX_BLOCK_SIZE_HEX + 1)

    async def clear_duplicate_pending_transactions(self):
        to_remove = []
        for tx_hash in self._pending_transactions:
            if tx_hash in self._transactions:
                to_remove.append(tx_hash)
        
        for tx_hash in to_remove:
            del self._pending_transactions[tx_hash]
        
        if to_remove:
            await self._save_pending_transactions()

    async def add_transaction(self, transaction: Union[Transaction, CoinbaseTransaction, TreasuryTransaction], block_hash: str):
        await self.add_transactions([transaction], block_hash)

    async def add_transactions(self, transactions: List[Union[Transaction, CoinbaseTransaction, TreasuryTransaction]], block_hash: str):
        block_timestamp = None
        if block_hash in self._blocks:
            block_timestamp = self._blocks[block_hash].get('timestamp')
        
        for transaction in transactions:
            tx_hash = transaction.hash()
            
            # Get time_received from pending transactions or use block timestamp
            time_received = None
            if isinstance(transaction, Transaction) and tx_hash in self._pending_transactions:
                time_received = self._pending_transactions[tx_hash].get('time_received')
            elif hasattr(transaction, 'treasury_address') and block_timestamp:  # TreasuryTransaction
                time_received = block_timestamp
            elif isinstance(transaction, CoinbaseTransaction) and block_timestamp:
                time_received = block_timestamp
            
            self._transactions[tx_hash] = {
                'block_hash': block_hash,
                'tx_hash': tx_hash,
                'tx_hex': transaction.hex(),
                'inputs_addresses': [point_to_string(await tx_input.get_public_key()) for tx_input in transaction.inputs] if isinstance(transaction, Transaction) else [],
                'outputs_addresses': [tx_output.address for tx_output in transaction.outputs],
                'outputs_amounts': [tx_output.amount * SMALLEST for tx_output in transaction.outputs],
                'fees': transaction.fees if isinstance(transaction, Transaction) else 0,
                'time_received': time_received,
                'is_treasury': hasattr(transaction, 'treasury_address')  # Mark treasury transactions
            }
            
            self._transaction_block_map[tx_hash] = block_hash
        
        await self._save_transactions()

    async def add_block(self, id: int, block_hash: str, block_content: str, address: str, random: int, difficulty: Decimal, reward: Decimal, timestamp: Union[datetime, int]):
        if isinstance(timestamp, int):
            timestamp = datetime.utcfromtimestamp(timestamp)
        
        self._blocks[block_hash] = {
            'id': id,
            'hash': block_hash,
            'content': block_content,
            'address': address,
            'random': random,
            'difficulty': float(difficulty),
            'reward': float(reward),
            'timestamp': timestamp.isoformat()
        }
        
        await self._save_blocks()
        
        # Clear difficulty cache
        from stellaris.manager import Manager
        Manager.difficulty = None

    async def get_transaction(self, tx_hash: str, check_signatures: bool = True) -> Union[Transaction, CoinbaseTransaction]:
        if tx_hash not in self._transactions:
            return None
        
        tx_data = self._transactions[tx_hash]
        tx = await Transaction.from_hex(tx_data['tx_hex'], check_signatures)
        tx.block_hash = tx_data['block_hash']
        return tx

    async def get_transaction_info(self, tx_hash: str) -> dict:
        return self._transactions.get(tx_hash)

    async def get_transactions_info(self, tx_hashes: List[str]) -> Dict[str, dict]:
        return {tx_hash: self._transactions[tx_hash] for tx_hash in tx_hashes if tx_hash in self._transactions}

    async def get_pending_transaction(self, tx_hash: str, check_signatures: bool = True) -> Transaction:
        if tx_hash not in self._pending_transactions:
            return None
        
        tx_data = self._pending_transactions[tx_hash]
        return await self._parse_transaction_from_hex(tx_data['tx_hex'], check_signatures)

    async def get_pending_transactions_by_hash(self, hashes: List[str], check_signatures: bool = True) -> List[Transaction]:
        result = []
        for tx_hash in hashes:
            if tx_hash in self._pending_transactions:
                tx_data = self._pending_transactions[tx_hash]
                result.append(await self._parse_transaction_from_hex(tx_data['tx_hex'], check_signatures))
        return result

    async def get_transactions(self, tx_hashes: List[str]):
        result = {}
        for tx_hash in tx_hashes:
            if tx_hash in self._transactions:
                tx_data = self._transactions[tx_hash]
                tx = await Transaction.from_hex(tx_data['tx_hex'])
                result[sha256(tx_data['tx_hex'])] = tx
        return result

    async def get_transaction_hash_by_contains_multi(self, contains: List[str], ignore: str = None):
        for tx_hash, tx_data in self._transactions.items():
            if ignore and tx_hash == ignore:
                continue
            if any(contain in tx_data['tx_hex'] for contain in contains):
                return tx_hash
        return None

    async def get_pending_transactions_by_contains(self, contains: str):
        result = []
        for tx_hash, tx_data in self._pending_transactions.items():
            if contains in tx_data['tx_hex'] and tx_hash != contains:
                result.append(await Transaction.from_hex(tx_data['tx_hex']))
        return result if result else None

    async def remove_pending_transactions_by_contains(self, search: List[str]) -> None:
        to_remove = []
        for tx_hash, tx_data in self._pending_transactions.items():
            if any(s in tx_data['tx_hex'] for s in search):
                to_remove.append(tx_hash)
        
        for tx_hash in to_remove:
            del self._pending_transactions[tx_hash]
        
        if to_remove:
            await self._save_pending_transactions()

    async def get_pending_transaction_by_contains_multi(self, contains: List[str], ignore: str = None):
        for tx_hash, tx_data in self._pending_transactions.items():
            if ignore and tx_hash == ignore:
                continue
            if any(contain in tx_data['tx_hex'] for contain in contains):
                return await Transaction.from_hex(tx_data['tx_hex'])
        return None

    async def get_last_block(self) -> dict:
        if not self._blocks:
            return None
        
        # Find block with highest ID
        last_block = max(self._blocks.values(), key=lambda b: b.get('id', 0))
        return normalize_block(last_block)

    async def get_next_block_id(self) -> int:
        if not self._blocks:
            return 1
        
        last_id = max(block_data.get('id', 0) for block_data in self._blocks.values())
        return last_id + 1

    async def get_block(self, block_hash: str) -> dict:
        if block_hash not in self._blocks:
            return None
        
        return normalize_block(self._blocks[block_hash])

    async def get_blocks(self, offset: int, limit: int) -> list:
        # Get blocks in ID range
        selected_blocks = []
        for block_hash, block_data in self._blocks.items():
            block_id = block_data.get('id', 0)
            if block_id >= offset:
                selected_blocks.append((block_hash, block_data))
        
        # Sort by ID and limit
        selected_blocks.sort(key=lambda x: x[1].get('id', 0))
        selected_blocks = selected_blocks[:limit]
        
        # Get transactions for these blocks
        result = []
        total_size = 0
        
        for block_hash, block_data in selected_blocks:
            # Find transactions for this block
            block_transactions = []
            for tx_hash, tx_data in self._transactions.items():
                if tx_data.get('block_hash') == block_hash:
                    block_transactions.append(tx_data['tx_hex'])
            
            # Check if we have old transaction order data
            old_txs = OLD_BLOCKS_TRANSACTIONS_ORDER.get(block_hash)
            if old_txs:
                block_transactions = old_txs
            
            # Check size limit
            block_size = sum(len(tx) for tx in block_transactions)
            if total_size + block_size > MAX_BLOCK_SIZE_HEX * 8:
                break
            
            total_size += block_size
            result.append({
                'block': normalize_block(block_data),
                'transactions': block_transactions
            })
        
        return result

    async def get_block_by_id(self, block_id: int) -> dict:
        for block_data in self._blocks.values():
            if block_data.get('id') == block_id:
                return normalize_block(block_data)
        return None

    async def get_block_transactions(self, block_hash: str, check_signatures: bool = True, hex_only: bool = False) -> List[Union[Transaction, CoinbaseTransaction]]:
        transactions = []
        for tx_hash, tx_data in self._transactions.items():
            if tx_data.get('block_hash') == block_hash:
                if hex_only:
                    transactions.append(tx_data['tx_hex'])
                else:
                    transactions.append(await Transaction.from_hex(tx_data['tx_hex'], check_signatures))
        return transactions

    async def get_block_transaction_hashes(self, block_hash: str) -> List[str]:
        hashes = []
        for tx_hash, tx_data in self._transactions.items():
            if tx_data.get('block_hash') == block_hash and block_hash not in tx_data['tx_hex']:
                hashes.append(tx_hash)
        return hashes

    async def get_block_nice_transactions(self, block_hash: str) -> List[dict]:
        transactions = []
        for tx_hash, tx_data in self._transactions.items():
            if tx_data.get('block_hash') == block_hash:
                transactions.append({
                    'hash': tx_hash,
                    'is_coinbase': not tx_data.get('inputs_addresses', [])
                })
        return transactions

    async def add_unspent_outputs(self, outputs: List[Tuple[str, int]]) -> None:
        if not outputs:
            return
        
        for output in outputs:
            if len(output) == 2:
                self._unspent_outputs.add(output)
            elif len(output) == 3:
                # For outputs with address, we store as (tx_hash, index, address) but keep in set as (tx_hash, index)
                self._unspent_outputs.add((output[0], output[1]))
        
        await self._save_unspent_outputs()

    async def add_pending_spent_outputs(self, outputs: List[Tuple[str, int]]) -> None:
        for output in outputs:
            self._pending_spent_outputs.add(output)
        await self._save_pending_spent_outputs()

    async def add_transactions_pending_spent_outputs(self, transactions: List[Transaction]) -> None:
        outputs = []
        for transaction in transactions:
            outputs.extend([(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs])
        
        for output in outputs:
            self._pending_spent_outputs.add(output)
        
        await self._save_pending_spent_outputs()

    async def add_unspent_transactions_outputs(self, transactions: List[Transaction]) -> None:
        outputs = []
        for transaction in transactions:
            tx_hash = transaction.hash()
            for index, output in enumerate(transaction.outputs):
                outputs.append((tx_hash, index, output.address))
        
        await self.add_unspent_outputs(outputs)

    async def remove_unspent_outputs(self, transactions: List[Transaction]) -> None:
        inputs = []
        for transaction in transactions:
            inputs.extend([(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs])
        
        for input_tuple in inputs:
            self._unspent_outputs.discard(input_tuple)
        
        await self._save_unspent_outputs()

    async def remove_pending_spent_outputs(self, transactions: List[Transaction]) -> None:
        inputs = []
        for transaction in transactions:
            inputs.extend([(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs])
        
        for input_tuple in inputs:
            self._pending_spent_outputs.discard(input_tuple)
        
        await self._save_pending_spent_outputs()

    async def get_unspent_outputs(self, outputs: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        result = []
        for output in outputs:
            if output in self._unspent_outputs:
                result.append(output)
        return result

    async def get_unspent_outputs_hash(self) -> str:
        # Sort outputs by tx_hash, index for consistent hashing
        sorted_outputs = sorted(self._unspent_outputs)
        hash_input = ''.join(tx_hash + bytes([index]).hex() for tx_hash, index in sorted_outputs)
        return sha256(hash_input)

    async def get_pending_spent_outputs(self, outputs: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        result = []
        for output in outputs:
            if output in self._pending_spent_outputs:
                result.append(output)
        return result

    async def set_unspent_outputs_addresses(self):
        # This method was used to populate address field in SQL - not needed for JSON storage
        # as we can store addresses directly when adding outputs
        pass

    async def get_unspent_outputs_from_all_transactions(self):
        # Rebuild unspent outputs from all transactions
        outputs = set()
        
        # Sort transactions by block ID
        sorted_transactions = []
        for tx_hash, tx_data in self._transactions.items():
            block_hash = tx_data.get('block_hash')
            if block_hash and block_hash in self._blocks:
                block_id = self._blocks[block_hash].get('id', 0)
                sorted_transactions.append((block_id, tx_hash, tx_data))
        
        sorted_transactions.sort(key=lambda x: x[0])  # Sort by block ID
        
        last_block_no = 0
        for block_id, tx_hash, tx_data in sorted_transactions:
            if block_id != last_block_no:
                last_block_no = block_id
                print(f'{len(outputs)} utxos at block {last_block_no - 1}')
            
            transaction = await Transaction.from_hex(tx_data['tx_hex'], check_signatures=False)
            
            # Remove spent outputs
            if isinstance(transaction, Transaction):
                spent_outputs = {(tx_input.tx_hash, tx_input.index) for tx_input in transaction.inputs}
                outputs = outputs.difference(spent_outputs)
            
            # Add new outputs
            new_outputs = {(tx_hash, index) for index in range(len(transaction.outputs))}
            outputs.update(new_outputs)
        
        return list(outputs)

    async def get_address_transactions(self, address: str, check_pending_txs: bool = False, check_signatures: bool = False, limit: int = 50, offset: int = 0) -> List[Union[Transaction, CoinbaseTransaction]]:
        point = string_to_point(address)
        search_patterns = [point_to_bytes(string_to_point(address), address_format).hex() for address_format in list(AddressFormat)]
        addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
        
        # Find transactions involving this address
        matching_txs = []
        
        # Search confirmed transactions
        for tx_hash, tx_data in self._transactions.items():
            block_hash = tx_data.get('block_hash')
            if block_hash in self._blocks:
                block_id = self._blocks[block_hash].get('id', 0)
                
                # Check if address is in inputs or outputs
                inputs_addresses = tx_data.get('inputs_addresses', [])
                outputs_addresses = tx_data.get('outputs_addresses', [])
                
                if (any(addr in addresses for addr in inputs_addresses) or 
                    any(addr in addresses for addr in outputs_addresses) or
                    any(pattern in tx_data['tx_hex'] for pattern in search_patterns)):
                    matching_txs.append((block_id, tx_data['tx_hex']))
        
        # Sort by block number descending
        matching_txs.sort(key=lambda x: x[0], reverse=True)
        
        # Apply pagination
        paginated_txs = matching_txs[offset:offset + limit]
        
        # Add pending transactions if requested
        if check_pending_txs:
            for tx_hash, tx_data in self._pending_transactions.items():
                inputs_addresses = tx_data.get('inputs_addresses', [])
                if (any(addr in addresses for addr in inputs_addresses) or
                    any(pattern in tx_data['tx_hex'] for pattern in search_patterns)):
                    paginated_txs.append((float('inf'), tx_data['tx_hex']))  # Pending txs have highest priority
        
        # Convert to Transaction objects
        result = []
        for _, tx_hex in paginated_txs:
            result.append(await Transaction.from_hex(tx_hex, check_signatures))
        
        return result

    async def get_address_pending_transactions(self, address: str, check_signatures: bool = False) -> List[Union[Transaction, CoinbaseTransaction]]:
        point = string_to_point(address)
        search_patterns = [point_to_bytes(string_to_point(address), address_format).hex() for address_format in list(AddressFormat)]
        addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
        
        result = []
        for tx_hash, tx_data in self._pending_transactions.items():
            inputs_addresses = tx_data.get('inputs_addresses', [])
            if (any(addr in addresses for addr in inputs_addresses) or
                any(pattern in tx_data['tx_hex'] for pattern in search_patterns)):
                result.append(await Transaction.from_hex(tx_data['tx_hex'], check_signatures))
        
        return result

    async def get_address_pending_spent_outputs(self, address: str, check_signatures: bool = False) -> List[Union[Transaction, CoinbaseTransaction]]:
        point = string_to_point(address)
        addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
        
        result = []
        for tx_hash, tx_data in self._pending_transactions.items():
            inputs_addresses = tx_data.get('inputs_addresses', [])
            if any(addr in addresses for addr in inputs_addresses):
                tx = await Transaction.from_hex(tx_data['tx_hex'], check_signatures)
                result.extend([{'tx_hash': tx_input.tx_hash, 'index': tx_input.index} for tx_input in tx.inputs])
        
        return result

    async def get_spendable_outputs(self, address: str, check_pending_txs: bool = False) -> List[TransactionInput]:
        point = string_to_point(address)
        addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
        
        result = []
        
        # Find unspent outputs for this address
        for tx_hash, index in self._unspent_outputs:
            if tx_hash in self._transactions:
                tx_data = self._transactions[tx_hash]
                outputs_addresses = tx_data.get('outputs_addresses', [])
                outputs_amounts = tx_data.get('outputs_amounts', [])
                
                if index < len(outputs_addresses) and outputs_addresses[index] in addresses:
                    # Check if not pending spent
                    if not check_pending_txs or (tx_hash, index) not in self._pending_spent_outputs:
                        amount = Decimal(outputs_amounts[index]) / SMALLEST
                        result.append(TransactionInput(tx_hash, index, amount=amount, public_key=point))
        
        return result

    async def get_address_balance(self, address: str, check_pending_txs: bool = False) -> Decimal:
        tx_inputs = await self.get_spendable_outputs(address, check_pending_txs=check_pending_txs)
        balance = sum([tx_input.amount for tx_input in tx_inputs], Decimal(0))
        
        if check_pending_txs:
            point = string_to_point(address)
            search_patterns = [point_to_bytes(string_to_point(address), address_format).hex() for address_format in list(AddressFormat)]
            addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
            
            for tx_hash, tx_data in self._pending_transactions.items():
                if any(pattern in tx_data['tx_hex'] for pattern in search_patterns):
                    tx = await Transaction.from_hex(tx_data['tx_hex'], check_signatures=False)
                    for i, tx_output in enumerate(tx.outputs):
                        if tx_output.address in addresses:
                            balance += tx_output.amount
        
        return balance

    async def get_address_spendable_outputs_delta(self, address: str, block_no: int) -> Tuple[List[TransactionInput], List[TransactionInput]]:
        point = string_to_point(address)
        addresses = [point_to_string(point, address_format) for address_format in list(AddressFormat)]
        
        unspent_outputs = []
        spending_txs = []
        
        # Find unspent outputs from blocks >= block_no
        for tx_hash, index in self._unspent_outputs:
            if tx_hash in self._transactions:
                tx_data = self._transactions[tx_hash]
                block_hash = tx_data.get('block_hash')
                if block_hash in self._blocks:
                    block_id = self._blocks[block_hash].get('id', 0)
                    if block_id >= block_no:
                        outputs_addresses = tx_data.get('outputs_addresses', [])
                        outputs_amounts = tx_data.get('outputs_amounts', [])
                        if index < len(outputs_addresses) and outputs_addresses[index] in addresses:
                            amount = Decimal(outputs_amounts[index]) / SMALLEST
                            unspent_outputs.append(TransactionInput(tx_hash, index, amount=amount, public_key=point))
        
        # Find spending transactions from blocks >= block_no
        for tx_hash, tx_data in self._transactions.items():
            block_hash = tx_data.get('block_hash')
            if block_hash in self._blocks:
                block_id = self._blocks[block_hash].get('id', 0)
                if block_id >= block_no:
                    inputs_addresses = tx_data.get('inputs_addresses', [])
                    if any(addr in addresses for addr in inputs_addresses):
                        tx = await Transaction.from_hex(tx_data['tx_hex'], False)
                        spending_txs.extend(tx.inputs)
        
        return unspent_outputs, spending_txs

    async def get_nice_transaction(self, tx_hash: str, address: str = None):
        print("Running get_nice_transaction")
        
        # Check if it's a confirmed transaction
        get_pending = False
        tx_data = None
        block_timestamp = None
        
        if tx_hash in self._transactions:
            tx_data = self._transactions[tx_hash]
            block_hash = tx_data.get('block_hash')
            if block_hash and block_hash in self._blocks:
                block_timestamp = self._blocks[block_hash].get('timestamp')
        elif tx_hash in self._pending_transactions:
            get_pending = True
            tx_data = self._pending_transactions[tx_hash]
        
        if tx_data is None:
            return None
        
        # Parse timestamps
        time_received = None
        if tx_data.get('time_received'):
            try:
                time_received_dt = datetime.fromisoformat(tx_data['time_received'].replace('Z', '+00:00'))
                time_received = int(round(time_received_dt.timestamp()))
            except:
                time_received = None
        
        time_confirmed = None
        if block_timestamp:
            try:
                if isinstance(block_timestamp, str):
                    time_confirmed_dt = datetime.fromisoformat(block_timestamp.replace('Z', '+00:00'))
                else:
                    time_confirmed_dt = block_timestamp
                time_confirmed = int(round(time_confirmed_dt.timestamp()))
            except:
                time_confirmed = None
        
        tx = await Transaction.from_hex(tx_data['tx_hex'], False)
        
        if isinstance(tx, CoinbaseTransaction):
            transaction = {
                'is_coinbase': True,
                'hash': tx_hash,
                'block_hash': tx_data.get('block_hash'),
                'time_mined': time_received,
            }
        else:
            delta = None
            if address is not None:
                public_key = string_to_point(address)
                delta = 0
                inputs_addresses = tx_data.get('inputs_addresses', [])
                for i, tx_input in enumerate(tx.inputs):
                    if i < len(inputs_addresses) and string_to_point(inputs_addresses[i]) == public_key:
                        print('getting related output for delta')
                        delta -= await tx_input.get_amount()
                for tx_output in tx.outputs:
                    if tx_output.public_key == public_key:
                        delta += tx_output.amount
            
            transaction = {
                'is_coinbase': False,
                'hash': tx_hash,
                'block_hash': tx_data.get('block_hash'),
                'message': tx.message.hex() if tx.message is not None else None,
                'time_received': time_received,
                'time_confirmed': time_confirmed,
                'inputs': [],
                'delta': delta,
                'fees': await tx.get_fees()
            }
            
            if get_pending:
                del transaction['time_confirmed']
            
            inputs_addresses = tx_data.get('inputs_addresses', [])
            for i, input_tx in enumerate(tx.inputs):
                input_address = inputs_addresses[i] if i < len(inputs_addresses) else None
                transaction['inputs'].append({
                    'index': input_tx.index,
                    'tx_hash': input_tx.tx_hash,
                    'address': input_address,
                    'amount': await input_tx.get_amount()
                })
        
        transaction['outputs'] = [{'address': output.address, 'amount': output.amount} for output in tx.outputs]
        return transaction

    # Smart Contract Database Methods
    
    async def _save_contracts(self):
        """Save contract data to file"""
        # Note: Lock should already be held by caller
        await self._save_to_file_unlocked(self.contracts_file, self._contracts)
    
    async def _save_contract_storage(self):
        """Save contract storage to file"""
        await self._save_to_file_unlocked(self.contract_storage_file, self._contract_storage)
    
    async def save_contract_state(self, contract_address: str, state_data: dict):
        """Save contract state to database"""
        async with self._lock:
            self._contracts[contract_address] = state_data
            await self._save_contracts()
    
    async def get_contract_state(self, contract_address: str) -> dict:
        """Get contract state from database"""
        return self._contracts.get(contract_address)
    
    async def set_contract_storage(self, contract_address: str, key: str, value):
        """Set contract storage value"""
        async with self._lock:
            if contract_address not in self._contract_storage:
                self._contract_storage[contract_address] = {}
            self._contract_storage[contract_address][key] = value
            await self._save_contract_storage()
    
    async def get_contract_storage(self, contract_address: str, key: str):
        """Get contract storage value"""
        storage = self._contract_storage.get(contract_address, {})
        return storage.get(key)
    
    async def get_contract_code(self, contract_address: str) -> str:
        """Get contract code"""
        contract_data = self._contracts.get(contract_address)
        return contract_data.get('code', '') if contract_data else ''
    
    async def get_contract_info(self, contract_address: str) -> dict:
        """Get complete contract information"""
        contract_data = self._contracts.get(contract_address)
        if not contract_data:
            return None
        
        storage_keys = list(self._contract_storage.get(contract_address, {}).keys())
        
        return {
            'address': contract_address,
            'deployed_by': contract_data.get('deployed_by', ''),
            'deployment_block': contract_data.get('deployment_block', 0),
            'balance': contract_data.get('balance', '0'),
            'code': contract_data.get('code', ''),
            'storage_keys': storage_keys
        }
    
    async def get_contracts_by_deployer(self, deployer_address: str) -> List[dict]:
        """Get all contracts deployed by a specific address"""
        contracts = []
        for address, data in self._contracts.items():
            if data.get('deployed_by') == deployer_address:
                contracts.append({
                    'address': address,
                    'deployment_block': data.get('deployment_block', 0),
                    'balance': data.get('balance', '0')
                })
        return contracts
    
    async def get_all_contracts(self) -> List[str]:
        """Get list of all contract addresses"""
        return list(self._contracts.keys())
    
    async def contract_exists(self, contract_address: str) -> bool:
        """Check if a contract exists"""
        return contract_address in self._contracts
    
    async def get_transaction_count(self, address: str) -> int:
        """Get transaction count for an address (nonce)"""
        count = 0
        for tx_data in self._transactions.values():
            inputs_addresses = tx_data.get('inputs_addresses', [])
            if address in inputs_addresses:
                count += 1
        return count
    
    # Treasury management methods
    async def accumulate_treasury_fees(self, amount: Decimal):
        """Add fees to the treasury accumulation with proper precision handling"""
        if amount < 0:
            raise ValueError("Cannot accumulate negative treasury fees")
        
        # Ensure proper Decimal precision throughout
        current_fees = Decimal(str(self._treasury_data.get('accumulated_fees', 0)))
        self._treasury_data['accumulated_fees'] = str(current_fees + amount)
        await self._save_treasury_data()
    
    async def get_accumulated_treasury_fees(self) -> Decimal:
        """Get current accumulated treasury fees"""
        return Decimal(str(self._treasury_data.get('accumulated_fees', 0)))
    
    async def distribute_treasury_funds(self, block_number: int, amount: Decimal):
        """Record a treasury distribution with validation"""
        if amount < 0:
            raise ValueError("Cannot distribute negative treasury amount")
        
        # Validate we have enough accumulated fees
        current_fees = Decimal(str(self._treasury_data.get('accumulated_fees', 0)))
        if amount > current_fees:
            raise ValueError(f"Cannot distribute {amount}, only {current_fees} accumulated")
        
        # Record distribution
        self._treasury_data['distributions'][str(block_number)] = str(amount)
        
        # Update totals
        total_distributed = Decimal(str(self._treasury_data.get('total_distributed', 0)))
        self._treasury_data['total_distributed'] = str(total_distributed + amount)
        
        # Deduct from accumulated fees
        self._treasury_data['accumulated_fees'] = str(current_fees - amount)
        self._treasury_data['last_distribution_block'] = block_number
        
        await self._save_treasury_data()
    
    async def get_treasury_distribution_history(self) -> dict:
        """Get all treasury distributions"""
        return self._treasury_data['distributions']
    
    async def get_last_treasury_distribution_block(self) -> int:
        """Get the block number of the last treasury distribution"""
        return self._treasury_data['last_distribution_block']
    
    async def is_treasury_distribution_block(self, block_number: int) -> bool:
        """
        Check if a block number should trigger a treasury distribution.
        Treasury distributions happen at regular intervals (e.g., every 25,000 blocks).
        
        Args:
            block_number: The block number to check
            
        Returns:
            True if this block should have a treasury distribution
        """
        from stellaris.constants import BLOCK_CONFIG
        
        if block_number <= 0:
            return False
        
        treasury_config = BLOCK_CONFIG.get('treasury', {})
        tax_interval = treasury_config.get('tax_interval', 25000)
        
        # Ensure tax_interval is valid
        if tax_interval <= 0:
            return False
        
        return block_number % tax_interval == 0