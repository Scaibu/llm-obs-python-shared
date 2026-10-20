"""
Blueprint:
- Contracts and DTOs for context_isolation pipeline step.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from src.features.http.pipeline.context_isolation.contracts.context_isolation_constants import (
    ContextIsolationConstants,
)

class ContextIsolationInputDTO(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = Field(default=None)
    max_body_size_bytes: int = Field(default=ContextIsolationConstants.DEFAULT_MAX_BODY_BYTES)

class ContextIsolationOutputDTO(BaseModel):
    tenant_id: str
    headers: Dict[str, str]
    body_size_bytes: int
