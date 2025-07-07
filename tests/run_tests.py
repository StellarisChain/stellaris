#!/usr/bin/env python3
"""
Test runner for BPF VM functionality
"""

import sys
import os
import subprocess

def run_tests():
    """Run all tests"""
    # Add the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Run pytest
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_bpf_vm.py', 
            '-v', '--tb=short'
        ], cwd=project_root, capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def validate_imports():
    """Validate that all imports work"""
    try:
        # Test basic imports
        from stellaris.bpf_vm import BPFVirtualMachine, BPFContract, BPFExecutor
        from stellaris.transactions import BPFContractTransaction
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def main():
    """Main test runner"""
    print("BPF VM Test Suite")
    print("=" * 40)
    
    # First validate imports
    if not validate_imports():
        print("Import validation failed. Exiting.")
        sys.exit(1)
    
    # Run tests
    print("\nRunning tests...")
    if run_tests():
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()