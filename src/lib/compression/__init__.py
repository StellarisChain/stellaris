"""
JSON Compression Library

This module provides efficient compression and decompression of JSON strings
using a combination of techniques including key mapping, zlib compression,
and binary encoding. Includes comprehensive file I/O capabilities.
"""

from .json_compressor import JSONCompressor
from .utils import (
    analyze_json_keys, 
    estimate_compression_benefit, 
    format_size,
    find_json_files,
    create_backup,
    validate_json_file,
    clean_temp_files,
    compare_compression_formats
)

__all__ = [
    'JSONCompressor', 
    'analyze_json_keys', 
    'estimate_compression_benefit', 
    'format_size',
    'find_json_files',
    'create_backup',
    'validate_json_file',
    'clean_temp_files',
    'compare_compression_formats'
]