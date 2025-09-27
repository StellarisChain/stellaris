import hashlib
from decimal import Decimal
from io import BytesIO
from math import ceil, floor, log
from typing import Tuple, List, Union
from stellaris.constants import MAX_SUPPLY, ENDIAN, MAX_BLOCK_SIZE_HEX, BLOCK_CONFIG
from stellaris.database import Database

BLOCK_TIME = 15  # Target time per block in seconds
BLOCKS_COUNT = 512  # Number of blocks to consider for difficulty adjustment
START_DIFFICULTY = Decimal('6.0')


def get_max_difficulty_for_block(block_number: int) -> Decimal:
    """Get maximum difficulty for a given block number based on XML configuration."""
    # If no ranges are configured, return no limit (very high value)
    if not BLOCK_CONFIG.get('ranges'):
        return Decimal('999.0')  # Effectively no limit
    
    # Find the range that contains this block number
    for range_config in BLOCK_CONFIG['ranges']:
        if range_config['min_index'] <= block_number <= range_config['max_index']:
            return Decimal(str(range_config['max_difficulty']))
    
    # If block number is beyond all configured ranges, return no limit
    return Decimal('999.0')


def difficulty_to_hashrate(difficulty: Decimal) -> Decimal:
    """
    Convert a difficulty value to a hashrate.
    Uses integer hex digit and fractional remainder for calculation.
    Returns a Decimal representing hashrate.
    """
    int_part = floor(difficulty)
    frac_part = difficulty % 1
    
    return Decimal(16 ** int_part * (16 / ceil(16 * (1 - frac_part))))


def hashrate_to_difficulty(hashrate: Union[int, Decimal]) -> Decimal:
    """
    Convert a hashrate to a difficulty value.
    Guards against negative/zero hashrates, computes integer hex digit,
    and derives intra-bucket ratio.
    Returns a Decimal representing difficulty.
    """
    # Guard against invalid hashrates
    if hashrate <= 0:
        return START_DIFFICULTY
    
    # Compute integer part (hex digit)
    int_part = floor(log(hashrate, 16))
    
    # Compute ratio within the current bucket
    ratio = hashrate / 16 ** int_part
    
    # Scan decimal tenths and return on first threshold match
    for i in range(0, 10):
        threshold = 16 / ceil(16 * (1 - i / 10))
        if ratio <= threshold:
            return Decimal(int_part + i / 10)
    
    # Default to 0.9 if no match found
    return Decimal(int_part + 0.9)


async def calculate_difficulty() -> Tuple[Decimal, dict]:
    database = Database.instance
    last_block = await database.get_last_block()
    if last_block is None:
        return START_DIFFICULTY, dict()
    last_block = dict(last_block)
    last_block['address'] = last_block['address'].strip(' ')
    if last_block['id'] < BLOCKS_COUNT:
        return START_DIFFICULTY, last_block

    # Retarget every 512 blocks
    if last_block['id'] % 512 == 0:
        # Get block from start of period
        last_adjust_block = await database.get_block_by_id(last_block['id'] - 512 + 1)
        elapsed = last_block['timestamp'] - last_adjust_block['timestamp']
        average_per_block = elapsed / 512
        last_difficulty = last_block['difficulty']
        
        # Convert difficulty to hashrate
        hashrate = difficulty_to_hashrate(last_difficulty)
        
        # Calculate adjustment ratio
        ratio = BLOCK_TIME / average_per_block
        
        # Clamp adjustment to [0.25, 4.0] range
        ratio = max(0.25, min(ratio, 4.0))
        
        # Apply ratio to hashrate
        hashrate *= Decimal(str(ratio))
        
        # Convert back to difficulty
        new_difficulty = hashrate_to_difficulty(hashrate)
        
        # Print adjustment summary
        print(f"Difficulty adjustment: {last_difficulty} → {new_difficulty} (ratio: {ratio:.2f})")
        
        # Apply maximum difficulty constraint for the next block
        next_block_number = last_block['id'] + 1
        max_difficulty = get_max_difficulty_for_block(next_block_number)
        if new_difficulty > max_difficulty:
            new_difficulty = max_difficulty
            print(f"Capped difficulty to {max_difficulty} due to block constraints")
        
        return new_difficulty, last_block

    # Return current on-chain difficulty within a period
    return last_block['difficulty'], last_block