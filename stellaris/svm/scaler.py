"""
Stellaris VM Scaling System
Provides parallel execution, load balancing, and performance optimization
"""

import asyncio
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple, Set
from decimal import Decimal
from dataclasses import dataclass, field
import logging
import multiprocessing as mp
from queue import Queue, Empty
import pickle
import hashlib

from stellaris.svm.vm_manager import StellarisVMManager, ExecutionResult, VMPoolStats
from stellaris.svm.vm import StellarisVM
from stellaris.svm.blockchain_interface import StellarisBlockchainInterface
from stellaris.transactions.smart_contract_transaction import SmartContractTransaction
from stellaris.database import Database


logger = logging.getLogger(__name__)


@dataclass
class ExecutionTask:
    """A task for VM execution"""
    task_id: str
    transaction: SmartContractTransaction
    sender: str
    priority: int = 0
    dependencies: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)


@dataclass
class ExecutionNode:
    """Execution node in the scaling system"""
    node_id: str
    vm_manager: StellarisVMManager
    max_concurrent: int = 4
    current_load: int = 0
    total_executed: int = 0
    avg_execution_time: float = 0.0
    is_available: bool = True
    last_heartbeat: float = field(default_factory=time.time)


class DependencyGraph:
    """Manages dependencies between smart contract transactions"""
    
    def __init__(self):
        self.graph: Dict[str, Set[str]] = {}  # tx_id -> set of dependent tx_ids
        self.reverse_graph: Dict[str, Set[str]] = {}  # tx_id -> set of dependency tx_ids
        self.completed: Set[str] = set()
    
    def add_dependency(self, tx_id: str, depends_on: str):
        """Add a dependency: tx_id depends on depends_on"""
        if tx_id not in self.graph:
            self.graph[tx_id] = set()
        if depends_on not in self.reverse_graph:
            self.reverse_graph[depends_on] = set()
        
        self.graph[tx_id].add(depends_on)
        self.reverse_graph[depends_on].add(tx_id)
    
    def get_ready_tasks(self) -> Set[str]:
        """Get tasks that are ready to execute (all dependencies completed)"""
        ready = set()
        for tx_id, dependencies in self.graph.items():
            if tx_id not in self.completed and dependencies.issubset(self.completed):
                ready.add(tx_id)
        return ready
    
    def mark_completed(self, tx_id: str):
        """Mark a task as completed"""
        self.completed.add(tx_id)
    
    def has_cycle(self) -> bool:
        """Check if the dependency graph has cycles"""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False


class StellarisVMScaler:
    """
    Stellaris VM Scaling System
    Provides parallel execution, load balancing, and performance optimization
    """
    
    def __init__(self, database: Database, max_nodes: int = 4, 
                 enable_parallel_execution: bool = True,
                 enable_dependency_analysis: bool = True):
        """
        Initialize the VM Scaler
        
        Args:
            database: Database instance
            max_nodes: Maximum number of execution nodes
            enable_parallel_execution: Enable parallel execution
            enable_dependency_analysis: Enable dependency analysis for parallelization
        """
        self.database = database
        self.max_nodes = max_nodes
        self.enable_parallel_execution = enable_parallel_execution
        self.enable_dependency_analysis = enable_dependency_analysis
        
        # Execution nodes
        self.nodes: Dict[str, ExecutionNode] = {}
        self.node_selector = 0
        
        # Task management
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.dependency_graph = DependencyGraph()
        self.active_tasks: Dict[str, ExecutionTask] = {}
        self.completed_tasks: Dict[str, ExecutionResult] = {}
        
        # Threading and processing
        self.thread_executor = ThreadPoolExecutor(max_workers=max_nodes * 2)
        self.process_executor = ProcessPoolExecutor(max_workers=max_nodes) if mp.cpu_count() > 1 else None
        
        # Statistics and monitoring
        self.total_executions = 0
        self.total_execution_time = 0.0
        self.failed_executions = 0
        self.cache_hits = 0
        
        # Performance optimization
        self.execution_cache: Dict[str, ExecutionResult] = {}
        self.cache_ttl = 3600  # 1 hour
        self.load_balancer_enabled = True
        
        # Initialize execution nodes
        self._initialize_nodes()
        
        # Start background tasks
        self.running = False
        self.background_tasks: List[asyncio.Task] = []
    
    def _initialize_nodes(self):
        """Initialize execution nodes"""
        for i in range(self.max_nodes):
            node_id = f"node_{i}"
            blockchain_interface = StellarisBlockchainInterface(self.database)
            vm_manager = StellarisVMManager(
                database=self.database,
                max_workers=2,
                vm_pool_size=4
            )
            
            node = ExecutionNode(
                node_id=node_id,
                vm_manager=vm_manager,
                max_concurrent=4
            )
            
            self.nodes[node_id] = node
        
        logger.info(f"Initialized {len(self.nodes)} execution nodes")
    
    async def start(self):
        """Start the scaling system"""
        if self.running:
            return
        
        self.running = True
        
        # Start background tasks
        self.background_tasks = [
            asyncio.create_task(self._task_processor()),
            asyncio.create_task(self._load_balancer()),
            asyncio.create_task(self._health_monitor()),
            asyncio.create_task(self._cache_cleaner())
        ]
        
        logger.info("VM Scaler started")
    
    async def stop(self):
        """Stop the scaling system"""
        self.running = False
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Cleanup executors
        self.thread_executor.shutdown(wait=True)
        if self.process_executor:
            self.process_executor.shutdown(wait=True)
        
        # Cleanup nodes
        for node in self.nodes.values():
            await node.vm_manager.cleanup()
        
        logger.info("VM Scaler stopped")
    
    async def submit_transaction(self, transaction: SmartContractTransaction, 
                               sender: str, priority: int = 0) -> str:
        """
        Submit a transaction for execution
        
        Args:
            transaction: Smart contract transaction
            sender: Sender address
            priority: Execution priority (higher = more urgent)
            
        Returns:
            Task ID
        """
        task_id = hashlib.sha256(f"{transaction.hex()}{sender}{time.time()}".encode()).hexdigest()[:16]
        
        # Analyze dependencies if enabled
        dependencies = set()
        if self.enable_dependency_analysis:
            dependencies = await self._analyze_dependencies(transaction, sender)
        
        task = ExecutionTask(
            task_id=task_id,
            transaction=transaction,
            sender=sender,
            priority=priority,
            dependencies=dependencies
        )
        
        self.active_tasks[task_id] = task
        
        # Add to dependency graph
        for dep in dependencies:
            self.dependency_graph.add_dependency(task_id, dep)
        
        # Add to appropriate queue
        if dependencies and not dependencies.issubset(self.dependency_graph.completed):
            # Has unfulfilled dependencies, will be processed when dependencies are complete
            pass
        else:
            # Ready to execute
            await self.priority_queue.put((-priority, time.time(), task))
        
        logger.debug(f"Submitted task {task_id} with {len(dependencies)} dependencies")
        return task_id
    
    async def get_result(self, task_id: str, timeout: float = 30.0) -> Optional[ExecutionResult]:
        """Get result for a task"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            await asyncio.sleep(0.1)
        
        return None
    
    async def execute_batch(self, transactions: List[Tuple[SmartContractTransaction, str]]) -> List[ExecutionResult]:
        """Execute a batch of transactions"""
        if not self.enable_parallel_execution:
            # Sequential execution
            results = []
            for tx, sender in transactions:
                task_id = await self.submit_transaction(tx, sender)
                result = await self.get_result(task_id)
                results.append(result)
            return results
        
        # Parallel execution
        task_ids = []
        for tx, sender in transactions:
            task_id = await self.submit_transaction(tx, sender)
            task_ids.append(task_id)
        
        # Wait for all results
        results = []
        for task_id in task_ids:
            result = await self.get_result(task_id)
            results.append(result)
        
        return results
    
    async def _analyze_dependencies(self, transaction: SmartContractTransaction, 
                                  sender: str) -> Set[str]:
        """Analyze dependencies for a transaction"""
        dependencies = set()
        
        if transaction.is_call():
            # Check if contract state might be modified by other pending transactions
            for task_id, task in self.active_tasks.items():
                if task_id in self.dependency_graph.completed:
                    continue
                
                # More granular dependency analysis
                if task.transaction.is_call():
                    # Only create dependency if transactions target the same contract
                    # AND involve state-modifying operations (not view calls)
                    if (task.transaction.contract_address == transaction.contract_address and
                        self._is_state_modifying_call(task.transaction) and 
                        self._is_state_modifying_call(transaction)):
                        # Further check if they affect the same state variables (simplified)
                        if self._may_conflict_state(task.transaction, transaction):
                            dependencies.add(task_id)
                
                elif (task.transaction.is_deployment() and 
                      task.transaction.get_contract_deployment_address() == transaction.contract_address):
                    # Transaction depends on contract deployment
                    dependencies.add(task_id)
        
        return dependencies
    
    def _is_state_modifying_call(self, transaction: SmartContractTransaction) -> bool:
        """
        Check if a transaction is likely to modify contract state.
        This is a simplified heuristic - in production, this would analyze the actual contract code.
        """
        # For now, assume transactions with non-zero value or specific method names modify state
        try:
            if hasattr(transaction, 'value') and transaction.value > 0:
                return True
            
            # Check method name if available (simplified)
            if hasattr(transaction, 'method_name'):
                read_only_methods = {'view', 'get', 'read', 'query', 'check'}
                method_lower = transaction.method_name.lower()
                return not any(readonly in method_lower for readonly in read_only_methods)
            
            # Default to assuming state modification for safety
            return True
        except:
            return True
    
    def _may_conflict_state(self, tx1: SmartContractTransaction, tx2: SmartContractTransaction) -> bool:
        """
        Check if two transactions may conflict on the same state variables.
        This is a simplified heuristic.
        """
        # For now, assume all state-modifying calls to the same contract may conflict
        # In production, this would analyze which state variables are accessed
        return True
    
    def _select_node(self) -> Optional[ExecutionNode]:
        """Select the best available node for execution"""
        if not self.load_balancer_enabled:
            # Improved round-robin selection with availability check
            attempts = 0
            while attempts < len(self.nodes):
                self.node_selector = (self.node_selector + 1) % len(self.nodes)
                node_id = f"node_{self.node_selector}"
                node = self.nodes.get(node_id)
                if node and node.is_available and node.current_load < node.max_concurrent:
                    return node
                attempts += 1
            return None  # No available nodes
        
        # Enhanced load-based selection with weighted scoring
        best_node = None
        best_score = float('inf')
        
        for node in self.nodes.values():
            if not node.is_available or node.current_load >= node.max_concurrent:
                continue
            
            # Enhanced scoring algorithm
            load_ratio = node.current_load / node.max_concurrent
            
            # Normalize execution time (avoid division by zero)
            time_penalty = (node.avg_execution_time / 1000.0) if node.avg_execution_time > 0 else 0.1
            
            # Add historical performance factor
            success_rate = 1.0
            if node.total_executed > 0:
                # Assume we track failed executions per node (would need to add this field)
                success_rate = max(0.1, 1.0)  # Placeholder for now
            
            # Composite score: lower is better
            score = (load_ratio * 40 +           # Load factor (40% weight)
                    time_penalty * 30 +          # Speed factor (30% weight) 
                    (1 - success_rate) * 30)     # Reliability factor (30% weight)
            
            # Add small random factor to avoid always picking the same node
            score += random.uniform(0, 0.1)
            
            if score < best_score:
                best_score = score
                best_node = node
        
        return best_node
    
    async def _execute_task(self, task: ExecutionTask) -> ExecutionResult:
        """Execute a task on a selected node"""
        # Check cache first
        cache_key = hashlib.sha256(f"{task.transaction.hex()}{task.sender}".encode()).hexdigest()
        if cache_key in self.execution_cache:
            cached_result, cache_time = self.execution_cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                self.cache_hits += 1
                return cached_result
        
        # Select execution node
        node = self._select_node()
        if not node:
            return ExecutionResult(
                success=False,
                error="No available execution nodes",
                gas_used=0
            )
        
        try:
            # Update node load
            node.current_load += 1
            start_time = time.time()
            
            # Execute transaction
            result = await node.vm_manager.execute_transaction(
                task.transaction, task.sender
            )
            
            # Update statistics
            execution_time = time.time() - start_time
            node.total_executed += 1
            node.avg_execution_time = (
                (node.avg_execution_time * (node.total_executed - 1) + execution_time * 1000) /
                node.total_executed
            )
            
            self.total_executions += 1
            self.total_execution_time += execution_time
            
            if not result.success:
                self.failed_executions += 1
            
            # Cache result
            self.execution_cache[cache_key] = (result, time.time())
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            self.failed_executions += 1
            return ExecutionResult(
                success=False,
                error=str(e),
                gas_used=task.transaction.gas_limit
            )
        
        finally:
            node.current_load = max(0, node.current_load - 1)
            node.last_heartbeat = time.time()
    
    async def _task_processor(self):
        """Background task processor"""
        while self.running:
            try:
                # Get ready tasks from dependency graph
                ready_task_ids = self.dependency_graph.get_ready_tasks()
                
                # Add ready tasks to priority queue
                for task_id in ready_task_ids:
                    if task_id in self.active_tasks:
                        task = self.active_tasks[task_id]
                        await self.priority_queue.put((-task.priority, task.created_at, task))
                        del self.active_tasks[task_id]  # Move to processing
                
                # Process priority queue
                try:
                    _, _, task = await asyncio.wait_for(self.priority_queue.get(), timeout=1.0)
                    
                    # Execute task
                    result = await self._execute_task(task)
                    
                    # Store result
                    self.completed_tasks[task.task_id] = result
                    
                    # Update dependency graph
                    self.dependency_graph.mark_completed(task.task_id)
                    
                    logger.debug(f"Completed task {task.task_id}: {'success' if result.success else 'failed'}")
                    
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in task processor: {e}")
                await asyncio.sleep(1)
    
    async def _load_balancer(self):
        """Background load balancer"""
        while self.running:
            try:
                # Monitor node health and redistribute load if needed
                total_load = sum(node.current_load for node in self.nodes.values())
                avg_load = total_load / len(self.nodes) if self.nodes else 0
                
                # Log load statistics
                if total_load > 0:
                    logger.debug(f"Total load: {total_load}, Average load: {avg_load:.2f}")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in load balancer: {e}")
                await asyncio.sleep(5)
    
    async def _health_monitor(self):
        """Monitor node health"""
        while self.running:
            try:
                current_time = time.time()
                recovered_nodes = []
                
                for node in self.nodes.values():
                    # Check node responsiveness
                    if current_time - node.last_heartbeat > 30:  # 30 second timeout
                        if node.is_available:
                            node.is_available = False
                            logger.warning(f"Node {node.node_id} marked as unavailable")
                    else:
                        if not node.is_available:
                            node.is_available = True
                            recovered_nodes.append(node.node_id)
                            logger.info(f"Node {node.node_id} recovered and marked as available")
                
                # Log recovery events
                if recovered_nodes:
                    logger.info(f"Recovered nodes: {recovered_nodes}")
                
                # Check for stalled executions and reset if needed
                self._check_stalled_executions(current_time)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(10)
    
    def _check_stalled_executions(self, current_time: float):
        """Check for and recover from stalled executions"""
        for node in self.nodes.values():
            # If a node has been unavailable for too long and has load, reset it
            if not node.is_available and node.current_load > 0:
                if current_time - node.last_heartbeat > 60:  # 1 minute
                    logger.warning(f"Resetting stalled node {node.node_id} (load: {node.current_load})")
                    node.current_load = 0
                    node.is_available = True  # Give it another chance
    
    async def _cache_cleaner(self):
        """Clean expired cache entries"""
        while self.running:
            try:
                current_time = time.time()
                expired_keys = []
                
                # Clean execution cache
                for key, (result, cache_time) in self.execution_cache.items():
                    if current_time - cache_time > self.cache_ttl:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.execution_cache[key]
                
                # Clean completed tasks if they're too old (prevent memory leak)
                old_task_keys = []
                for task_id, result in self.completed_tasks.items():
                    # Remove completed tasks older than 1 hour
                    if current_time - getattr(result, 'completion_time', current_time) > 3600:
                        old_task_keys.append(task_id)
                
                for key in old_task_keys:
                    del self.completed_tasks[key]
                
                if expired_keys or old_task_keys:
                    logger.debug(f"Cleaned {len(expired_keys)} cache entries and {len(old_task_keys)} old tasks")
                
                # Limit cache size to prevent unbounded growth
                max_cache_size = 1000
                if len(self.execution_cache) > max_cache_size:
                    # Remove oldest entries
                    sorted_cache = sorted(
                        self.execution_cache.items(),
                        key=lambda x: x[1][1]  # Sort by cache_time
                    )
                    # Keep only the newest max_cache_size entries
                    self.execution_cache = dict(sorted_cache[-max_cache_size:])
                    logger.debug(f"Trimmed execution cache to {max_cache_size} entries")
                
                await asyncio.sleep(300)  # Clean every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cache cleaner: {e}")
                await asyncio.sleep(300)
    
    def get_scaling_stats(self) -> Dict[str, Any]:
        """Get scaling system statistics"""
        node_stats = []
        for node in self.nodes.values():
            node_stats.append({
                'node_id': node.node_id,
                'current_load': node.current_load,
                'max_concurrent': node.max_concurrent,
                'total_executed': node.total_executed,
                'avg_execution_time': node.avg_execution_time,
                'is_available': node.is_available
            })
        
        return {
            'total_executions': self.total_executions,
            'failed_executions': self.failed_executions,
            'success_rate': (self.total_executions - self.failed_executions) / max(self.total_executions, 1),
            'avg_execution_time': self.total_execution_time / max(self.total_executions, 1),
            'cache_hits': self.cache_hits,
            'cache_size': len(self.execution_cache),
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'nodes': node_stats
        }
