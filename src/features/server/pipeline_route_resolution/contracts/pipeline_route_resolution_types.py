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
    required_scopes: Set[str] = Field(default_factory=set)
    max_body_bytes: int = Field(default=10 * 1024 * 1024)
    allowed_media_types: List[str] = Field(default_factory=lambda: ["application/json"])

class RouteResolutionInputDTO(BaseModel):
    path: str
    method: str

class RouteResolutionOutputDTO(BaseModel):
    matched: bool
    status_code: int = 200
    route: Optional[RouteDefinition] = None
    allowed_methods: List[str] = Field(default_factory=list)
