import xml.etree.ElementTree as ET
import os
from fastecdsa import curve

ENDIAN = 'little'
CURVE = curve.secp256k1
SMALLEST = 1000000
MAX_SUPPLY = 1_062_005
VERSION = 1
MAX_BLOCK_SIZE_HEX = 4096 * 1024  # 4MB in HEX format, 2MB in raw bytes

def _load_block_config():
    """Load block configuration from XML file and convert to dictionary."""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'block_config.xml')
    
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        
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
        
        return {'ranges': ranges}
    
    except (ET.ParseError, FileNotFoundError, ValueError) as e:
        # Return empty config if file can't be loaded
        return {'ranges': []}

BLOCK_CONFIG = _load_block_config()