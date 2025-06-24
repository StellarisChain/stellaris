from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class AppDeploymentResponse(BaseModel):
    success: bool
    app_id: str
    deployment_id: str
    message: str
    instances: list[Dict[str, Any]]
    successful: int
    failed: int
    total: int