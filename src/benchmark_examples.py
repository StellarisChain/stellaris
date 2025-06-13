#!/usr/bin/env python3
"""
Example usage and tests for the benchmark decorator system.
This file demonstrates various ways to use the benchmarking utilities.
"""

import time
import random
from util.benchmark import (
    benchmark, 
    benchmark_context, 
    print_benchmark_summary, 
    export_benchmarks,
    get_benchmark_collector,
    BenchmarkCollector
)


# Example 1: Basic function benchmarking
@benchmark()
def simple_function():
    """A simple function that sleeps for a random time."""
    time.sleep(random.uniform(0.01, 0.1))
    return "completed"


# Example 2: Function with custom benchmark name and slow threshold
@benchmark(name="encryption_simulation", slow_threshold_ms=50)
def simulate_encryption():
    """Simulate encryption work with variable timing."""
    time.sleep(random.uniform(0.02, 0.08))
    if random.random() < 0.1:  # 10% chance of being slow
        time.sleep(0.1)
    return "encrypted"


# Example 3: Function that might fail (to test error tracking)
@benchmark(name="risky_operation")
def risky_function():
    """A function that sometimes fails."""
    if random.random() < 0.2:  # 20% chance of failure
        raise ValueError("Random failure occurred")
    time.sleep(random.uniform(0.005, 0.03))
    return "success"


# Example 4: Function with memory monitoring (requires psutil)
@benchmark(name="memory_intensive", collect_memory=True)
def memory_intensive_function():
    """Function that uses memory."""
    # Simulate memory usage
    data = [i for i in range(10000)]
    time.sleep(0.01)
    return len(data)


# Example 5: Using benchmark with the multi-threaded encryption function
# (Applying it to the function we created earlier)
def apply_benchmark_to_routing():
    """Example of applying benchmark to existing routing functions."""
    from lib.VoxaCommunications_Router.routing.routeutils import encrypt_routing_chain_threaded
    
    # You can dynamically add benchmarking to existing functions
    benchmarked_encrypt = benchmark(
        name="routing.encrypt_chain_threaded",
        slow_threshold_ms=2000
    )(encrypt_routing_chain_threaded)
    
    return benchmarked_encrypt


# Example 6: Using custom collector for specific module benchmarking
routing_collector = BenchmarkCollector(max_history=500)

@benchmark(name="routing.helper_function", collector=routing_collector)
def routing_helper():
    """Helper function with dedicated collector."""
    time.sleep(random.uniform(0.001, 0.01))
    return "routing_complete"


def run_benchmark_examples():
    """Run various benchmark examples to generate test data."""
    print("Running benchmark examples...")
    
    # Run functions multiple times to generate data
    for i in range(20):
        simple_function()
        simulate_encryption()
        memory_intensive_function()
        routing_helper()
        
        try:
            risky_function()
        except ValueError:
            pass  # Expected failures
    
    # Example of using context manager for timing code blocks
    with benchmark_context("database_operation"):
        time.sleep(0.05)
        # Simulate database work
        data = {"id": 1, "value": "test"}
    
    with benchmark_context("file_processing"):
        time.sleep(0.02)
        # Simulate file processing
        pass
    
    # Example of using context manager with custom collector
    with benchmark_context("routing_context", routing_collector):
        time.sleep(0.03)
        # Simulate routing work
        pass


def analyze_benchmarks():
    """Analyze and display benchmark results."""
    print("\n" + "="*60)
    print("BENCHMARK ANALYSIS")
    print("="*60)
    
    # Get global collector
    collector = get_benchmark_collector()
    
    # Print summary
    print_benchmark_summary(top_n=5)
    
    # Get specific function stats
    encryption_stats = collector.get_stats("encryption_simulation")
    print(f"\nEncryption Simulation Details:")
    print(f"  Total calls: {encryption_stats.total_calls}")
    print(f"  Average time: {encryption_stats.avg_time*1000:.2f}ms")
    print(f"  Min time: {encryption_stats.min_time*1000:.2f}ms")
    print(f"  Max time: {encryption_stats.max_time*1000:.2f}ms")
    print(f"  Success rate: {encryption_stats.success_rate:.1f}%")
    
    # Analyze routing collector separately
    print(f"\nRouting Module Benchmarks:")
    print("-" * 30)
    routing_stats = routing_collector.get_stats()
    for name, stats in routing_stats.items():
        print(f"  {name}: {stats.total_calls} calls, "
              f"avg {stats.avg_time*1000:.2f}ms")
    
    # Export data
    export_benchmarks("benchmarks/example_benchmarks.json")
    routing_collector.export_to_json("benchmarks/routing_benchmarks.json")
    print(f"\nBenchmark data exported to benchmarks/ directory")


def benchmark_comparison():
    """Compare different implementations."""
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)
    
    # Create separate collectors for comparison
    old_impl_collector = BenchmarkCollector()
    new_impl_collector = BenchmarkCollector()
    
    @benchmark(name="old_implementation", collector=old_impl_collector)
    def old_implementation():
        # Simulate old slower implementation
        time.sleep(random.uniform(0.02, 0.05))
        return "old_result"
    
    @benchmark(name="new_implementation", collector=new_impl_collector)
    def new_implementation():
        # Simulate new faster implementation
        time.sleep(random.uniform(0.005, 0.02))
        return "new_result"
    
    # Run both implementations
    for _ in range(50):
        old_implementation()
        new_implementation()
    
    # Compare results
    old_stats = old_impl_collector.get_stats("old_implementation")
    new_stats = new_impl_collector.get_stats("new_implementation")
    
    improvement = ((old_stats.avg_time - new_stats.avg_time) / old_stats.avg_time) * 100
    
    print(f"Old implementation: {old_stats.avg_time*1000:.2f}ms average")
    print(f"New implementation: {new_stats.avg_time*1000:.2f}ms average")
    print(f"Performance improvement: {improvement:.1f}%")


if __name__ == "__main__":
    # Run examples
    run_benchmark_examples()
    
    # Analyze results
    analyze_benchmarks()
    
    # Performance comparison
    benchmark_comparison()
    
    print("\nBenchmark examples completed!")