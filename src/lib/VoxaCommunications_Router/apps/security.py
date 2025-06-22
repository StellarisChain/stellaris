"""
App Security and Sandboxing

Provides security controls and sandboxing for deployed applications.
"""

import os
import json
import subprocess
from typing import Dict, Any, List
from pathlib import Path

from util.logging import log
from util.jsonreader import read_json_from_namespace

logger = log()

class AppSandbox:
    """
    Provides security sandboxing for deployed applications.
    
    Features:
    - Resource limits (CPU, memory, disk, network)
    - Filesystem isolation
    - Network isolation
    - Process limits
    - Capability restrictions
    """
    
    def __init__(self):
        self.config = read_json_from_namespace("config.apps") or {}
        self.security_config = self.config.get("security", {})
        
    def get_container_security_options(self, app_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Get Docker security options for an app container"""
        security_opts = []
        
        # Basic security options
        if not self.security_config.get("allow_privileged_containers", False):
            security_opts.append("no-new-privileges:true")
        
        # AppArmor/SELinux profiles
        if os.path.exists("/sys/kernel/security/apparmor"):
            security_opts.append("apparmor=docker-default")
        
        # Seccomp profile
        security_opts.append("seccomp=default")
        
        return {
            "security_opt": security_opts,
            "cap_drop": ["ALL"],
            "cap_add": self._get_required_capabilities(app_spec),
            "read_only": self.security_config.get("read_only_rootfs", True),
            "user": "1000:1000",  # Non-root user
            "tmpfs": {"/tmp": "noexec,nosuid,size=100m"}
        }
    
    def _get_required_capabilities(self, app_spec: Dict[str, Any]) -> List[str]:
        """Get minimal required capabilities for the app"""
        base_caps = ["SETGID", "SETUID"]  # Basic capabilities
        
        # Add network capabilities if needed
        network_config = app_spec.get("network_config", {})
        if network_config.get("bind_ports", False):
            base_caps.append("NET_BIND_SERVICE")
        
        return base_caps
    
    def get_resource_limits(self, app_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Get resource limits for an app"""
        resource_reqs = app_spec.get("resource_requirements", {})
        
        # Memory limits
        memory_limit = resource_reqs.get("memory", self.config.get("default_memory_limit", "512m"))
        memory_swap = resource_reqs.get("memory_swap", memory_limit)  # No additional swap
        
        # CPU limits
        cpu_limit = resource_reqs.get("cpu", self.config.get("default_cpu_limit", "1.0"))
        cpu_quota = int(float(cpu_limit) * 100000)  # Convert to Docker format
        
        # Disk limits
        storage_limit = resource_reqs.get("storage", "1G")
        
        return {
            "mem_limit": memory_limit,
            "memswap_limit": memory_swap,
            "cpu_quota": cpu_quota,
            "cpu_period": 100000,
            "storage_opt": {"size": storage_limit},
            "pids_limit": resource_reqs.get("max_processes", 100)
        }
    
    def get_network_config(self, app_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Get network configuration with security restrictions"""
        network_config = app_spec.get("network_config", {})
        
        config = {
            "network_mode": "bridge",  # Isolated network
            "dns": ["8.8.8.8", "8.8.4.4"],  # Controlled DNS
            "network_disabled": False
        }
        
        # Port mappings with restrictions
        if network_config.get("ports"):
            allowed_ports = self._filter_allowed_ports(network_config["ports"])
            if allowed_ports:
                config["ports"] = allowed_ports
        
        # Network isolation
        if self.security_config.get("network_isolation", True):
            config["network_mode"] = "none"  # No network access by default
        
        return config
    
    def _filter_allowed_ports(self, requested_ports: Dict[str, Any]) -> Dict[str, Any]:
        """Filter and validate requested port mappings"""
        allowed_ports = {}
        port_range = self.config.get("networking", {}).get("internal_port_range", [10000, 20000])
        
        for container_port, host_config in requested_ports.items():
            try:
                port_num = int(container_port)
                if port_range[0] <= port_num <= port_range[1]:
                    allowed_ports[container_port] = host_config
                else:
                    logger.warning(f"Port {port_num} outside allowed range {port_range}")
            except ValueError:
                logger.warning(f"Invalid port specification: {container_port}")
        
        return allowed_ports
    
    def validate_app_spec(self, app_spec: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate app specification against security policies"""
        errors = []
        
        # Check resource requirements
        resource_reqs = app_spec.get("resource_requirements", {})
        
        # Memory limits
        memory = resource_reqs.get("memory", "512m")
        if self._parse_memory_size(memory) > self._parse_memory_size("2G"):
            errors.append("Memory request exceeds maximum allowed (2G)")
        
        # CPU limits  
        cpu = float(resource_reqs.get("cpu", "1.0"))
        if cpu > 4.0:
            errors.append("CPU request exceeds maximum allowed (4.0)")
        
        # Storage limits
        storage = resource_reqs.get("storage", "1G")
        max_storage = self.config.get("storage", {}).get("max_storage_per_app", "10G")
        if self._parse_memory_size(storage) > self._parse_memory_size(max_storage):
            errors.append(f"Storage request exceeds maximum allowed ({max_storage})")
        
        # Container image validation
        if app_spec.get("image"):
            if not self._validate_container_image(app_spec["image"]):
                errors.append("Container image not from allowed registry")
        
        # Build config validation
        if app_spec.get("build_config"):
            build_errors = self._validate_build_config(app_spec["build_config"])
            errors.extend(build_errors)
        
        return len(errors) == 0, errors
    
    def _parse_memory_size(self, size_str: str) -> int:
        """Parse memory size string to bytes"""
        size_str = size_str.upper()
        multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        
        if size_str[-1] in multipliers:
            return int(size_str[:-1]) * multipliers[size_str[-1]]
        else:
            return int(size_str)
    
    def _validate_container_image(self, image: str) -> bool:
        """Validate if container image is from allowed registry"""
        allowed_registries = self.security_config.get("allowed_registries", ["docker.io"])
        
        # Check if image is from allowed registry
        for registry in allowed_registries:
            if image.startswith(registry) or "/" not in image:  # Docker Hub shorthand
                return True
        
        return False
    
    def _validate_build_config(self, build_config: Dict[str, Any]) -> List[str]:
        """Validate build configuration"""
        errors = []
        
        # Check build timeout
        build_timeout = build_config.get("timeout", 600)
        max_timeout = self.security_config.get("max_build_time", 1800)
        if build_timeout > max_timeout:
            errors.append(f"Build timeout exceeds maximum ({max_timeout}s)")
        
        # Check runtime
        runtime = build_config.get("runtime", "python")
        allowed_runtimes = ["python", "node", "go", "rust", "java"]
        if runtime not in allowed_runtimes:
            errors.append(f"Runtime '{runtime}' not allowed")
        
        return errors
    
    def create_app_user(self, app_id: str) -> Dict[str, Any]:
        """Create a dedicated user for the app (Linux only)"""
        try:
            username = f"voxaapp-{app_id[:8]}"
            uid = 2000 + hash(app_id) % 1000  # UID range 2000-2999
            
            # Check if user already exists
            try:
                subprocess.run(["id", username], check=True, capture_output=True)
                logger.info(f"User {username} already exists")
            except subprocess.CalledProcessError:
                # Create user
                subprocess.run([
                    "useradd",
                    "--system",
                    "--no-create-home",
                    "--shell", "/bin/false",
                    "--uid", str(uid),
                    username
                ], check=True)
                logger.info(f"Created user {username} with UID {uid}")
            
            return {"username": username, "uid": uid, "gid": uid}
            
        except Exception as e:
            logger.warning(f"Failed to create app user: {e}")
            return {"username": "nobody", "uid": 65534, "gid": 65534}
    
    def setup_app_filesystem(self, app_id: str, instance_id: str) -> Path:
        """Set up isolated filesystem for the app"""
        try:
            # Create app directory structure
            app_data_dir = Path(self.config.get("app_data_dir", "data/apps"))
            app_dir = app_data_dir / app_id / instance_id
            
            # Create directories
            directories = ["data", "tmp", "logs", "config"]
            for dir_name in directories:
                (app_dir / dir_name).mkdir(parents=True, exist_ok=True)
            
            # Set permissions (Linux only)
            if os.name == "posix":
                os.chmod(app_dir, 0o750)
                for dir_name in directories:
                    os.chmod(app_dir / dir_name, 0o750)
            
            return app_dir
            
        except Exception as e:
            logger.error(f"Failed to set up app filesystem: {e}")
            raise
    
    def cleanup_app_resources(self, app_id: str, instance_id: str):
        """Clean up app resources after stopping"""
        try:
            # Remove filesystem
            app_data_dir = Path(self.config.get("app_data_dir", "data/apps"))
            app_dir = app_data_dir / app_id / instance_id
            
            if app_dir.exists():
                import shutil
                shutil.rmtree(app_dir)
                logger.info(f"Cleaned up filesystem for {instance_id}")
            
            # Remove user (optional - might want to keep for auditing)
            retention_days = self.config.get("storage", {}).get("retention_days", 7)
            if retention_days == 0:
                username = f"voxaapp-{app_id[:8]}"
                try:
                    subprocess.run(["userdel", username], check=True, capture_output=True)
                    logger.info(f"Removed user {username}")
                except subprocess.CalledProcessError:
                    pass  # User might not exist or be in use
            
        except Exception as e:
            logger.error(f"Failed to cleanup app resources: {e}")


class AppSecurityMonitor:
    """
    Monitors running applications for security violations.
    """
    
    def __init__(self):
        self.config = read_json_from_namespace("config.apps") or {}
        self.security_config = self.config.get("security", {})
        
    async def monitor_app_security(self, instance_id: str, container_id: str):
        """Monitor an app instance for security violations"""
        import asyncio
        
        while True:
            try:
                # Check resource usage
                await self._check_resource_usage(instance_id, container_id)
                
                # Check network activity
                await self._check_network_activity(instance_id, container_id)
                
                # Check filesystem access
                await self._check_filesystem_access(instance_id, container_id)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Security monitoring error for {instance_id}: {e}")
                await asyncio.sleep(60)  # Back off on errors
    
    async def _check_resource_usage(self, instance_id: str, container_id: str):
        """Check if app is exceeding resource limits"""
        # This would integrate with your existing container stats monitoring
        pass
    
    async def _check_network_activity(self, instance_id: str, container_id: str):
        """Monitor network activity for suspicious behavior"""
        # This would monitor network connections and traffic
        pass
    
    async def _check_filesystem_access(self, instance_id: str, container_id: str):
        """Monitor filesystem access patterns"""
        # This would monitor file access patterns for anomalies
        pass


# Global instances
_app_sandbox: AppSandbox = None
_security_monitor: AppSecurityMonitor = None

def get_app_sandbox() -> AppSandbox:
    """Get the global app sandbox instance"""
    global _app_sandbox
    if _app_sandbox is None:
        _app_sandbox = AppSandbox()
    return _app_sandbox

def get_security_monitor() -> AppSecurityMonitor:
    """Get the global security monitor instance"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = AppSecurityMonitor()
    return _security_monitor
