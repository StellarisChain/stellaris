"""
App Load Balancer and Traffic Router

Handles load balancing and traffic routing for deployed applications
across the decentralized network.
"""

import asyncio
import json
import random
import time
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict

from lib.VoxaCommunications_Router.discovery.discovery_manager import DiscoveryManager
from lib.VoxaCommunications_Router.net.net_manager import get_global_net_manager
from util.logging import log
from util.jsonreader import read_json_from_namespace

logger = log()

class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RANDOM = "random"
    HEALTH_BASED = "health_based"
    LATENCY_BASED = "latency_based"

@dataclass
class AppEndpoint:
    """Represents an application endpoint"""
    instance_id: str
    node_id: str
    host: str
    port: int
    health_score: float = 1.0
    connections: int = 0
    weight: int = 1
    last_health_check: float = 0
    response_time: float = 0.0
    
    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

@dataclass
class AppRoute:
    """Represents a route to an application"""
    app_id: str
    app_name: str
    version: str
    path_prefix: str
    endpoints: List[AppEndpoint]
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    health_check_url: Optional[str] = None
    
class AppLoadBalancer:
    """
    Manages load balancing and traffic routing for deployed applications.
    
    Features:
    - Multiple load balancing strategies
    - Health checking
    - Automatic failover
    - Request routing based on path/host
    - Metrics collection
    - Circuit breaker pattern
    """
    
    def __init__(self):
        self.logger = log()
        self.config = read_json_from_namespace("config.apps") or {}
        self.lb_config = self.config.get("load_balancer", {})
        
        # Application routes
        self.routes: Dict[str, AppRoute] = {}  # app_id -> AppRoute
        self.path_routes: Dict[str, str] = {}  # path_prefix -> app_id
        
        # Load balancer state
        self.round_robin_counters: Dict[str, int] = defaultdict(int)
        
        # Health check state
        self.health_check_interval = self.lb_config.get("health_check_interval", 30)
        self.health_check_timeout = self.lb_config.get("health_check_timeout", 5)
        
        # Circuit breaker state
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}  # endpoint_id -> state
        
        # Metrics
        self.metrics: Dict[str, Any] = {
            "requests": defaultdict(int),
            "errors": defaultdict(int),
            "response_times": defaultdict(list)
        }
        
        # Start background tasks
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._metrics_cleanup_loop())
    
    def register_app(self, app_id: str, app_name: str, version: str, 
                    instances: List[Dict[str, Any]], routing_config: Optional[Dict[str, Any]] = None):
        """Register an application with the load balancer"""
        try:
            routing_config = routing_config or {}
            
            # Create endpoints from instances
            endpoints = []
            for instance in instances:
                if instance.get("status") == "running":
                    endpoint = AppEndpoint(
                        instance_id=instance["instance_id"],
                        node_id=instance["node_id"],
                        host=self._resolve_instance_host(instance),
                        port=self._resolve_instance_port(instance),
                        weight=routing_config.get("weight", 1)
                    )
                    endpoints.append(endpoint)
            
            if not endpoints:
                logger.warning(f"No healthy endpoints found for app {app_id}")
                return
            
            # Determine load balancing strategy
            strategy_name = routing_config.get("strategy", "round_robin")
            strategy = LoadBalancingStrategy(strategy_name)
            
            # Create route
            path_prefix = routing_config.get("path_prefix", f"/{app_name}")
            health_check_url = routing_config.get("health_check_url")
            
            route = AppRoute(
                app_id=app_id,
                app_name=app_name,
                version=version,
                path_prefix=path_prefix,
                endpoints=endpoints,
                strategy=strategy,
                health_check_url=health_check_url
            )
            
            # Register route
            self.routes[app_id] = route
            self.path_routes[path_prefix] = app_id
            
            logger.info(f"Registered app {app_name} ({app_id}) with {len(endpoints)} endpoints")
            
        except Exception as e:
            logger.error(f"Failed to register app {app_id}: {e}")
    
    def unregister_app(self, app_id: str):
        """Unregister an application from the load balancer"""
        if app_id in self.routes:
            route = self.routes[app_id]
            del self.routes[app_id]
            
            # Remove path mapping
            if route.path_prefix in self.path_routes:
                del self.path_routes[route.path_prefix]
            
            # Clean up state
            if app_id in self.round_robin_counters:
                del self.round_robin_counters[app_id]
            
            logger.info(f"Unregistered app {route.app_name} ({app_id})")
    
    def update_app_instances(self, app_id: str, instances: List[Dict[str, Any]]):
        """Update instances for an existing app"""
        if app_id not in self.routes:
            logger.warning(f"App {app_id} not registered with load balancer")
            return
        
        route = self.routes[app_id]
        
        # Create new endpoints
        new_endpoints = []
        for instance in instances:
            if instance.get("status") == "running":
                # Check if endpoint already exists
                existing = None
                for ep in route.endpoints:
                    if ep.instance_id == instance["instance_id"]:
                        existing = ep
                        break
                
                if existing:
                    # Update existing endpoint
                    new_endpoints.append(existing)
                else:
                    # Create new endpoint
                    endpoint = AppEndpoint(
                        instance_id=instance["instance_id"],
                        node_id=instance["node_id"],
                        host=self._resolve_instance_host(instance),
                        port=self._resolve_instance_port(instance)
                    )
                    new_endpoints.append(endpoint)
        
        route.endpoints = new_endpoints
        logger.info(f"Updated app {app_id} with {len(new_endpoints)} endpoints")
    
    async def route_request(self, path: str, method: str = "GET", 
                          headers: Optional[Dict[str, str]] = None) -> Optional[Tuple[str, int]]:
        """
        Route a request to an appropriate app endpoint.
        
        Returns:
            Tuple of (host, port) for the selected endpoint, or None if no route found
        """
        try:
            # Find matching route
            app_id = self._find_matching_route(path)
            if not app_id:
                return None
            
            route = self.routes[app_id]
            
            # Select endpoint using load balancing strategy
            endpoint = await self._select_endpoint(route)
            if not endpoint:
                logger.warning(f"No healthy endpoints available for app {app_id}")
                return None
            
            # Update metrics
            endpoint.connections += 1
            self.metrics["requests"][app_id] += 1
            
            return (endpoint.host, endpoint.port)
            
        except Exception as e:
            logger.error(f"Failed to route request for {path}: {e}")
            return None
    
    def _find_matching_route(self, path: str) -> Optional[str]:
        """Find the app_id that matches the request path"""
        # Try exact path match first
        if path in self.path_routes:
            return self.path_routes[path]
        
        # Try prefix matching
        for path_prefix, app_id in self.path_routes.items():
            if path.startswith(path_prefix):
                return app_id
        
        return None
    
    async def _select_endpoint(self, route: AppRoute) -> Optional[AppEndpoint]:
        """Select an endpoint based on the load balancing strategy"""
        healthy_endpoints = [ep for ep in route.endpoints if ep.health_score > 0.5]
        
        if not healthy_endpoints:
            return None
        
        if route.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_select(route.app_id, healthy_endpoints)
        
        elif route.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(healthy_endpoints, key=lambda ep: ep.connections)
        
        elif route.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(route.app_id, healthy_endpoints)
        
        elif route.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(healthy_endpoints)
        
        elif route.strategy == LoadBalancingStrategy.HEALTH_BASED:
            return max(healthy_endpoints, key=lambda ep: ep.health_score)
        
        elif route.strategy == LoadBalancingStrategy.LATENCY_BASED:
            return min(healthy_endpoints, key=lambda ep: ep.response_time or float('inf'))
        
        else:
            return healthy_endpoints[0]
    
    def _round_robin_select(self, app_id: str, endpoints: List[AppEndpoint]) -> AppEndpoint:
        """Round-robin endpoint selection"""
        counter = self.round_robin_counters[app_id]
        selected = endpoints[counter % len(endpoints)]
        self.round_robin_counters[app_id] = (counter + 1) % len(endpoints)
        return selected
    
    def _weighted_round_robin_select(self, app_id: str, endpoints: List[AppEndpoint]) -> AppEndpoint:
        """Weighted round-robin endpoint selection"""
        # Create weighted list
        weighted_endpoints = []
        for endpoint in endpoints:
            weighted_endpoints.extend([endpoint] * endpoint.weight)
        
        if not weighted_endpoints:
            return endpoints[0]
        
        counter = self.round_robin_counters[app_id]
        selected = weighted_endpoints[counter % len(weighted_endpoints)]
        self.round_robin_counters[app_id] = (counter + 1) % len(weighted_endpoints)
        return selected
    
    def _resolve_instance_host(self, instance: Dict[str, Any]) -> str:
        """Resolve the host address for an instance"""
        # This would integrate with your node discovery system
        node_id = instance.get("node_id")
        
        # For local instances
        if node_id == "local" or node_id == self._get_local_node_id():
            return "127.0.0.1"
        
        # For remote instances, resolve via discovery
        # This is a placeholder - you'd use your actual node discovery
        return f"node-{node_id}.voxa.local"
    
    def _resolve_instance_port(self, instance: Dict[str, Any]) -> int:
        """Resolve the port for an instance"""
        # Extract port from instance configuration
        # This depends on how you configure app ports
        return instance.get("port", 8080)
    
    def _get_local_node_id(self) -> str:
        """Get the local node ID"""
        # This would integrate with your node identification system
        return "local_node_id"
    
    async def _health_check_loop(self):
        """Background loop for health checking endpoints"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                for app_id, route in self.routes.items():
                    for endpoint in route.endpoints:
                        await self._check_endpoint_health(route, endpoint)
                        
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(60)
    
    async def _check_endpoint_health(self, route: AppRoute, endpoint: AppEndpoint):
        """Check the health of a specific endpoint"""
        try:
            current_time = time.time()
            
            # Skip if recently checked
            if current_time - endpoint.last_health_check < self.health_check_interval / 2:
                return
            
            endpoint.last_health_check = current_time
            
            # Determine health check URL
            if route.health_check_url:
                health_url = f"http://{endpoint.address}{route.health_check_url}"
            else:
                health_url = f"http://{endpoint.address}/health"
            
            # Perform health check
            start_time = time.time()
            
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, timeout=self.health_check_timeout) as response:
                        response_time = time.time() - start_time
                        endpoint.response_time = response_time
                        
                        if response.status == 200:
                            endpoint.health_score = min(1.0, endpoint.health_score + 0.1)
                        else:
                            endpoint.health_score = max(0.0, endpoint.health_score - 0.2)
                            
            except Exception:
                endpoint.health_score = max(0.0, endpoint.health_score - 0.3)
                endpoint.response_time = float('inf')
            
            # Update circuit breaker
            self._update_circuit_breaker(endpoint)
            
        except Exception as e:
            logger.error(f"Health check failed for {endpoint.instance_id}: {e}")
    
    def _update_circuit_breaker(self, endpoint: AppEndpoint):
        """Update circuit breaker state for an endpoint"""
        endpoint_id = f"{endpoint.instance_id}_{endpoint.address}"
        
        if endpoint_id not in self.circuit_breakers:
            self.circuit_breakers[endpoint_id] = {
                "state": "closed",  # closed, open, half_open
                "failure_count": 0,
                "last_failure_time": 0,
                "success_count": 0
            }
        
        cb = self.circuit_breakers[endpoint_id]
        
        if endpoint.health_score > 0.7:
            # Success
            cb["failure_count"] = 0
            cb["success_count"] += 1
            
            if cb["state"] == "half_open" and cb["success_count"] >= 3:
                cb["state"] = "closed"
                cb["success_count"] = 0
                
        else:
            # Failure
            cb["failure_count"] += 1
            cb["last_failure_time"] = time.time()
            cb["success_count"] = 0
            
            if cb["failure_count"] >= 5 and cb["state"] == "closed":
                cb["state"] = "open"
                logger.warning(f"Circuit breaker opened for {endpoint_id}")
    
    async def _metrics_cleanup_loop(self):
        """Background loop for cleaning up old metrics"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up old response time data
                for app_id in self.metrics["response_times"]:
                    response_times = self.metrics["response_times"][app_id]
                    if len(response_times) > 1000:
                        # Keep only recent 1000 measurements
                        self.metrics["response_times"][app_id] = response_times[-1000:]
                
            except Exception as e:
                logger.error(f"Metrics cleanup error: {e}")
    
    def get_load_balancer_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics"""
        stats = {
            "registered_apps": len(self.routes),
            "total_endpoints": sum(len(route.endpoints) for route in self.routes.values()),
            "healthy_endpoints": sum(
                sum(1 for ep in route.endpoints if ep.health_score > 0.5)
                for route in self.routes.values()
            ),
            "total_requests": sum(self.metrics["requests"].values()),
            "total_errors": sum(self.metrics["errors"].values()),
            "routes": {}
        }
        
        for app_id, route in self.routes.items():
            healthy_endpoints = [ep for ep in route.endpoints if ep.health_score > 0.5]
            stats["routes"][app_id] = {
                "app_name": route.app_name,
                "version": route.version,
                "path_prefix": route.path_prefix,
                "strategy": route.strategy.value,
                "total_endpoints": len(route.endpoints),
                "healthy_endpoints": len(healthy_endpoints),
                "requests": self.metrics["requests"][app_id],
                "errors": self.metrics["errors"][app_id]
            }
        
        return stats
    
    def update_endpoint_connection_count(self, host: str, port: int, delta: int):
        """Update connection count for an endpoint"""
        for route in self.routes.values():
            for endpoint in route.endpoints:
                if endpoint.host == host and endpoint.port == port:
                    endpoint.connections = max(0, endpoint.connections + delta)
                    break


# Global load balancer instance
_app_load_balancer: Optional[AppLoadBalancer] = None

def get_app_load_balancer() -> AppLoadBalancer:
    """Get the global app load balancer instance"""
    global _app_load_balancer
    if _app_load_balancer is None:
        _app_load_balancer = AppLoadBalancer()
    return _app_load_balancer

def set_app_load_balancer(lb: AppLoadBalancer):
    """Set the global app load balancer instance"""
    global _app_load_balancer
    _app_load_balancer = lb
