"""
Blueprint:
- Route resolution DTOs and contracts.
"""
from typing import List, Optional, Set
from pydantic import BaseModel, Field

class RouteDefinition(BaseModel):
    path_template: str
    allowed_methods: Set[str]
    handler_name: str

class RouteResolutionInputDTO(BaseModel):
    path: str
    method: str

class RouteResolutionOutputDTO(BaseModel):
    matched: bool
    status_code: int = 200
    route: Optional[RouteDefinition] = None
    allowed_methods: List[str] = Field(default_factory=list)
