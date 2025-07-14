from fastecdsa import curve

ENDIAN = 'little'
CURVE = curve.P256
SMALLEST = 1000000
MAX_SUPPLY = 1_062_005
VERSION = 1
MAX_BLOCK_SIZE_HEX = 4096 * 1024  # 4MB in HEX format, 2MB in raw bytes

# BPF VM constants
BPF_VERSION = 4  # Transaction version for BPF contracts
BPF_MAX_GAS = 1000000
BPF_DEFAULT_GAS = 100000