from fastecdsa import curve

ENDIAN = 'little'
CURVE = curve.P256
SMALLEST = 1000000
MAX_SUPPLY = 1_062_005
VERSION = 1
MAX_BLOCK_SIZE_HEX = 4096 * 1024  # 4MB in HEX format, 2MB in raw bytes

# IBC Constants
IBC_VERSION = "1"
IBC_PORT_ID = "stellaris"
IBC_CHANNEL_VERSION = "stellaris-1"
IBC_CLIENT_TYPE = "stellaris-light"
IBC_COMMITMENT_PREFIX = "stellaris"
IBC_PACKET_TIMEOUT_HEIGHT = 1000  # blocks
IBC_PACKET_TIMEOUT_TIMESTAMP = 3600  # seconds