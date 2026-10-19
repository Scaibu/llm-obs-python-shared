"""
Blueprint:
- Route limits types and DTOs.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class RouteLimitsConfig(BaseModel):
    max_body_bytes: int = Field(default=10 * 1024 * 1024)
    max_header_bytes: int = Field(default=32 * 1024)
    allowed_media_types: List[str] = Field(default_factory=lambda: ["application/json"])

class RouteLimitsInputDTO(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict)
    limits: RouteLimitsConfig = Field(default_factory=RouteLimitsConfig)

class RouteLimitsOutputDTO(BaseModel):
    passed: bool
    status_code: int = 200
    rejection_reason: Optional[str] = None
