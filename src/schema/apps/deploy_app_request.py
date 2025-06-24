from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class DeployAppRequest(BaseModel):
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version") 
    image: Optional[str] = Field(None, description="Docker image (for container deployment)")
    source_code_hash: Optional[str] = Field(None, description="Source code hash (for source deployment)")
    build_config: Optional[Dict[str, Any]] = Field(None, description="Build configuration")
    runtime_config: Dict[str, Any] = Field(default_factory=dict, description="Runtime configuration")
    resource_requirements: Optional[Dict[str, Any]] = Field(None, description="Resource requirements")
    network_config: Optional[Dict[str, Any]] = Field(None, description="Network configuration")
    replicas: int = Field(1, description="Number of replicas to deploy")
    target_nodes: Optional[list[str]] = Field(None, description="Specific nodes to deploy to")