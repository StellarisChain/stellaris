#!/usr/bin/env python3
# Stellaris CUDA Miner
# Based on Denaro's CUDA miner, adapted for Stellaris

import argparse
import os
import time
import sys
import math
from decimal import Decimal
import hashlib
import json
import requests
from typing import List, Tuple, Optional
import base58

# CUDA imports - will fail gracefully if not available
try:
    import pycuda.driver as cuda
    import pycuda.autoinit
    from pycuda.compiler import SourceModule
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    print("PyCUDA not available. Install with: pip install pycuda")

# Status codes
STATUS_PENDING = 0
STATUS_SUCCESS = 1
STATUS_STALE = 2
STATUS_FAILED = 3

# CUDA kernel code
CUDA_KERNEL = """
#include <stdint.h>

// SHA256 round constants
__constant__ uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f3, 0xc67178f2
};

// SHA256 device functions
__device__ void sha256_transform(uint32_t* state, const uint32_t* block) {
    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];

    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = (block[j] << 24) | (block[j + 1] << 16) | (block[j + 2] << 8) | (block[j + 3]);
    
    for (; i < 64; ++i)
        m[i] = (((m[i - 2] >> 17) | (m[i - 2] << 15)) ^ ((m[i - 2] >> 19) | (m[i - 2] << 13)) ^ (m[i - 2] >> 10)) + m[i - 7] + 
               (((m[i - 15] >> 7) | (m[i - 15] << 25)) ^ ((m[i - 15] >> 18) | (m[i - 15] << 14)) ^ (m[i - 15] >> 3)) + m[i - 16];

    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    f = state[5];
    g = state[6];
    h = state[7];

    for (i = 0; i < 64; ++i) {
        t1 = h + (((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + K[i] + m[i];
        t2 = (((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c));
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

__device__ void sha256_init(uint32_t* state) {
    state[0] = 0x6a09e667;
    state[1] = 0xbb67ae85;
    state[2] = 0x3c6ef372;
    state[3] = 0xa54ff53a;
    state[4] = 0x510e527f;
    state[5] = 0x9b05688c;
    state[6] = 0x1f83d9ab;
    state[7] = 0x5be0cd19;
}

__device__ void sha256_update(uint32_t* state, const uint8_t* data, size_t len) {
    uint32_t block[16];
    uint32_t i, j = 0;
    
    for (i = 0; i < len / 64; i++) {
        for (j = 0; j < 16; j++) {
            block[j] = 0;
            for (uint32_t k = 0; k < 4; k++) {
                block[j] = (block[j] << 8) | data[i * 64 + j * 4 + k];
            }
        }
        sha256_transform(state, block);
    }
}

__device__ void sha256_final(uint32_t* state, const uint8_t* data, size_t len, uint32_t total_len) {
    uint32_t block[16];
    uint32_t i, j;
    
    for (i = 0; i < 16; i++)
        block[i] = 0;
        
    // Copy remainder
    size_t remain = len % 64;
    for (i = 0; i < remain; i++)
        ((uint8_t*)block)[i] = data[len - remain + i];
        
    // Add padding
    ((uint8_t*)block)[remain] = 0x80;
    
    if (remain >= 56) {
        sha256_transform(state, block);
        for (i = 0; i < 14; i++)
            block[i] = 0;
    }
    
    // Add length (in bits)
    block[14] = (total_len >> 29) & 0xFFFFFFFF;
    block[15] = (total_len << 3) & 0xFFFFFFFF;
    sha256_transform(state, block);
}

// Convert SHA256 state to hex string (uppercase)
__device__ void sha256_to_hex_uc(uint32_t* state, char* hex) {
    const char HEX_CHARS[] = "0123456789ABCDEF";
    for (int i = 0; i < 8; i++) {
        uint32_t val = state[i];
        for (int j = 7; j >= 0; j--) {
            uint8_t nib = (val >> (j * 4)) & 0xF;
            *hex++ = HEX_CHARS[nib];
        }
    }
    *hex = '\\0';
}

// Check if a byte prefix matches the required suffix
__device__ bool nibble_prefix_match(uint32_t* state, const char* required_suffix, int idiff) {
    char hex[65];
    sha256_to_hex_uc(state, hex);
    
    // Compare last idiff chars of hex to required_suffix
    for (int i = 0; i < idiff; i++) {
        if (hex[63 - i] != required_suffix[idiff - 1 - i])
            return false;
    }
    return true;
}

// Check if a character is in the allowed charset
__device__ bool bytes_contains_uc(char c, const char* charset, int charset_len) {
    for (int i = 0; i < charset_len; i++) {
        if (c == charset[i])
            return true;
    }
    return false;
}

// Main mining kernel
__global__ void miner_kernel(
    const uint8_t* prefix,        // Block prefix bytes (excluding nonce)
    size_t prefix_len,            // Length of prefix
    uint32_t start_nonce,         // Starting nonce for this batch
    uint32_t iters_per_thread,    // Number of iterations per thread
    const char* required_suffix,  // Required hex suffix to match
    int idiff,                    // Integer difficulty (number of hex chars to match)
    const char* charset,          // Allowed charset for next hex digit for fractional difficulty
    int charset_len,              // Length of charset
    volatile uint32_t* found_nonce // Output: found nonce (0 if not found)
) {
    // Compute starting nonce for this thread
    uint32_t nonce = start_nonce + (blockIdx.x * blockDim.x + threadIdx.x);
    const uint32_t grid_size = gridDim.x * blockDim.x;
    
    uint8_t buffer[128];  // Temp buffer for SHA256 input
    
    // Copy prefix into buffer
    for (int i = 0; i < prefix_len; i++) {
        buffer[i] = prefix[i];
    }
    
    // Loop for iters_per_thread iterations
    for (uint32_t i = 0; i < iters_per_thread; i++) {
        uint32_t current_nonce = nonce + i * grid_size;
        
        // Write nonce to buffer in little-endian
        buffer[prefix_len] = current_nonce & 0xFF;
        buffer[prefix_len + 1] = (current_nonce >> 8) & 0xFF;
        buffer[prefix_len + 2] = (current_nonce >> 16) & 0xFF;
        buffer[prefix_len + 3] = (current_nonce >> 24) & 0xFF;
        
        // Compute SHA256 hash
        uint32_t state[8];
        sha256_init(state);
        sha256_final(state, buffer, prefix_len + 4, prefix_len + 4);
        
        // Check if matches difficulty requirement
        bool matched = false;
        
        if (idiff > 0) {
            matched = nibble_prefix_match(state, required_suffix, idiff);
            
            // If integer difficulty matched and charset_len > 0, check next digit
            if (matched && charset_len > 0) {
                // Get next hex digit from hash
                char hex[65];
                sha256_to_hex_uc(state, hex);
                char next_digit = hex[63 - idiff];
                matched = bytes_contains_uc(next_digit, charset, charset_len);
            }
        } else if (charset_len > 0) {
            // Only fractional difficulty
            char hex[65];
            sha256_to_hex_uc(state, hex);
            matched = bytes_contains_uc(hex[63], charset, charset_len);
        }
        
        if (matched) {
            // Found a match, set result and exit
            *found_nonce = current_nonce;
            return;
        }
    }
}
"""

def build_prefix(previous_block_hash: str, address: str, merkle_root: str, timestamp_val: int, difficulty: float) -> bytes:
    """
    Construct the block prefix that excludes the nonce.
    Returns bytes ready for SHA256 hashing.
    """
    # Convert address to bytes
    addr_bytes = string_to_bytes(address)
    
    # Prepare version byte if needed
    version = bytes([])
    if len(addr_bytes) != 64:
        version = bytes([2])
    
    # Construct prefix
    prefix = (
        version +
        bytes.fromhex(previous_block_hash) + 
        addr_bytes + 
        bytes.fromhex(merkle_root) + 
        timestamp_val.to_bytes(4, byteorder='little') +
        int(float(difficulty) * 10).to_bytes(2, byteorder='little')
    )
    
    return prefix

def compute_fractional_charset(difficulty: float) -> Tuple[int, str]:
    """
    Split difficulty into integer and fractional parts.
    Return integer difficulty and allowed charset for fractional part.
    """
    idiff = int(difficulty)
    frac = difficulty % 1
    
    # No fractional part
    if frac == 0:
        return idiff, ""
    
    # Compute allowed charset for fractional difficulty
    allowed_count = math.ceil(16 * (1 - frac))
    charset = "0123456789ABCDEF"[:allowed_count]
    
    return idiff, charset

def make_last_block_chunk(previous_hash: str, idiff: int) -> str:
    """
    Get the required suffix from previous block hash for matching.
    """
    return previous_hash[-idiff:].upper() if idiff > 0 else ""

def string_to_bytes(s: str) -> bytes:
    """
    Convert a string to bytes, with Base58 fallback if hex fails.
    """
    try:
        return bytes.fromhex(s)
    except ValueError:
        try:
            return base58.b58decode(s)
        except:
            raise ValueError(f"Cannot decode address: {s}")

def timestamp() -> int:
    """
    Get current UTC timestamp in seconds.
    """
    return int(time.time())

def submit_block(node_url: str, block_content: str, txs: List[str], last_block_id: int) -> int:
    """
    Submit a mined block to the node.
    Returns a status code.
    """
    try:
        response = requests.post(
            f"{node_url}/push_block",
            json={
                "block_content": block_content,
                "txs": txs,
                "id": last_block_id + 1
            },
            timeout=30
        )
        
        result = response.json()
        
        if not isinstance(result, dict):
            return STATUS_FAILED
            
        if result.get("ok", False) and "error" not in result:
            return STATUS_SUCCESS
            
        error = result.get("error", "")
        if "duplicate" in error.lower() or "already" in error.lower():
            return STATUS_STALE
            
        print(f"Block submission error: {error}")
        return STATUS_FAILED
        
    except Exception as e:
        print(f"Block submission exception: {e}")
        return STATUS_FAILED

def prepend_env_path_if_not_set(env_var: str, path: str):
    """
    Prepend a path to an environment variable if not already present.
    """
    current = os.environ.get(env_var, "")
    paths = current.split(os.pathsep)
    
    if path not in paths:
        os.environ[env_var] = path + (os.pathsep + current if current else "")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Stellaris CUDA Miner")
    parser.add_argument("-a", "--address", required=True, help="Mining address to receive rewards")
    parser.add_argument("-n", "--node", default="http://127.0.0.1:3006/", help="Stellaris node URL")
    parser.add_argument("-m", "--max-blocks", type=int, default=10, help="Maximum blocks to mine before exiting")
    parser.add_argument("--gpu-blocks", type=int, default=256, help="CUDA grid blocks")
    parser.add_argument("--gpu-threads", type=int, default=256, help="CUDA threads per block")
    parser.add_argument("--gpu-iterations", type=int, default=10000, help="Iterations per thread per batch")
    parser.add_argument("--gpu-arch", required=True, help="CUDA architecture flag for nvcc")
    
    args = parser.parse_args()
    
    if not CUDA_AVAILABLE:
        print("ERROR: PyCUDA is not installed or CUDA is not available.")
        sys.exit(1)
    
    # Prepare environment for CUDA toolchain
    cuda_bin = "/usr/local/cuda/bin"
    cuda_lib = "/usr/local/cuda/lib64"
    
    prepend_env_path_if_not_set("PATH", cuda_bin)
    prepend_env_path_if_not_set("LD_LIBRARY_PATH", cuda_lib)
    
    # Ensure node URL ends with a slash
    node_url = args.node
    if not node_url.endswith('/'):
        node_url += '/'
    
    # Normalize address
    address = args.address
    
    # Compile CUDA module
    try:
        mod = SourceModule(CUDA_KERNEL, options=[f"-arch={args.gpu_arch}"])
        miner_kernel = mod.get_function("miner_kernel")
        
        # Get SHA256 round constants and copy to device
        sha256_k = mod.get_global("K")[0]
        
        # These are the SHA-256 round constants
        k = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f3, 0xc67178f2
        ]
        cuda.memcpy_htod(sha256_k, bytes(v.to_bytes(4, 'little') for v in k))
        
    except Exception as e:
        print(f"ERROR: Failed to compile CUDA kernel: {e}")
        sys.exit(1)
    
    print(f"Stellaris CUDA Miner")
    print(f"  Node: {node_url}")
    print(f"  Address: {address}")
    print(f"  GPU configuration: {args.gpu_blocks} blocks x {args.gpu_threads} threads")
    print(f"  Iterations per thread: {args.gpu_iterations}")
    
    # Prepare mining loop
    blocks_mined = 0
    found_nonce_buffer = cuda.pagelocked_empty(1, dtype=numpy.uint32)
    found_nonce_gpu = cuda.mem_alloc(found_nonce_buffer.nbytes)
    
    while blocks_mined < args.max_blocks:
        # Get mining info with retry logic
        mining_info = None
        retries = 0
        while retries < 5:
            try:
                response = requests.get(f"{node_url}get_mining_info", timeout=10)
                mining_info = response.json()
                if "result" in mining_info:
                    mining_info = mining_info["result"]
                    break
            except Exception as e:
                print(f"Error getting mining info: {e}")
            
            print(f"Retrying to get mining info in 5 seconds...")
            time.sleep(5)
            retries += 1
        
        if mining_info is None:
            print("Failed to get mining info after retries, exiting.")
            break
        
        # Extract mining parameters
        pending_txs = mining_info.get("pending_transactions", [])
        hashes = mining_info.get("hashes", [])
        merkle_root = mining_info.get("merkle_root", "")
        
        # Get last block
        try:
            response = requests.get(f"{node_url}get_blocks?limit=1", timeout=10)
            blocks = response.json()["result"]
            if not blocks:
                print("No blocks found, using defaults.")
                last_block = {"hash": "0" * 64, "id": 0, "timestamp": int(time.time()) - 15, "difficulty": 6.0}
            else:
                last_block = blocks[0]
        except Exception as e:
            print(f"Error getting last block: {e}")
            time.sleep(5)
            continue
        
        # Extract block parameters
        last_block_hash = last_block["hash"]
        last_block_id = last_block["id"]
        last_block_time = last_block["timestamp"]
        difficulty = float(last_block["difficulty"])
        
        # Build inputs
        current_time = timestamp()
        prefix = build_prefix(last_block_hash, address, merkle_root, current_time, difficulty)
        idiff, charset = compute_fractional_charset(difficulty)
        required_suffix = make_last_block_chunk(last_block_hash, idiff)
        
        print(f"\nMining block {last_block_id + 1} with difficulty {difficulty}")
        print(f"  Integer difficulty: {idiff}, Charset: '{charset}'")
        print(f"  Timestamp: {current_time}")
        print(f"  Merkle root: {merkle_root}")
        print(f"  {len(pending_txs)} pending transactions")
        
        # Start mining
        start_time = time.time()
        refresh_time = start_time + 90  # Refresh work every 90 seconds
        
        # Allocate memory on GPU
        prefix_gpu = cuda.mem_alloc(len(prefix))
        cuda.memcpy_htod(prefix_gpu, prefix)
        
        charset_gpu = None
        if charset:
            charset_gpu = cuda.mem_alloc(len(charset))
            cuda.memcpy_htod(charset_gpu, charset.encode('utf-8'))
        else:
            charset_gpu = cuda.mem_alloc(1)  # Dummy allocation
            cuda.memcpy_htod(charset_gpu, b'\0')
        
        required_suffix_gpu = None
        if required_suffix:
            required_suffix_gpu = cuda.mem_alloc(len(required_suffix) + 1)
            cuda.memcpy_htod(required_suffix_gpu, required_suffix.encode('utf-8') + b'\0')
        else:
            required_suffix_gpu = cuda.mem_alloc(1)  # Dummy allocation
            cuda.memcpy_htod(required_suffix_gpu, b'\0')
        
        nonce = 0
        found = False
        
        while time.time() < refresh_time and not found:
            # Reset found nonce
            found_nonce_buffer[0] = 0
            cuda.memcpy_htod(found_nonce_gpu, found_nonce_buffer)
            
            # Launch kernel
            miner_kernel(
                prefix_gpu,
                numpy.int32(len(prefix)),
                numpy.uint32(nonce),
                numpy.uint32(args.gpu_iterations),
                required_suffix_gpu,
                numpy.int32(idiff),
                charset_gpu,
                numpy.int32(len(charset)),
                found_nonce_gpu,
                block=(args.gpu_threads, 1, 1),
                grid=(args.gpu_blocks, 1)
            )
            
            # Get result
            cuda.memcpy_dtoh(found_nonce_buffer, found_nonce_gpu)
            if found_nonce_buffer[0] > 0:
                found = True
                nonce = found_nonce_buffer[0]
            else:
                nonce += args.gpu_blocks * args.gpu_threads * args.gpu_iterations
                
                # Occasionally print progress
                if nonce % (args.gpu_blocks * args.gpu_threads * args.gpu_iterations * 10) == 0:
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        hashrate = nonce / elapsed
                        print(f"  Hashrate: {hashrate/1000000:.2f} MH/s, Nonces: {nonce}")
        
        # Free GPU memory
        prefix_gpu.free()
        charset_gpu.free()
        required_suffix_gpu.free()
        
        # If we found a nonce
        if found:
            # Build block content
            block_content = (
                prefix +
                nonce.to_bytes(4, byteorder='little')
            ).hex()
            
            print(f"Found nonce: {nonce}")
            print(f"Block hash: {hashlib.sha256(bytes.fromhex(block_content)).hexdigest()}")
            print(f"Submitting block...")
            
            # Submit the block
            status = submit_block(node_url, block_content, pending_txs, last_block_id)
            
            if status == STATUS_SUCCESS:
                blocks_mined += 1
                print(f"✅ Block accepted! ({blocks_mined}/{args.max_blocks})")
                time.sleep(2)  # Short pause after successful mining
            elif status == STATUS_STALE:
                print("⚠️ Block was stale, someone else found it first.")
                time.sleep(2)  # Short pause before trying again
            else:
                print("❌ Block submission failed.")
                time.sleep(5)  # Longer pause on failure
        else:
            print("No solution found in this time window, refreshing work...")
    
    print(f"Mined {blocks_mined} blocks. Exiting.")

if __name__ == "__main__":
    try:
        import numpy  # Required for CUDA operations
        main()
    except ImportError:
        print("ERROR: NumPy is not installed. Install with: pip install numpy")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting on user request.")
        sys.exit(0)