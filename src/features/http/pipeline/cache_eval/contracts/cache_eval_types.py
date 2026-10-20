"""
Blueprint:
- Contracts and DTOs for cache_eval pipeline step.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

class CacheEvalInputDTO(BaseModel):
    tenant_id: str
    method: str
    no_cache: bool = Field(default=False)
    hashed_request_key: Optional[str] = Field(default=None)

class CacheEvalOutputDTO(BaseModel):
    cleared: bool = Field(default=False)
    cached_response: Optional[Any] = Field(default=None)
