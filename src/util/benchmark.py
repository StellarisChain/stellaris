import time
import functools
import threading
from collections import defaultdict, deque
from typing import Dict, List, Callable, Any, Optional, Union
from dataclasses import dataclass, field
from statistics import mean, median, stdev
from util.logging import log
from util.jsonutils import serialize_for_json
import json
import os
from datetime import datetime


@dataclass
class BenchmarkResult:
    """Represents a single benchmark measurement."""
    function_name: str
    execution_time: float
    timestamp: datetime
    args_count: int
    kwargs_count: int
    success: bool
    error_message: Optional[str] = None
    thread_id: Optional[int] = None
    memory_usage: Optional[float] = None


@dataclass
class BenchmarkStats:
    """Statistics for a benchmarked function."""
    function_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    median_time: float = 0.0
    std_dev: float = 0.0
    success_rate: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0


class BenchmarkCollector:
    """Central collector for benchmark data with thread-safe operations."""
    
    def __init__(self, max_history: int = 1000):
        self._results: Dict[str, List[BenchmarkResult]] = defaultdict(list)
        self._stats: Dict[str, BenchmarkStats] = defaultdict(lambda: BenchmarkStats(""))
        self._lock = threading.RLock()
        self._max_history = max_history
        self.logger = log()
        
    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result in a thread-safe manner."""
        with self._lock:
            func_name = result.function_name
            
            # Add to results history
            self._results[func_name].append(result)
            
            # Maintain max history limit
            if len(self._results[func_name]) > self._max_history:
                self._results[func_name] = self._results[func_name][-self._max_history:]
            
            # Update statistics
            self._update_stats(result)
    
    def _update_stats(self, result: BenchmarkResult) -> None:
        """Update statistics for a function."""
        stats = self._stats[result.function_name]
        stats.function_name = result.function_name
        stats.total_calls += 1
        
        if result.success:
            stats.total_time += result.execution_time
            stats.min_time = min(stats.min_time, result.execution_time)
            stats.max_time = max(stats.max_time, result.execution_time)
            stats.recent_times.append(result.execution_time)
            
            # Calculate averages and statistics
            times = list(stats.recent_times)
            if times:
                stats.avg_time = mean(times)
                stats.median_time = median(times)
                if len(times) > 1:
                    stats.std_dev = stdev(times)
        else:
            stats.error_count += 1
        
        stats.success_rate = (stats.total_calls - stats.error_count) / stats.total_calls * 100
    
    def get_stats(self, function_name: Optional[str] = None) -> Union[BenchmarkStats, Dict[str, BenchmarkStats]]:
        """Get statistics for a specific function or all functions."""
        with self._lock:
            if function_name:
                return self._stats.get(function_name, BenchmarkStats(function_name))
            return dict(self._stats)
    
    def get_results(self, function_name: str, limit: Optional[int] = None) -> List[BenchmarkResult]:
        """Get recent results for a function."""
        with self._lock:
            results = self._results.get(function_name, [])
            if limit:
                return results[-limit:]
            return results.copy()
    
    def get_slowest_functions(self, limit: int = 10) -> List[BenchmarkStats]:
        """Get the slowest functions by average execution time."""
        with self._lock:
            stats_list = [stats for stats in self._stats.values() if stats.total_calls > 0]
            return sorted(stats_list, key=lambda x: x.avg_time, reverse=True)[:limit]
    
    def get_most_called_functions(self, limit: int = 10) -> List[BenchmarkStats]:
        """Get the most frequently called functions."""
        with self._lock:
            stats_list = list(self._stats.values())
            return sorted(stats_list, key=lambda x: x.total_calls, reverse=True)[:limit]
    
    def export_to_json(self, filepath: str) -> None:
        """Export benchmark data to JSON file."""
        with self._lock:
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'stats': {name: serialize_for_json(stats) for name, stats in self._stats.items()},
                'recent_results': {
                    name: [serialize_for_json(result) for result in results[-50:]]
                    for name, results in self._results.items()
                }
            }
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
    
    def clear_stats(self, function_name: Optional[str] = None) -> None:
        """Clear statistics for a specific function or all functions."""
        with self._lock:
            if function_name:
                if function_name in self._stats:
                    del self._stats[function_name]
                if function_name in self._results:
                    del self._results[function_name]
            else:
                self._stats.clear()
                self._results.clear()
    
    def print_summary(self, top_n: int = 10) -> None:
        """Print a summary of benchmark statistics."""
        with self._lock:
            print("\n" + "="*80)
            print("BENCHMARK SUMMARY")
            print("="*80)
            
            if not self._stats:
                print("No benchmark data available.")
                return
            
            print(f"\nSlowest Functions (Top {top_n}):")
            print("-" * 50)
            for i, stats in enumerate(self.get_slowest_functions(top_n), 1):
                print(f"{i:2d}. {stats.function_name:<30} "
                      f"Avg: {stats.avg_time*1000:.2f}ms "
                      f"Calls: {stats.total_calls} "
                      f"Success: {stats.success_rate:.1f}%")
            
            print(f"\nMost Called Functions (Top {top_n}):")
            print("-" * 50)
            for i, stats in enumerate(self.get_most_called_functions(top_n), 1):
                print(f"{i:2d}. {stats.function_name:<30} "
                      f"Calls: {stats.total_calls} "
                      f"Avg: {stats.avg_time*1000:.2f}ms "
                      f"Success: {stats.success_rate:.1f}%")


# Global benchmark collector instance
_global_collector = BenchmarkCollector()


def benchmark(
    name: Optional[str] = None,
    enabled: bool = True,
    log_slow_calls: bool = True,
    slow_threshold_ms: float = 1000.0,
    collect_memory: bool = False,
    collector: Optional[BenchmarkCollector] = None
):
    """
    Decorator to benchmark function execution time and collect performance metrics.
    
    Args:
        name: Custom name for the benchmark (defaults to function name)
        enabled: Whether benchmarking is enabled
        log_slow_calls: Whether to log calls that exceed the slow threshold
        slow_threshold_ms: Threshold in milliseconds for considering a call slow
        collect_memory: Whether to collect memory usage (requires psutil)
        collector: Custom collector instance (defaults to global collector)
    
    Usage:
        @benchmark()
        def my_function():
            pass
        
        @benchmark(name="custom_name", slow_threshold_ms=500)
        def another_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        if not enabled:
            return func
        
        func_name = name or f"{func.__module__}.{func.__qualname__}"
        benchmark_collector = collector or _global_collector
        logger = log()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            thread_id = threading.get_ident()
            memory_before = None
            
            if collect_memory:
                try:
                    import psutil
                    process = psutil.Process()
                    memory_before = process.memory_info().rss / 1024 / 1024  # MB
                except ImportError:
                    logger.warning("psutil not available for memory collection")
            
            success = True
            error_message = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                
                memory_usage = None
                if collect_memory and memory_before is not None:
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_after = process.memory_info().rss / 1024 / 1024  # MB
                        memory_usage = memory_after - memory_before
                    except ImportError:
                        pass
                
                # Create benchmark result
                benchmark_result = BenchmarkResult(
                    function_name=func_name,
                    execution_time=execution_time,
                    timestamp=datetime.now(),
                    args_count=len(args),
                    kwargs_count=len(kwargs),
                    success=success,
                    error_message=error_message,
                    thread_id=thread_id,
                    memory_usage=memory_usage
                )
                
                # Add to collector
                benchmark_collector.add_result(benchmark_result)
                
                # Log slow calls
                if log_slow_calls and execution_time * 1000 > slow_threshold_ms:
                    logger.warning(
                        f"Slow function call detected: {func_name} "
                        f"took {execution_time*1000:.2f}ms "
                        f"(threshold: {slow_threshold_ms}ms)"
                    )
        
        return wrapper
    return decorator


def get_benchmark_collector() -> BenchmarkCollector:
    """Get the global benchmark collector instance."""
    return _global_collector


def print_benchmark_summary(top_n: int = 10) -> None:
    """Print benchmark summary using the global collector."""
    _global_collector.print_summary(top_n)


def export_benchmarks(filepath: str = "benchmarks/benchmark_data.json") -> None:
    """Export benchmark data to JSON file."""
    _global_collector.export_to_json(filepath)


def clear_benchmarks(function_name: Optional[str] = None) -> None:
    """Clear benchmark data."""
    _global_collector.clear_stats(function_name)


# Context manager for temporary benchmarking
class BenchmarkContext:
    """Context manager for benchmarking code blocks."""
    
    def __init__(self, name: str, collector: Optional[BenchmarkCollector] = None):
        self.name = name
        self.collector = collector or _global_collector
        self.start_time = None
        self.logger = log()
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            execution_time = time.perf_counter() - self.start_time
            
            result = BenchmarkResult(
                function_name=self.name,
                execution_time=execution_time,
                timestamp=datetime.now(),
                args_count=0,
                kwargs_count=0,
                success=exc_type is None,
                error_message=str(exc_val) if exc_val else None,
                thread_id=threading.get_ident()
            )
            
            self.collector.add_result(result)


def benchmark_context(name: str, collector: Optional[BenchmarkCollector] = None) -> BenchmarkContext:
    """Create a benchmark context manager for timing code blocks."""
    return BenchmarkContext(name, collector)