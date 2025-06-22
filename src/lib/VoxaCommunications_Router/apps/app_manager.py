"""
Decentralized App Manager

Handles deployment, execution, and lifecycle management of decentralized applications
on the VoxaCommunications network.
"""

import asyncio
import json
import os
import subprocess
import uuid
import docker
import hashlib
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

from lib.VoxaCommunications_Router.util.logging import log
from lib.VoxaCommunications_Router.net.net_manager import NetManager, get_global_net_manager
from lib.VoxaCommunications_Router.discovery.discovery_manager import DiscoveryManager
from util.jsonreader import read_json_from_namespace


class AppStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    BUILDING = "building"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    SCALING = "scaling"


@dataclass
class AppSpec:
    """Application specification for deployment"""
    app_id: str
    name: str
    version: str
    image: Optional[str] = None  # Docker image
    source_code_hash: Optional[str] = None  # For source-based deployments
    build_config: Optional[Dict[str, Any]] = None
    runtime_config: Dict[str, Any] = None
    resource_requirements: Dict[str, Any] = None
    network_config: Dict[str, Any] = None
    replicas: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppInstance:
    """Running instance of an application"""
    instance_id: str
    app_id: str
    node_id: str
    container_id: Optional[str] = None
    process_id: Optional[int] = None
    status: AppStatus = AppStatus.PENDING
    created_at: datetime = None
    updated_at: datetime = None
    health_endpoint: Optional[str] = None
    metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['status'] = self.status.value
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result


class AppManager:
    """
    Manages decentralized application deployment and execution.
    
    Features:
    - Docker-based containerization
    - Source code deployment and building
    - Resource allocation and limits
    - Health monitoring
    - Auto-scaling based on network load
    - P2P app discovery and routing
    """
    
    def __init__(self):
        self.logger = log()
        self.docker_client = None
        self.net_manager: NetManager = get_global_net_manager()
        self.discovery_manager = DiscoveryManager()
        
        # Configuration
        self.config = read_json_from_namespace("config.apps") or self._default_config()
        
        # Storage
        self.apps: Dict[str, AppSpec] = {}  # app_id -> AppSpec
        self.instances: Dict[str, AppInstance] = {}  # instance_id -> AppInstance
        self.node_instances: Dict[str, List[str]] = {}  # node_id -> [instance_ids]
        
        # App data directory
        self.app_data_dir = Path(self.config.get("app_data_dir", "data/apps"))
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        self._setup_docker()
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for app manager"""
        return {
            "app_data_dir": "data/apps",
            "max_apps_per_node": 10,
            "default_memory_limit": "512m",
            "default_cpu_limit": "1.0",
            "health_check_interval": 30,
            "scale_threshold_cpu": 80,
            "scale_threshold_memory": 85,
            "enable_auto_scaling": True,
            "docker_network": "voxacomms-apps",
            "registry_urls": ["docker.io", "ghcr.io"],
            "build_timeout": 600,  # 10 minutes
            "deployment_strategies": ["blue_green", "rolling", "canary"]
        }
    
    def _setup_docker(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.logger.info("Docker client initialized successfully")
            
            # Create app network if it doesn't exist
            network_name = self.config.get("docker_network", "voxacomms-apps")
            try:
                self.docker_client.networks.get(network_name)
            except docker.errors.NotFound:
                self.docker_client.networks.create(
                    network_name,
                    driver="bridge",
                    labels={"managed_by": "voxacommunications"}
                )
                self.logger.info(f"Created Docker network: {network_name}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Docker: {e}")
            self.docker_client = None

    async def deploy_app(self, app_spec: AppSpec, target_nodes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Deploy an application to the network
        
        Args:
            app_spec: Application specification
            target_nodes: Specific nodes to deploy to (None for auto-selection)
            
        Returns:
            Deployment status and instance information
        """
        self.logger.info(f"Deploying app {app_spec.name} (ID: {app_spec.app_id})")
        
        # Store app spec
        self.apps[app_spec.app_id] = app_spec
        
        # Select target nodes if not specified
        if target_nodes is None:
            target_nodes = await self._select_deployment_nodes(app_spec)
        
        if not target_nodes:
            raise ValueError("No suitable nodes found for deployment")
        
        # Create instances
        instances = []
        for i in range(app_spec.replicas):
            node_id = target_nodes[i % len(target_nodes)]
            instance_id = f"{app_spec.app_id}-{uuid.uuid4().hex[:8]}"
            
            instance = AppInstance(
                instance_id=instance_id,
                app_id=app_spec.app_id,
                node_id=node_id,
                status=AppStatus.PENDING
            )
            
            self.instances[instance_id] = instance
            
            if node_id not in self.node_instances:
                self.node_instances[node_id] = []
            self.node_instances[node_id].append(instance_id)
            
            instances.append(instance)
        
        # Deploy to each node
        deployment_tasks = []
        for instance in instances:
            if instance.node_id == self._get_local_node_id():
                # Deploy locally
                task = asyncio.create_task(self._deploy_local_instance(app_spec, instance))
            else:
                # Deploy to remote node
                task = asyncio.create_task(self._deploy_remote_instance(app_spec, instance))
            deployment_tasks.append(task)
        
        # Wait for all deployments
        results = await asyncio.gather(*deployment_tasks, return_exceptions=True)
        
        # Process results
        successful = 0
        failed = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                instances[i].status = AppStatus.FAILED
                failed += 1
                self.logger.error(f"Failed to deploy instance {instances[i].instance_id}: {result}")
            else:
                successful += 1
        
        return {
            "app_id": app_spec.app_id,
            "deployment_id": str(uuid.uuid4()),
            "instances": [instance.to_dict() for instance in instances],
            "successful": successful,
            "failed": failed,
            "total": len(instances)
        }

    async def _deploy_local_instance(self, app_spec: AppSpec, instance: AppInstance) -> bool:
        """Deploy an instance locally using Docker"""
        try:
            if not self.docker_client:
                raise RuntimeError("Docker client not available")
            
            instance.status = AppStatus.DOWNLOADING
            self._update_instance(instance)
            
            # Handle different deployment types
            if app_spec.image:
                # Container-based deployment
                await self._deploy_container_instance(app_spec, instance)
            elif app_spec.source_code_hash:
                # Source-based deployment
                await self._deploy_source_instance(app_spec, instance)
            else:
                raise ValueError("Either image or source_code_hash must be specified")
            
            instance.status = AppStatus.RUNNING
            self._update_instance(instance)
            
            # Start health monitoring
            asyncio.create_task(self._monitor_instance_health(instance))
            
            return True
            
        except Exception as e:
            instance.status = AppStatus.FAILED
            self._update_instance(instance)
            self.logger.error(f"Failed to deploy local instance {instance.instance_id}: {e}")
            return False

    async def _deploy_container_instance(self, app_spec: AppSpec, instance: AppInstance):
        """Deploy a Docker container instance"""
        try:
            # Pull image if needed
            image_name = app_spec.image
            self.logger.info(f"Pulling image {image_name}")
            self.docker_client.images.pull(image_name)
            
            # Prepare container configuration
            container_config = self._build_container_config(app_spec, instance)
            
            # Create and start container
            container = self.docker_client.containers.run(
                image_name,
                name=f"voxacomms-app-{instance.instance_id}",
                detach=True,
                **container_config
            )
            
            instance.container_id = container.id
            instance.status = AppStatus.RUNNING
            
            self.logger.info(f"Container {container.id} started for instance {instance.instance_id}")
            
        except Exception as e:
            raise RuntimeError(f"Container deployment failed: {e}")

    async def _deploy_source_instance(self, app_spec: AppSpec, instance: AppInstance):
        """Deploy from source code"""
        try:
            instance.status = AppStatus.BUILDING
            self._update_instance(instance)
            
            # Download source code (implement P2P source distribution)
            source_dir = await self._download_source_code(app_spec.source_code_hash)
            
            # Build the application
            image_tag = f"voxacomms-app-{app_spec.app_id}:{app_spec.version}"
            await self._build_source_image(source_dir, image_tag, app_spec.build_config)
            
            # Deploy the built image
            app_spec.image = image_tag
            await self._deploy_container_instance(app_spec, instance)
            
        except Exception as e:
            raise RuntimeError(f"Source deployment failed: {e}")

    def _build_container_config(self, app_spec: AppSpec, instance: AppInstance) -> Dict[str, Any]:
        """Build Docker container configuration"""
        config = {
            "network": self.config.get("docker_network", "voxacomms-apps"),
            "labels": {
                "managed_by": "voxacommunications",
                "app_id": app_spec.app_id,
                "instance_id": instance.instance_id,
                "node_id": instance.node_id
            },
            "restart_policy": {"Name": "unless-stopped"}
        }
        
        # Resource limits
        if app_spec.resource_requirements:
            mem_limit = app_spec.resource_requirements.get("memory", self.config.get("default_memory_limit"))
            cpu_limit = app_spec.resource_requirements.get("cpu", self.config.get("default_cpu_limit"))
            
            config["mem_limit"] = mem_limit
            config["cpu_quota"] = int(float(cpu_limit) * 100000)
            config["cpu_period"] = 100000
        
        # Environment variables
        config["environment"] = {
            "VOXA_APP_ID": app_spec.app_id,
            "VOXA_INSTANCE_ID": instance.instance_id,
            "VOXA_NODE_ID": instance.node_id,
            **app_spec.runtime_config.get("environment", {})
        }
        
        # Port mappings
        if app_spec.network_config and "ports" in app_spec.network_config:
            config["ports"] = app_spec.network_config["ports"]
        
        # Volumes
        app_volume_dir = self.app_data_dir / app_spec.app_id / instance.instance_id
        app_volume_dir.mkdir(parents=True, exist_ok=True)
        config["volumes"] = {
            str(app_volume_dir): {"bind": "/app/data", "mode": "rw"}
        }
        
        return config

    async def _deploy_remote_instance(self, app_spec: AppSpec, instance: AppInstance) -> bool:
        """Deploy instance to a remote node via P2P network"""
        try:
            # Use the existing P2P network to send deployment request
            deployment_request = {
                "action": "deploy_app",
                "app_spec": app_spec.to_dict(),
                "instance": instance.to_dict()
            }
            
            # Send request via SSU/P2P network
            # This would integrate with your existing net_manager and routing
            success = await self._send_p2p_deployment_request(instance.node_id, deployment_request)
            
            if success:
                instance.status = AppStatus.RUNNING  # Will be updated by remote node status
                return True
            else:
                instance.status = AppStatus.FAILED
                return False
                
        except Exception as e:
            self.logger.error(f"Remote deployment failed for {instance.instance_id}: {e}")
            instance.status = AppStatus.FAILED
            return False

    async def _send_p2p_deployment_request(self, target_node_id: str, request: Dict[str, Any]) -> bool:
        """Send deployment request via P2P network"""
        # This would integrate with your SSU/P2P networking
        # Implementation depends on your existing routing and messaging system
        try:
            # Use your existing InternalHTTPPacket or SSU system
            from lib.VoxaCommunications_Router.net.packets import InternalHTTPPacket
            
            packet = InternalHTTPPacket(
                addr=target_node_id,  # This would need to be resolved to actual address
                method="POST",
                endpoint="/api/apps/deploy",
                data=json.dumps(request)
            )
            
            # Send via your existing SSU system
            # This is a placeholder - you'd use your actual P2P sending mechanism
            response = await self.net_manager.ssu_node.send_packet(packet)
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Failed to send P2P deployment request: {e}")
            return False

    async def _select_deployment_nodes(self, app_spec: AppSpec) -> List[str]:
        """Select optimal nodes for deployment based on resources and network topology"""
        try:
            # For local development/testing, use local node if network discovery is disabled
            discovery_config = self.config.get("discovery", {})
            if not discovery_config.get("enable_network_discovery", True):
                self.logger.info("Network discovery disabled, using local node for deployment")
                return ["local"]
            
            # Get network overview from discovery manager with timeout
            try:
                network_info = await asyncio.wait_for(
                    self.discovery_manager.get_network_overview(),
                    timeout=discovery_config.get("discovery_timeout", 10)
                )
                available_nodes = network_info.get("nodes", {})
            except asyncio.TimeoutError:
                self.logger.warning("Network discovery timed out, falling back to local deployment")
                return ["local"]
            
            # Filter nodes based on capabilities and resources
            suitable_nodes = []
            for node_id, node_info in available_nodes.items():
                if self._is_node_suitable(node_info, app_spec):
                    suitable_nodes.append(node_id)
            
            # If no suitable nodes found, fall back to local
            if not suitable_nodes:
                self.logger.info("No suitable remote nodes found, using local node")
                return ["local"]
            
            # Sort by preference (load, latency, resources, etc.)
            suitable_nodes.sort(key=lambda n: self._calculate_node_score(n, app_spec))
            
            # Return top nodes up to required replicas
            return suitable_nodes[:app_spec.replicas]
            
        except Exception as e:
            self.logger.error(f"Node selection failed: {e}, falling back to local deployment")
            return ["local"]

    def _is_node_suitable(self, node_info: Dict[str, Any], app_spec: AppSpec) -> bool:
        """Check if a node is suitable for the application"""
        # Check capabilities
        capabilities = node_info.get("capabilities", [])
        if "app-deployment" not in capabilities:
            return False
        
        # Check current load
        current_apps = len(self.node_instances.get(node_info.get("node_id", ""), []))
        max_apps = self.config.get("max_apps_per_node", 10)
        if current_apps >= max_apps:
            return False
        
        # Check resource requirements
        if app_spec.resource_requirements:
            # This would check available CPU, memory, storage, etc.
            # Implementation depends on how you track node resources
            pass
        
        return True

    def _calculate_node_score(self, node_id: str, app_spec: AppSpec) -> float:
        """Calculate preference score for a node (lower is better)"""
        score = 0.0
        
        # Factor in current load
        current_load = len(self.node_instances.get(node_id, []))
        score += current_load * 10
        
        # Factor in network latency (if available)
        # score += estimated_latency * 5
        
        # Factor in resource availability
        # score += resource_utilization * 3
        
        return score

    async def _monitor_instance_health(self, instance: AppInstance):
        """Monitor the health of a running instance"""
        while instance.status == AppStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.get("health_check_interval", 30))
                
                # Check container health
                if instance.container_id and self.docker_client:
                    container = self.docker_client.containers.get(instance.container_id)
                    
                    if container.status != "running":
                        instance.status = AppStatus.FAILED
                        self.logger.warning(f"Instance {instance.instance_id} container stopped")
                        break
                    
                    # Update metrics
                    stats = container.stats(stream=False)
                    instance.metrics = self._extract_container_metrics(stats)
                    
                # Check health endpoint if configured
                if instance.health_endpoint:
                    healthy = await self._check_health_endpoint(instance.health_endpoint)
                    if not healthy:
                        instance.status = AppStatus.FAILED
                        self.logger.warning(f"Instance {instance.instance_id} health check failed")
                        break
                
                instance.updated_at = datetime.utcnow()
                
            except Exception as e:
                self.logger.error(f"Health check failed for {instance.instance_id}: {e}")
                await asyncio.sleep(5)  # Short retry interval

    def _extract_container_metrics(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metrics from Docker container stats"""
        try:
            # CPU usage
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})
            
            cpu_usage = 0.0
            if cpu_stats and precpu_stats:
                cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - precpu_stats["cpu_usage"]["total_usage"]
                system_delta = cpu_stats["system_cpu_usage"] - precpu_stats["system_cpu_usage"]
                if system_delta > 0:
                    cpu_usage = (cpu_delta / system_delta) * 100.0
            
            # Memory usage
            memory_stats = stats.get("memory_stats", {})
            memory_usage = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 0)
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
            
            return {
                "cpu_usage_percent": cpu_usage,
                "memory_usage_bytes": memory_usage,
                "memory_usage_percent": memory_percent,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to extract metrics: {e}")
            return {}

    async def _check_health_endpoint(self, endpoint: str) -> bool:
        """Check application health via HTTP endpoint"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, timeout=10) as response:
                    return response.status == 200
        except Exception:
            return False

    def _update_instance(self, instance: AppInstance):
        """Update instance information"""
        instance.updated_at = datetime.utcnow()
        self.instances[instance.instance_id] = instance

    def _get_local_node_id(self) -> str:
        """Get the current node's ID"""
        # This would integrate with your existing node identification system
        return "local"  # For development/testing

    async def stop_app(self, app_id: str) -> Dict[str, Any]:
        """Stop all instances of an application"""
        if app_id not in self.apps:
            raise ValueError(f"App {app_id} not found")
        
        instances = [inst for inst in self.instances.values() if inst.app_id == app_id]
        stopped = 0
        failed = 0
        
        for instance in instances:
            try:
                if instance.container_id and self.docker_client:
                    container = self.docker_client.containers.get(instance.container_id)
                    container.stop(timeout=30)
                    container.remove()
                
                instance.status = AppStatus.STOPPED
                self._update_instance(instance)
                stopped += 1
                
            except Exception as e:
                self.logger.error(f"Failed to stop instance {instance.instance_id}: {e}")
                failed += 1
        
        return {
            "app_id": app_id,
            "stopped": stopped,
            "failed": failed,
            "total": len(instances)
        }

    def get_app_status(self, app_id: str) -> Dict[str, Any]:
        """Get status of an application and its instances"""
        if app_id not in self.apps:
            raise ValueError(f"App {app_id} not found")
        
        app_spec = self.apps[app_id]
        instances = [inst for inst in self.instances.values() if inst.app_id == app_id]
        
        status_counts = {}
        for instance in instances:
            status = instance.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "app_id": app_id,
            "app_spec": app_spec.to_dict(),
            "instances": [inst.to_dict() for inst in instances],
            "status_summary": status_counts,
            "total_instances": len(instances)
        }

    def list_apps(self) -> List[Dict[str, Any]]:
        """List all managed applications"""
        return [
            {
                "app_id": app_id,
                "name": spec.name,
                "version": spec.version,
                "replicas": spec.replicas,
                "instances": len([inst for inst in self.instances.values() if inst.app_id == app_id])
            }
            for app_id, spec in self.apps.items()
        ]

    async def scale_app(self, app_id: str, new_replica_count: int) -> Dict[str, Any]:
        """Scale an application to a new replica count"""
        if app_id not in self.apps:
            raise ValueError(f"App {app_id} not found")
        
        app_spec = self.apps[app_id]
        current_instances = [inst for inst in self.instances.values() if inst.app_id == app_id]
        current_count = len(current_instances)
        
        if new_replica_count == current_count:
            return {"message": "No scaling needed", "current_replicas": current_count}
        
        if new_replica_count > current_count:
            # Scale up
            additional_replicas = new_replica_count - current_count
            app_spec.replicas = additional_replicas
            
            result = await self.deploy_app(app_spec)
            return {
                "action": "scale_up",
                "previous_replicas": current_count,
                "new_replicas": new_replica_count,
                "deployment_result": result
            }
        else:
            # Scale down
            instances_to_remove = current_instances[new_replica_count:]
            removed = 0
            
            for instance in instances_to_remove:
                try:
                    if instance.container_id and self.docker_client:
                        container = self.docker_client.containers.get(instance.container_id)
                        container.stop(timeout=30)
                        container.remove()
                    
                    instance.status = AppStatus.STOPPED
                    removed += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to remove instance {instance.instance_id}: {e}")
            
            return {
                "action": "scale_down",
                "previous_replicas": current_count,
                "new_replicas": new_replica_count,
                "removed_instances": removed
            }

    async def _download_source_code(self, source_hash: str) -> Path:
        """Download source code from P2P network using hash"""
        # This would integrate with your P2P file sharing system
        # Implementation depends on how you handle distributed file storage
        source_dir = self.app_data_dir / "sources" / source_hash
        source_dir.mkdir(parents=True, exist_ok=True)
        
        # Placeholder for P2P source download
        # You'd implement this using your existing P2P file transfer mechanisms
        
        return source_dir

    async def _build_source_image(self, source_dir: Path, image_tag: str, build_config: Optional[Dict[str, Any]]):
        """Build Docker image from source code"""
        try:
            dockerfile_path = source_dir / "Dockerfile"
            if not dockerfile_path.exists():
                # Generate Dockerfile based on build config
                await self._generate_dockerfile(source_dir, build_config)
            
            # Build image
            self.logger.info(f"Building image {image_tag} from {source_dir}")
            image, logs = self.docker_client.images.build(
                path=str(source_dir),
                tag=image_tag,
                timeout=self.config.get("build_timeout", 600)
            )
            
            self.logger.info(f"Successfully built image {image_tag}")
            return image
            
        except Exception as e:
            raise RuntimeError(f"Failed to build image: {e}")

    async def _generate_dockerfile(self, source_dir: Path, build_config: Optional[Dict[str, Any]]):
        """Generate Dockerfile based on build configuration"""
        if not build_config:
            build_config = {"runtime": "python", "version": "3.12"}
        
        runtime = build_config.get("runtime", "python")
        version = build_config.get("version", "3.12")
        
        dockerfile_content = f"""
FROM {runtime}:{version}

WORKDIR /app
COPY . .

# Install dependencies based on runtime
"""
        
        if runtime == "python":
            dockerfile_content += """
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
CMD ["python", "main.py"]
"""
        elif runtime == "node":
            dockerfile_content += """
RUN if [ -f package.json ]; then npm install; fi
CMD ["node", "index.js"]
"""
        
        dockerfile_path = source_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content.strip())


# Global app manager instance
_app_manager: Optional[AppManager] = None

def get_global_app_manager() -> AppManager:
    """Get the global app manager instance"""
    global _app_manager
    if _app_manager is None:
        _app_manager = AppManager()
    return _app_manager

def set_global_app_manager(manager: AppManager) -> None:
    """Set the global app manager instance"""
    global _app_manager
    _app_manager = manager
