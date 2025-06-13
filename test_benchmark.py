#!/usr/bin/env python3
"""
Quick test to verify the benchmark decorator system works.
"""

import sys
import os
sys.path.append('/workspaces/VoxaCommunications-NetNode/src')

import time
import random
from util.benchmark import benchmark, print_benchmark_summary, export_benchmarks

@benchmark()
def test_function_1():
    """Test function with basic benchmarking."""
    time.sleep(random.uniform(0.01, 0.05))
    return "test1_complete"

@benchmark(name="slow_operation", slow_threshold_ms=30)
def test_function_2():
    """Test function that sometimes triggers slow call warnings."""
    sleep_time = random.uniform(0.01, 0.08)
    time.sleep(sleep_time)
    return f"slept_{sleep_time:.3f}s"

def run_test():
    """Run a quick test of the benchmark system."""
    print("Testing benchmark decorator system...")
    
    # Run test functions multiple times
    for i in range(10):
        test_function_1()
        test_function_2()
    
    # Print summary
    print_benchmark_summary(top_n=5)
    
    # Export data
    export_benchmarks("test_benchmarks.json")
    print("\nTest completed! Benchmark data exported to test_benchmarks.json")

if __name__ == "__main__":
    run_test()