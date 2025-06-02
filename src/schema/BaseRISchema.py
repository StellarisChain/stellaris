from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
import re

class BaseRISchema(BaseModel):
    routing_info: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = {}