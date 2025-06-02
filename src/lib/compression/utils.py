"""
Compression utilities and helper functions.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List


def analyze_json_keys(json_string: str) -> Dict[str, int]:
    """
    Analyze a JSON string to find the most frequent keys.
    
    Args:
        json_string: The JSON string to analyze
        
    Returns:
        Dictionary mapping keys to their frequency count
    """
    try:
        obj = json.loads(json_string)
        key_counts = {}
        
        def count_keys(item: Any) -> None:
            if isinstance(item, dict):
                for key, value in item.items():
                    key_counts[key] = key_counts.get(key, 0) + 1
                    count_keys(value)
            elif isinstance(item, list):
                for element in item:
                    count_keys(element)
        
        count_keys(obj)
        return dict(sorted(key_counts.items(), key=lambda x: x[1], reverse=True))
        
    except json.JSONDecodeError:
        return {}


def estimate_compression_benefit(json_string: str) -> Dict[str, Any]:
    """
    Estimate the potential compression benefit for a JSON string.
    
    Args:
        json_string: The JSON string to analyze
        
    Returns:
        Dictionary with compression analysis
    """
    from .json_compressor import JSONCompressor
    
    compressor = JSONCompressor()
    key_frequency = analyze_json_keys(json_string)
    
    # Calculate potential savings from key mapping
    total_key_savings = 0
    for key, count in key_frequency.items():
        if key in compressor.key_mappings:
            # Each occurrence saves (original_length - 1) characters
            savings_per_occurrence = len(key) - 1
            total_key_savings += savings_per_occurrence * count
    
    original_size = len(json_string.encode('utf-8'))
    compressed_size = len(compressor.compress(json_string))
    actual_ratio = original_size / compressed_size
    
    return {
        'original_size': original_size,
        'compressed_size': compressed_size,
        'compression_ratio': actual_ratio,
        'space_saved_bytes': original_size - compressed_size,
        'space_saved_percent': ((original_size - compressed_size) / original_size) * 100,
        'key_mapping_savings': total_key_savings,
        'most_frequent_keys': dict(list(key_frequency.items())[:10])
    }


def format_size(size_bytes: int) -> str:
    """
    Format a size in bytes to a human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def find_json_files(directory: str, recursive: bool = True) -> List[str]:
    """
    Find all JSON files in a directory.
    
    Args:
        directory: Directory to search
        recursive: If True, search subdirectories recursively
        
    Returns:
        List of JSON file paths
    """
    try:
        path = Path(directory)
        if not path.exists():
            return []
        
        if recursive:
            json_files = list(path.rglob("*.json"))
        else:
            json_files = list(path.glob("*.json"))
        
        return [str(f) for f in json_files]
    except Exception:
        return []


def create_backup(file_path: str, backup_suffix: str = ".backup") -> str:
    """
    Create a backup copy of a file.
    
    Args:
        file_path: Path to the file to backup
        backup_suffix: Suffix to add to backup file
        
    Returns:
        Path to the backup file
        
    Raises:
        FileNotFoundError: If original file doesn't exist
        Exception: If backup creation fails
    """
    try:
        original_path = Path(file_path)
        if not original_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        backup_path = original_path.with_suffix(original_path.suffix + backup_suffix)
        
        # Copy the file
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return str(backup_path)
    except Exception as e:
        raise Exception(f"Backup creation failed: {e}")


def validate_json_file(file_path: str) -> Dict[str, Any]:
    """
    Validate a JSON file and return information about it.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary with validation results
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                'file_path': file_path,
                'exists': False,
                'is_valid_json': False,
                'error': 'File not found'
            }
        
        file_size = path.stat().st_size
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to parse JSON
        json_obj = json.loads(content)
        
        # Count keys recursively
        def count_keys(obj):
            if isinstance(obj, dict):
                count = len(obj)
                for value in obj.values():
                    count += count_keys(value)
                return count
            elif isinstance(obj, list):
                count = 0
                for item in obj:
                    count += count_keys(item)
                return count
            return 0
        
        key_count = count_keys(json_obj)
        
        return {
            'file_path': file_path,
            'exists': True,
            'is_valid_json': True,
            'file_size': file_size,
            'character_count': len(content),
            'total_keys': key_count,
            'json_type': type(json_obj).__name__
        }
        
    except json.JSONDecodeError as e:
        return {
            'file_path': file_path,
            'exists': True,
            'is_valid_json': False,
            'error': f'Invalid JSON: {e}'
        }
    except Exception as e:
        return {
            'file_path': file_path,
            'exists': path.exists() if 'path' in locals() else False,
            'is_valid_json': False,
            'error': str(e)
        }


def clean_temp_files(directory: str, patterns: List[str] = None) -> Dict[str, Any]:
    """
    Clean temporary compression files.
    
    Args:
        directory: Directory to clean
        patterns: List of file patterns to remove (default: compression temp files)
        
    Returns:
        Dictionary with cleanup results
    """
    if patterns is None:
        patterns = ["*.compressed.bin", "*.compressed.txt", "*.tmp", "*.backup"]
    
    try:
        path = Path(directory)
        if not path.exists():
            return {
                'directory': directory,
                'files_removed': 0,
                'bytes_freed': 0,
                'error': 'Directory not found'
            }
        
        files_removed = 0
        bytes_freed = 0
        removed_files = []
        
        for pattern in patterns:
            for file_path in path.glob(pattern):
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    files_removed += 1
                    bytes_freed += file_size
                    removed_files.append(str(file_path))
                except Exception as e:
                    # Continue with other files if one fails
                    pass
        
        return {
            'directory': directory,
            'files_removed': files_removed,
            'bytes_freed': bytes_freed,
            'removed_files': removed_files
        }
        
    except Exception as e:
        return {
            'directory': directory,
            'files_removed': 0,
            'bytes_freed': 0,
            'error': str(e)
        }


def compare_compression_formats(json_string: str) -> Dict[str, Any]:
    """
    Compare different compression formats for a JSON string.
    
    Args:
        json_string: JSON string to analyze
        
    Returns:
        Dictionary comparing different compression approaches
    """
    from .json_compressor import JSONCompressor
    
    try:
        compressor = JSONCompressor()
        
        # Original size
        original_size = len(json_string.encode('utf-8'))
        
        # Binary compression
        binary_compressed = compressor.compress(json_string)
        binary_size = len(binary_compressed)
        
        # Base64 compression
        base64_compressed = compressor.compress_to_base64(json_string)
        base64_size = len(base64_compressed.encode('utf-8'))
        
        # Standard zlib compression (without key mapping)
        import zlib
        standard_zlib = zlib.compress(json_string.encode('utf-8'), level=9)
        standard_zlib_size = len(standard_zlib)
        
        return {
            'original_size': original_size,
            'formats': {
                'binary_compression': {
                    'size': binary_size,
                    'ratio': original_size / binary_size if binary_size > 0 else 0,
                    'savings_percent': ((original_size - binary_size) / original_size) * 100 if original_size > 0 else 0
                },
                'base64_compression': {
                    'size': base64_size,
                    'ratio': original_size / base64_size if base64_size > 0 else 0,
                    'savings_percent': ((original_size - base64_size) / original_size) * 100 if original_size > 0 else 0
                },
                'standard_zlib': {
                    'size': standard_zlib_size,
                    'ratio': original_size / standard_zlib_size if standard_zlib_size > 0 else 0,
                    'savings_percent': ((original_size - standard_zlib_size) / original_size) * 100 if original_size > 0 else 0
                }
            },
            'best_format': min(['binary_compression', 'base64_compression', 'standard_zlib'],
                             key=lambda x: globals()['binary_size'] if x == 'binary_compression' 
                             else globals()['base64_size'] if x == 'base64_compression' 
                             else globals()['standard_zlib_size'])
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }