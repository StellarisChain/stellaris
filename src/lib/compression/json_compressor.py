"""
JSON Compressor Implementation

This module provides efficient compression and decompression of JSON strings
using multiple techniques:
1. Key mapping to replace common JSON keys with shorter representations
2. zlib compression for binary data reduction
3. Base64 encoding for safe binary transport
4. File I/O operations for reading and writing compressed data
"""

import json
import zlib
import base64
import struct
import os
from pathlib import Path
from typing import Dict, Any, Union


class JSONCompressor:
    """
    A class for compressing and decompressing JSON strings efficiently.
    
    Uses key mapping and zlib compression to achieve significant size reduction
    while maintaining full reversibility. Includes file I/O capabilities.
    """
    
    def __init__(self):
        """Initialize the JSONCompressor with default key mappings."""
        # Common JSON keys that appear frequently - map to single characters
        self.key_mappings = {
            'id': 'a',
            'name': 'b',
            'type': 'c',
            'data': 'd',
            'value': 'e',
            'timestamp': 'f',
            'status': 'g',
            'message': 'h',
            'user': 'i',
            'config': 'j',
            'settings': 'k',
            'version': 'l',
            'created': 'm',
            'updated': 'n',
            'url': 'o',
            'path': 'p',
            'method': 'q',
            'params': 'r',
            'response': 's',
            'error': 't',
            'success': 'u',
            'total': 'v',
            'count': 'w',
            'items': 'x',
            'result': 'y',
            'payload': 'z'
        }
        
        # Reverse mapping for decompression
        self.reverse_mappings = {v: k for k, v in self.key_mappings.items()}
    
    def _map_keys(self, obj: Any) -> Any:
        """
        Recursively map JSON keys to shorter representations.
        
        Args:
            obj: The object to process (dict, list, or primitive)
            
        Returns:
            Object with mapped keys
        """
        if isinstance(obj, dict):
            mapped = {}
            for key, value in obj.items():
                # Use mapping if available, otherwise keep original key
                new_key = self.key_mappings.get(key, key)
                mapped[new_key] = self._map_keys(value)
            return mapped
        elif isinstance(obj, list):
            return [self._map_keys(item) for item in obj]
        else:
            return obj
    
    def _unmap_keys(self, obj: Any) -> Any:
        """
        Recursively restore original JSON keys from mapped representations.
        
        Args:
            obj: The object to process (dict, list, or primitive)
            
        Returns:
            Object with original keys restored
        """
        if isinstance(obj, dict):
            unmapped = {}
            for key, value in obj.items():
                # Restore original key if it was mapped
                original_key = self.reverse_mappings.get(key, key)
                unmapped[original_key] = self._unmap_keys(value)
            return unmapped
        elif isinstance(obj, list):
            return [self._unmap_keys(item) for item in obj]
        else:
            return obj
    
    def compress(self, json_string: str) -> bytes:
        """
        Compress a JSON string into binary format.
        
        Args:
            json_string: The JSON string to compress
            
        Returns:
            Compressed binary data
            
        Raises:
            ValueError: If the input is not valid JSON
            Exception: If compression fails
        """
        try:
            # Parse JSON to ensure it's valid
            json_obj = json.loads(json_string)
            
            # Map keys to shorter representations
            mapped_obj = self._map_keys(json_obj)
            
            # Convert back to JSON string with minimal formatting
            mapped_json = json.dumps(mapped_obj, separators=(',', ':'), ensure_ascii=False)
            
            # Compress using zlib
            compressed_data = zlib.compress(mapped_json.encode('utf-8'), level=9)
            
            # Add header with original length for validation
            original_length = len(json_string)
            header = struct.pack('<I', original_length)  # Little-endian 4-byte unsigned int
            
            return header + compressed_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")
        except Exception as e:
            raise Exception(f"Compression failed: {e}")
    
    def decompress(self, compressed_data: bytes) -> str:
        """
        Decompress binary data back to a JSON string.
        
        Args:
            compressed_data: The compressed binary data
            
        Returns:
            The original JSON string
            
        Raises:
            ValueError: If the compressed data is invalid
            Exception: If decompression fails
        """
        try:
            if len(compressed_data) < 4:
                raise ValueError("Invalid compressed data: too short")
            
            # Extract header
            original_length = struct.unpack('<I', compressed_data[:4])[0]
            compressed_payload = compressed_data[4:]
            
            # Decompress using zlib
            decompressed_data = zlib.decompress(compressed_payload)
            mapped_json = decompressed_data.decode('utf-8')
            
            # Parse the mapped JSON
            mapped_obj = json.loads(mapped_json)
            
            # Restore original keys
            original_obj = self._unmap_keys(mapped_obj)
            
            # Convert back to JSON string with pretty formatting
            result = json.dumps(original_obj, indent=2, ensure_ascii=False)
            
            return result
            
        except zlib.error as e:
            raise ValueError(f"Invalid compressed data: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted JSON data: {e}")
        except Exception as e:
            raise Exception(f"Decompression failed: {e}")
    
    def compress_to_base64(self, json_string: str) -> str:
        """
        Compress a JSON string and encode as base64 for safe transport.
        
        Args:
            json_string: The JSON string to compress
            
        Returns:
            Base64-encoded compressed data
        """
        compressed_data = self.compress(json_string)
        return base64.b64encode(compressed_data).decode('ascii')
    
    def decompress_from_base64(self, base64_data: str) -> str:
        """
        Decompress from base64-encoded compressed data.
        
        Args:
            base64_data: Base64-encoded compressed data
            
        Returns:
            The original JSON string
        """
        try:
            compressed_data = base64.b64decode(base64_data.encode('ascii'))
            return self.decompress(compressed_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 data: {e}")
    
    def get_compression_ratio(self, json_string: str) -> float:
        """
        Calculate the compression ratio for a JSON string.
        
        Args:
            json_string: The JSON string to analyze
            
        Returns:
            Compression ratio (original_size / compressed_size)
        """
        try:
            compressed_data = self.compress(json_string)
            original_size = len(json_string.encode('utf-8'))
            compressed_size = len(compressed_data)
            return original_size / compressed_size if compressed_size > 0 else 0
        except Exception:
            return 0
    
    def add_key_mapping(self, original_key: str, mapped_key: str) -> None:
        """
        Add a custom key mapping for compression.
        
        Args:
            original_key: The original JSON key
            mapped_key: The shorter representation
            
        Raises:
            ValueError: If the mapping would create conflicts
        """
        if mapped_key in self.reverse_mappings:
            existing_key = self.reverse_mappings[mapped_key]
            if existing_key != original_key:
                raise ValueError(f"Mapping conflict: '{mapped_key}' already maps to '{existing_key}'")
        
        self.key_mappings[original_key] = mapped_key
        self.reverse_mappings[mapped_key] = original_key
    
    def compress_file(self, input_file_path: str, output_file_path: str, use_base64: bool = False) -> Dict[str, Any]:
        """
        Compress a JSON file and save to a new file.
        
        Args:
            input_file_path: Path to the input JSON file
            output_file_path: Path to save the compressed file
            use_base64: If True, save as base64 text file, otherwise save as binary
            
        Returns:
            Dictionary with compression statistics
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If input file is not valid JSON
            Exception: If compression or file operations fail
        """
        try:
            # Read the JSON file
            json_string = self.read_json_file(input_file_path)
            
            # Get original file size
            original_size = os.path.getsize(input_file_path)
            
            if use_base64:
                # Compress to base64 and save as text file
                compressed_data = self.compress_to_base64(json_string)
                self.write_text_file(output_file_path, compressed_data)
            else:
                # Compress to binary and save as binary file
                compressed_data = self.compress(json_string)
                self.write_binary_file(output_file_path, compressed_data)
            
            # Get compressed file size
            compressed_size = os.path.getsize(output_file_path)
            
            return {
                'input_file': input_file_path,
                'output_file': output_file_path,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': original_size / compressed_size if compressed_size > 0 else 0,
                'space_saved_bytes': original_size - compressed_size,
                'space_saved_percent': ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0,
                'format': 'base64' if use_base64 else 'binary'
            }
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        except Exception as e:
            raise Exception(f"File compression failed: {e}")
    
    def decompress_file(self, input_file_path: str, output_file_path: str, is_base64: bool = False) -> Dict[str, Any]:
        """
        Decompress a compressed file and save as JSON.
        
        Args:
            input_file_path: Path to the compressed file
            output_file_path: Path to save the decompressed JSON file
            is_base64: If True, read as base64 text file, otherwise read as binary
            
        Returns:
            Dictionary with decompression statistics
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If compressed data is invalid
            Exception: If decompression or file operations fail
        """
        try:
            # Get compressed file size
            compressed_size = os.path.getsize(input_file_path)
            
            if is_base64:
                # Read base64 data and decompress
                base64_data = self.read_text_file(input_file_path)
                json_string = self.decompress_from_base64(base64_data)
            else:
                # Read binary data and decompress
                compressed_data = self.read_binary_file(input_file_path)
                json_string = self.decompress(compressed_data)
            
            # Save decompressed JSON
            self.write_json_file(output_file_path, json_string)
            
            # Get decompressed file size
            decompressed_size = os.path.getsize(output_file_path)
            
            return {
                'input_file': input_file_path,
                'output_file': output_file_path,
                'compressed_size': compressed_size,
                'decompressed_size': decompressed_size,
                'expansion_ratio': decompressed_size / compressed_size if compressed_size > 0 else 0,
                'format': 'base64' if is_base64 else 'binary'
            }
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        except Exception as e:
            raise Exception(f"File decompression failed: {e}")
    
    def read_json_file(self, file_path: str) -> str:
        """
        Read and validate a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            JSON content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not valid JSON
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON
            json.loads(content)
            return content
            
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file {file_path}: {e}")
        except Exception as e:
            raise Exception(f"Error reading JSON file {file_path}: {e}")
    
    def write_json_file(self, file_path: str, json_string: str) -> None:
        """
        Write JSON string to a file with pretty formatting.
        
        Args:
            file_path: Path to save the JSON file
            json_string: JSON content to write
            
        Raises:
            ValueError: If json_string is not valid JSON
            Exception: If file write fails
        """
        try:
            # Validate and pretty-format JSON
            json_obj = json.loads(json_string)
            formatted_json = json.dumps(json_obj, indent=2, ensure_ascii=False)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_json)
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")
        except Exception as e:
            raise Exception(f"Error writing JSON file {file_path}: {e}")
    
    def read_binary_file(self, file_path: str) -> bytes:
        """
        Read binary data from a file.
        
        Args:
            file_path: Path to the binary file
            
        Returns:
            Binary data
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except Exception as e:
            raise Exception(f"Error reading binary file {file_path}: {e}")
    
    def write_binary_file(self, file_path: str, data: bytes) -> None:
        """
        Write binary data to a file.
        
        Args:
            file_path: Path to save the binary file
            data: Binary data to write
            
        Raises:
            Exception: If file write fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            raise Exception(f"Error writing binary file {file_path}: {e}")
    
    def read_text_file(self, file_path: str) -> str:
        """
        Read text data from a file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Text content
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except Exception as e:
            raise Exception(f"Error reading text file {file_path}: {e}")
    
    def write_text_file(self, file_path: str, content: str) -> None:
        """
        Write text content to a file.
        
        Args:
            file_path: Path to save the text file
            content: Text content to write
            
        Raises:
            Exception: If file write fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            raise Exception(f"Error writing text file {file_path}: {e}")
    
    def batch_compress_files(self, input_dir: str, output_dir: str, use_base64: bool = False, 
                           pattern: str = "*.json") -> Dict[str, Any]:
        """
        Compress multiple JSON files in a directory.
        
        Args:
            input_dir: Directory containing JSON files
            output_dir: Directory to save compressed files
            use_base64: If True, save as base64 text files
            pattern: File pattern to match (default: "*.json")
            
        Returns:
            Dictionary with batch compression statistics
            
        Raises:
            Exception: If batch compression fails
        """
        try:
            from pathlib import Path
            
            input_path = Path(input_dir)
            output_path = Path(output_dir)
            
            if not input_path.exists():
                raise FileNotFoundError(f"Input directory not found: {input_dir}")
            
            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Find JSON files
            json_files = list(input_path.glob(pattern))
            
            if not json_files:
                raise ValueError(f"No files matching pattern '{pattern}' found in {input_dir}")
            
            results = []
            total_original_size = 0
            total_compressed_size = 0
            
            for json_file in json_files:
                try:
                    # Determine output file extension
                    if use_base64:
                        output_file = output_path / f"{json_file.stem}.compressed.txt"
                    else:
                        output_file = output_path / f"{json_file.stem}.compressed.bin"
                    
                    # Compress file
                    result = self.compress_file(str(json_file), str(output_file), use_base64)
                    results.append(result)
                    
                    total_original_size += result['original_size']
                    total_compressed_size += result['compressed_size']
                    
                except Exception as e:
                    results.append({
                        'input_file': str(json_file),
                        'error': str(e),
                        'success': False
                    })
            
            # Calculate overall statistics
            successful_compressions = [r for r in results if 'error' not in r]
            
            return {
                'input_directory': input_dir,
                'output_directory': output_dir,
                'total_files': len(json_files),
                'successful_compressions': len(successful_compressions),
                'failed_compressions': len(results) - len(successful_compressions),
                'total_original_size': total_original_size,
                'total_compressed_size': total_compressed_size,
                'overall_compression_ratio': total_original_size / total_compressed_size if total_compressed_size > 0 else 0,
                'total_space_saved': total_original_size - total_compressed_size,
                'format': 'base64' if use_base64 else 'binary',
                'results': results
            }
            
        except Exception as e:
            raise Exception(f"Batch compression failed: {e}")
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get information about a file (JSON, compressed, etc.).
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = path.stat().st_size
            file_type = "unknown"
            
            # Determine file type
            if path.suffix.lower() == '.json':
                file_type = "json"
                try:
                    content = self.read_json_file(file_path)
                    analysis = self.get_compression_ratio(content)
                    return {
                        'file_path': file_path,
                        'file_type': file_type,
                        'file_size': file_size,
                        'is_valid_json': True,
                        'potential_compression_ratio': analysis
                    }
                except:
                    return {
                        'file_path': file_path,
                        'file_type': file_type,
                        'file_size': file_size,
                        'is_valid_json': False
                    }
            
            elif path.suffix.lower() in ['.bin', '.compressed']:
                file_type = "compressed_binary"
                
            elif path.suffix.lower() == '.txt':
                # Check if it's base64 compressed data
                try:
                    content = self.read_text_file(file_path)
                    # Try to decode as base64
                    base64.b64decode(content.encode('ascii'))
                    file_type = "compressed_base64"
                except:
                    file_type = "text"
            
            return {
                'file_path': file_path,
                'file_type': file_type,
                'file_size': file_size
            }
            
        except Exception as e:
            return {
                'file_path': file_path,
                'error': str(e)
            }