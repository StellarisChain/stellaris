import xml.etree.ElementTree as ET
import os
from fastecdsa import curve

ENDIAN = 'little'
CURVE = curve.secp256k1
SMALLEST = 1000000
MAX_SUPPLY = 1_062_005
VERSION = 1
MAX_BLOCK_SIZE_HEX = 4096 * 1024  # 4MB in HEX format, 2MB in raw bytes

# Network identification - prevents mainnet/testnet cross-connection
NETWORK_ID = os.environ.get('STELLARIS_NETWORK_ID', 'mainnet')  # 'mainnet' or 'testnet'
NETWORK_MAGIC_BYTES = {
    'mainnet': b'STLR',  # Network magic bytes for mainnet
    'testnet': b'TEST',  # Network magic bytes for testnet
}

# Treasury configuration
TREASURY_WALLET = "E32vDuz39DjXmDyJF1juU9cvt1yJ4W8xdGcZAj76i5uUH"  # Default treasury wallet
TREASURY_TAX_RATE = 0.25  # 25% tax rate
TREASURY_TAX_INTERVAL = 2500  # Tax occurs every 25,000 blocks

def _load_block_config():
    """Load block configuration from XML file and convert to dictionary."""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'block_config.xml')
    
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        
        # Parse activation block
        activation_elem = root.find('ActivationBlock')
        activation_block = int(activation_elem.text) if activation_elem is not None else 0
        
        # Parse treasury configuration
        treasury_elem = root.find('Treasury')
        treasury_config = {}
        if treasury_elem is not None:
            wallet_elem = treasury_elem.find('WalletAddress')
            tax_rate_elem = treasury_elem.find('TaxRate')
            tax_interval_elem = treasury_elem.find('TaxInterval')
            
            treasury_config = {
                'wallet_address': wallet_elem.text if wallet_elem is not None else TREASURY_WALLET,
                'tax_rate': float(tax_rate_elem.text) if tax_rate_elem is not None else TREASURY_TAX_RATE,
                'tax_interval': int(tax_interval_elem.text) if tax_interval_elem is not None else TREASURY_TAX_INTERVAL
            }
        else:
            treasury_config = {
                'wallet_address': TREASURY_WALLET,
                'tax_rate': TREASURY_TAX_RATE,
                'tax_interval': TREASURY_TAX_INTERVAL
            }
        
        ranges = []
        prev_max = 0
        
        for range_elem in root.findall('Range'):
            min_index = range_elem.get('minIndex')
            max_index = int(range_elem.get('maxIndex'))
            
            # Handle "previous" keyword
            if min_index == "previous":
                min_index = prev_max + 1
            else:
                min_index = int(min_index)
            
            reward_elem = range_elem.find('Reward')
            max_difficulty_elem = range_elem.find('MaxDifficulty')
            
            range_config = {
                'min_index': min_index,
                'max_index': max_index,
                'reward': float(reward_elem.text) if reward_elem is not None else 0,
                'max_difficulty': float(max_difficulty_elem.text) if max_difficulty_elem is not None else 0
            }
            
            ranges.append(range_config)
            prev_max = max_index
        
        return {
            'activation_block': activation_block,
            'treasury': treasury_config,
            'ranges': ranges
        }
    
    except (ET.ParseError, FileNotFoundError, ValueError) as e:
        # Return empty config if file can't be loaded
        treasury_config = {
            'wallet_address': TREASURY_WALLET,
            'tax_rate': TREASURY_TAX_RATE,
            'tax_interval': TREASURY_TAX_INTERVAL
        }
        return {
            'activation_block': 0,
            'treasury': treasury_config,
            'ranges': []
        }

BLOCK_CONFIG = _load_block_config()