import hashlib
from decimal import Decimal
from io import BytesIO
from math import ceil, floor, log
from typing import Tuple, List, Union
from lib.VoxaCommunications_Router.stellaris.constants import MAX_SUPPLY, ENDIAN, MAX_BLOCK_SIZE_HEX
from lib.VoxaCommunications_Router.stellaris.database import Database

BLOCK_TIME = 180
BLOCKS_COUNT = Decimal(500)
START_DIFFICULTY = Decimal('6.0')

def difficulty_to_hashrate_old(difficulty: Decimal) -> int:
    decimal = difficulty % 1 or 1/16
    return Decimal(16 ** int(difficulty) * (16 * decimal))


def difficulty_to_hashrate(difficulty: Decimal) -> int:
    decimal = difficulty % 1
    return Decimal(16 ** int(difficulty) * (16 / ceil(16 * (1 - decimal))))


def hashrate_to_difficulty_old(hashrate: int) -> Decimal:
    difficulty = int(log(hashrate, 16))
    if hashrate == 16 ** difficulty:
        return Decimal(difficulty)
    return Decimal(difficulty + (hashrate / Decimal(16) ** difficulty) / 16)


def hashrate_to_difficulty_wrong(hashrate: int) -> Decimal:
    difficulty = int(log(hashrate, 16))
    if hashrate == 16 ** difficulty:
        return Decimal(difficulty)
    ratio = hashrate / 16 ** difficulty

    decimal = 16 / ratio / 16
    decimal = 1 - floor(decimal * 10) / Decimal(10)
    return Decimal(difficulty + decimal)


def hashrate_to_difficulty(hashrate: int) -> Decimal:
    difficulty = int(log(hashrate, 16))
    ratio = hashrate / 16 ** difficulty

    for i in range(0, 10):
        coeff = 16 / ceil(16 * (1 - i / 10))
        if coeff > ratio:
            decimal = (i - 1) / Decimal(10)
            return Decimal(difficulty + decimal)
        if coeff == ratio:
            decimal = i / Decimal(10)
            return Decimal(difficulty + decimal)

    return Decimal(difficulty) + Decimal('0.9')


async def calculate_difficulty() -> Tuple[Decimal, dict]:
    database = Database.instance
    last_block = await database.get_last_block()
    if last_block is None:
        return START_DIFFICULTY, dict()
    last_block = dict(last_block)
    last_block['address'] = last_block['address'].strip(' ')
    if last_block['id'] < BLOCKS_COUNT:
        return START_DIFFICULTY, last_block

    if last_block['id'] % BLOCKS_COUNT == 0:
        last_adjust_block = await database.get_block_by_id(last_block['id'] - BLOCKS_COUNT + 1)
        elapsed = last_block['timestamp'] - last_adjust_block['timestamp']
        average_per_block = elapsed / BLOCKS_COUNT
        last_difficulty = last_block['difficulty']
        if last_block['id'] <= 17500:
            hashrate = difficulty_to_hashrate_old(last_difficulty)
        else:
            hashrate = difficulty_to_hashrate(last_difficulty)
        ratio = BLOCK_TIME / average_per_block
        if last_block['id'] >= 180_000:  # from block 180k, allow difficulty to double at most
            ratio = min(ratio, 2)
        hashrate *= ratio
        if last_block['id'] < 17500:
            new_difficulty = hashrate_to_difficulty_old(hashrate)
            new_difficulty = floor(new_difficulty * 10) / Decimal(10)
        elif last_block['id'] < 180_000:
            new_difficulty = hashrate_to_difficulty_wrong(hashrate)
        else:
            new_difficulty = hashrate_to_difficulty(hashrate)
        return new_difficulty, last_block

    return last_block['difficulty'], last_block