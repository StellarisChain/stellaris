#!/usr/bin/env python3
"""
Test script for the JSON compression library with file I/O capabilities.
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lib.compression import (
    JSONCompressor, 
    analyze_json_keys, 
    estimate_compression_benefit, 
    format_size,
    find_json_files,
    create_backup,
    validate_json_file,
    clean_temp_files,
    compare_compression_formats
)


def test_basic_compression():
    """Test basic compression and decompression functionality."""
    print("=== Basic Compression Test ===")
    
    compressor = JSONCompressor()
    
    # Test with a simple JSON
    test_json = json.dumps({
        "id": 12345,
        "name": "Test User",
        "type": "user",
        "data": {
            "settings": {
                "version": "1.0",
                "config": {"enabled": True}
            },
            "timestamp": "2025-06-02T10:00:00Z",
            "status": "active"
        }
    }, indent=2)
    
    print(f"Original JSON ({len(test_json)} bytes):")
    print(test_json[:200] + "..." if len(test_json) > 200 else test_json)
    
    # Compress
    compressed = compressor.compress(test_json)
    print(f"\nCompressed size: {len(compressed)} bytes")
    
    # Decompress
    decompressed = compressor.decompress(compressed)
    print(f"Decompressed size: {len(decompressed)} bytes")
    
    # Verify they're equivalent
    original_obj = json.loads(test_json)
    decompressed_obj = json.loads(decompressed)
    
    if original_obj == decompressed_obj:
        print("✅ Compression/decompression successful!")
        ratio = len(test_json) / len(compressed)
        print(f"Compression ratio: {ratio:.2f}x")
    else:
        print("❌ Compression/decompression failed!")
    
    return original_obj == decompressed_obj


def test_base64_compression():
    """Test base64 compression functionality."""
    print("\n=== Base64 Compression Test ===")
    
    compressor = JSONCompressor()
    
    test_json = json.dumps({
        "message": "Hello, World!",
        "timestamp": "2025-06-02T10:00:00Z",
        "user": {"id": 1, "name": "Alice"},
        "data": [1, 2, 3, 4, 5]
    })
    
    # Compress to base64
    base64_compressed = compressor.compress_to_base64(test_json)
    print(f"Base64 compressed: {base64_compressed}")
    print(f"Length: {len(base64_compressed)} characters")
    
    # Decompress from base64
    decompressed = compressor.decompress_from_base64(base64_compressed)
    
    original_obj = json.loads(test_json)
    decompressed_obj = json.loads(decompressed)
    
    if original_obj == decompressed_obj:
        print("✅ Base64 compression/decompression successful!")
    else:
        print("❌ Base64 compression/decompression failed!")
    
    return original_obj == decompressed_obj


def test_large_json():
    """Test with a larger, more complex JSON structure."""
    print("\n=== Large JSON Test ===")
    
    # Create a larger test JSON
    large_json = {
        "users": [],
        "settings": {
            "version": "2.1.0",
            "config": {
                "timeout": 30,
                "retries": 3
            }
        },
        "data": {
            "items": [],
            "total": 0,
            "timestamp": "2025-06-02T10:00:00Z"
        }
    }
    
    # Add many users
    for i in range(100):
        user = {
            "id": i,
            "name": f"User {i}",
            "type": "standard",
            "status": "active" if i % 2 == 0 else "inactive",
            "created": "2025-01-01T00:00:00Z",
            "updated": "2025-06-02T10:00:00Z",
            "data": {
                "settings": {"notifications": True},
                "stats": {"login_count": i * 10}
            }
        }
        large_json["users"].append(user)
        
        item = {
            "id": f"item_{i}",
            "value": f"Value {i}",
            "timestamp": "2025-06-02T10:00:00Z"
        }
        large_json["data"]["items"].append(item)
    
    large_json["data"]["total"] = len(large_json["data"]["items"])
    
    test_json_str = json.dumps(large_json, indent=2)
    
    compressor = JSONCompressor()
    
    print(f"Original size: {format_size(len(test_json_str))}")
    
    # Analyze compression benefit
    analysis = estimate_compression_benefit(test_json_str)
    print(f"Compression analysis:")
    print(f"  - Compression ratio: {analysis['compression_ratio']:.2f}x")
    print(f"  - Space saved: {format_size(analysis['space_saved_bytes'])} ({analysis['space_saved_percent']:.1f}%)")
    print(f"  - Key mapping savings: {analysis['key_mapping_savings']} characters")
    
    # Test compression
    compressed = compressor.compress(test_json_str)
    decompressed = compressor.decompress(compressed)
    
    original_obj = json.loads(test_json_str)
    decompressed_obj = json.loads(decompressed)
    
    if original_obj == decompressed_obj:
        print("✅ Large JSON compression/decompression successful!")
    else:
        print("❌ Large JSON compression/decompression failed!")
    
    return original_obj == decompressed_obj


def test_key_analysis():
    """Test key frequency analysis."""
    print("\n=== Key Analysis Test ===")
    
    test_json = json.dumps({
        "users": [
            {"id": 1, "name": "Alice", "type": "admin"},
            {"id": 2, "name": "Bob", "type": "user"},
            {"id": 3, "name": "Charlie", "type": "user"}
        ],
        "settings": {"version": "1.0", "config": {"enabled": True}},
        "data": {"timestamp": "2025-06-02", "status": "ok"}
    })
    
    key_freq = analyze_json_keys(test_json)
    print("Key frequency analysis:")
    for key, count in key_freq.items():
        print(f"  '{key}': {count} occurrences")
    
    return len(key_freq) > 0


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n=== Error Handling Test ===")
    
    compressor = JSONCompressor()
    
    # Test invalid JSON
    try:
        compressor.compress("invalid json {")
        print("❌ Should have failed on invalid JSON")
        return False
    except ValueError:
        print("✅ Correctly handled invalid JSON")
    
    # Test invalid compressed data
    try:
        compressor.decompress(b"invalid data")
        print("❌ Should have failed on invalid compressed data")
        return False
    except ValueError:
        print("✅ Correctly handled invalid compressed data")
    
    # Test invalid base64
    try:
        compressor.decompress_from_base64("invalid base64!")
        print("❌ Should have failed on invalid base64")
        return False
    except ValueError:
        print("✅ Correctly handled invalid base64")
    
    return True


def test_file_compression():
    """Test file compression and decompression functionality."""
    print("\n=== File Compression Test ===")
    
    compressor = JSONCompressor()
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test JSON file
        test_data = {
            "id": 12345,
            "name": "Test User",
            "type": "user",
            "data": {
                "settings": {
                    "version": "1.0",
                    "config": {"enabled": True, "timeout": 30}
                },
                "timestamp": "2025-06-02T10:00:00Z",
                "status": "active",
                "items": [
                    {"id": 1, "value": "Item 1", "type": "standard"},
                    {"id": 2, "value": "Item 2", "type": "premium"},
                    {"id": 3, "value": "Item 3", "type": "standard"}
                ]
            }
        }
        
        input_file = temp_path / "test_input.json"
        binary_output = temp_path / "test_output.bin"
        base64_output = temp_path / "test_output.txt"
        decompressed_binary = temp_path / "decompressed_binary.json"
        decompressed_base64 = temp_path / "decompressed_base64.json"
        
        # Write test JSON file
        with open(input_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"Created test file: {input_file}")
        print(f"Original size: {format_size(input_file.stat().st_size)}")
        
        # Test binary compression
        result_binary = compressor.compress_file(str(input_file), str(binary_output), use_base64=False)
        print(f"Binary compressed size: {format_size(result_binary['compressed_size'])}")
        print(f"Binary compression ratio: {result_binary['compression_ratio']:.2f}x")
        
        # Test base64 compression
        result_base64 = compressor.compress_file(str(input_file), str(base64_output), use_base64=True)
        print(f"Base64 compressed size: {format_size(result_base64['compressed_size'])}")
        print(f"Base64 compression ratio: {result_base64['compression_ratio']:.2f}x")
        
        # Test binary decompression
        decomp_result_binary = compressor.decompress_file(str(binary_output), str(decompressed_binary), is_base64=False)
        print(f"Binary decompressed size: {format_size(decomp_result_binary['decompressed_size'])}")
        
        # Test base64 decompression
        decomp_result_base64 = compressor.decompress_file(str(base64_output), str(decompressed_base64), is_base64=True)
        print(f"Base64 decompressed size: {format_size(decomp_result_base64['decompressed_size'])}")
        
        # Verify files are identical
        with open(input_file, 'r') as f1, open(decompressed_binary, 'r') as f2, open(decompressed_base64, 'r') as f3:
            original = json.load(f1)
            binary_decompressed = json.load(f2)
            base64_decompressed = json.load(f3)
        
        if original == binary_decompressed == base64_decompressed:
            print("✅ File compression/decompression successful!")
            return True
        else:
            print("❌ File compression/decompression failed!")
            return False


def test_batch_compression():
    """Test batch compression of multiple files."""
    print("\n=== Batch Compression Test ===")
    
    compressor = JSONCompressor()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"
        input_dir.mkdir()
        
        # Create multiple test JSON files
        test_files = []
        for i in range(5):
            test_data = {
                "id": i,
                "name": f"User {i}",
                "type": "test_user",
                "data": {
                    "created": "2025-06-02T10:00:00Z",
                    "status": "active",
                    "settings": {"notifications": True, "theme": "dark"},
                    "items": [{"id": j, "value": f"Item {j}"} for j in range(10)]
                }
            }
            
            file_path = input_dir / f"user_{i}.json"
            with open(file_path, 'w') as f:
                json.dump(test_data, f, indent=2)
            test_files.append(file_path)
        
        print(f"Created {len(test_files)} test files")
        
        # Test batch compression
        batch_result = compressor.batch_compress_files(str(input_dir), str(output_dir), use_base64=False)
        
        print(f"Batch compression results:")
        print(f"  - Total files: {batch_result['total_files']}")
        print(f"  - Successful: {batch_result['successful_compressions']}")
        print(f"  - Failed: {batch_result['failed_compressions']}")
        print(f"  - Total original size: {format_size(batch_result['total_original_size'])}")
        print(f"  - Total compressed size: {format_size(batch_result['total_compressed_size'])}")
        print(f"  - Overall compression ratio: {batch_result['overall_compression_ratio']:.2f}x")
        print(f"  - Total space saved: {format_size(batch_result['total_space_saved'])}")
        
        if batch_result['successful_compressions'] == batch_result['total_files']:
            print("✅ Batch compression successful!")
            return True
        else:
            print("❌ Batch compression failed!")
            return False


def test_file_utilities():
    """Test file utility functions."""
    print("\n=== File Utilities Test ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test JSON file
        test_data = {"id": 1, "name": "Test", "data": {"value": 42}}
        test_file = temp_path / "test.json"
        
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        # Test file validation
        validation_result = validate_json_file(str(test_file))
        print(f"File validation result:")
        print(f"  - Valid JSON: {validation_result['is_valid_json']}")
        print(f"  - File size: {format_size(validation_result['file_size'])}")
        print(f"  - Total keys: {validation_result['total_keys']}")
        
        # Test backup creation
        backup_path = create_backup(str(test_file))
        print(f"Backup created: {backup_path}")
        
        # Test find JSON files
        json_files = find_json_files(str(temp_path))
        print(f"Found JSON files: {len(json_files)}")
        
        # Test compression format comparison
        with open(test_file, 'r') as f:
            json_content = f.read()
        
        comparison = compare_compression_formats(json_content)
        print(f"Compression format comparison:")
        for format_name, stats in comparison['formats'].items():
            print(f"  - {format_name}: {format_size(stats['size'])} ({stats['ratio']:.2f}x)")
        
        # Test cleanup
        cleanup_result = clean_temp_files(str(temp_path))
        print(f"Cleanup result: {cleanup_result['files_removed']} files removed")
        
        return True


def test_file_info():
    """Test file information functionality."""
    print("\n=== File Info Test ===")
    
    compressor = JSONCompressor()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test files
        json_file = temp_path / "test.json"
        compressed_file = temp_path / "test.bin"
        
        test_data = {"message": "Hello, World!", "data": [1, 2, 3]}
        
        with open(json_file, 'w') as f:
            json.dump(test_data, f)
        
        # Compress the file
        compressor.compress_file(str(json_file), str(compressed_file))
        
        # Get file info
        json_info = compressor.get_file_info(str(json_file))
        compressed_info = compressor.get_file_info(str(compressed_file))
        
        print(f"JSON file info:")
        print(f"  - Type: {json_info['file_type']}")
        print(f"  - Size: {format_size(json_info['file_size'])}")
        if 'is_valid_json' in json_info:
            print(f"  - Valid JSON: {json_info['is_valid_json']}")
            if 'potential_compression_ratio' in json_info:
                print(f"  - Potential compression: {json_info['potential_compression_ratio']:.2f}x")
        
        print(f"Compressed file info:")
        print(f"  - Type: {compressed_info['file_type']}")
        print(f"  - Size: {format_size(compressed_info['file_size'])}")
        
        return True


def test_real_world_scenario():
    """Test with a realistic JSON structure similar to config files."""
    print("\n=== Real-World Scenario Test ===")
    
    compressor = JSONCompressor()
    
    # Create a realistic configuration file structure
    config_data = {
        "version": "2.1.0",
        "settings": {
            "server": {
                "host": "localhost",
                "port": 8080,
                "timeout": 30,
                "max_connections": 100
            },
            "database": {
                "type": "postgresql",
                "host": "db.example.com",
                "port": 5432,
                "name": "myapp",
                "user": "dbuser",
                "settings": {
                    "pool_size": 10,
                    "timeout": 30
                }
            },
            "logging": {
                "level": "info",
                "file": "/var/log/app.log",
                "max_size": "10MB",
                "rotate": True
            }
        },
        "features": {
            "authentication": {
                "enabled": True,
                "type": "oauth2",
                "providers": ["google", "github", "facebook"]
            },
            "cache": {
                "enabled": True,
                "type": "redis",
                "host": "cache.example.com",
                "ttl": 3600
            },
            "monitoring": {
                "enabled": True,
                "metrics": {
                    "response_time": True,
                    "error_rate": True,
                    "throughput": True
                }
            }
        },
        "users": []
    }
    
    # Add many users to make it more realistic
    for i in range(50):
        user = {
            "id": i + 1,
            "name": f"User {i + 1}",
            "email": f"user{i + 1}@example.com",
            "created": "2025-01-01T00:00:00Z",
            "updated": "2025-06-02T10:00:00Z",
            "status": "active" if i % 3 != 0 else "inactive",
            "settings": {
                "notifications": True,
                "theme": "light" if i % 2 == 0 else "dark",
                "language": "en"
            },
            "permissions": ["read", "write"] if i % 5 == 0 else ["read"]
        }
        config_data["users"].append(user)
    
    json_string = json.dumps(config_data, indent=2)
    
    print(f"Original JSON size: {format_size(len(json_string))}")
    
    # Analyze the JSON
    analysis = estimate_compression_benefit(json_string)
    print(f"Compression analysis:")
    print(f"  - Estimated ratio: {analysis['compression_ratio']:.2f}x")
    print(f"  - Space saved: {format_size(analysis['space_saved_bytes'])} ({analysis['space_saved_percent']:.1f}%)")
    print(f"  - Key mapping savings: {analysis['key_mapping_savings']} characters")
    
    # Show most frequent keys
    print(f"  - Most frequent keys: {list(analysis['most_frequent_keys'].keys())[:5]}")
    
    # Test compression
    compressed = compressor.compress(json_string)
    decompressed = compressor.decompress(compressed)
    
    original_obj = json.loads(json_string)
    decompressed_obj = json.loads(decompressed)
    
    if original_obj == decompressed_obj:
        print("✅ Real-world scenario test successful!")
        actual_ratio = len(json_string) / len(compressed)
        print(f"Actual compression ratio: {actual_ratio:.2f}x")
        return True
    else:
        print("❌ Real-world scenario test failed!")
        return False


def main():
    """Run all tests."""
    print("JSON Compression Library Test Suite with File I/O")
    print("=" * 60)
    
    tests = [
        test_basic_compression,
        test_base64_compression,
        test_large_json,
        test_key_analysis,
        test_error_handling,
        test_file_compression,
        test_batch_compression,
        test_file_utilities,
        test_file_info,
        test_real_world_scenario
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{len(tests)} tests")
    
    if passed == len(tests):
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())