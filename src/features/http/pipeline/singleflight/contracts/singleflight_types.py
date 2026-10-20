"""
Blueprint:
- Contracts and DTOs for singleflight pipeline step.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

class SingleflightInputDTO(BaseModel):
    tenant_id: str
    method: str
    url: str
    body: Optional[Any] = Field(default=None)
    cancel_previous: bool = Field(default=False)

class SingleflightOutputDTO(BaseModel):
    hashed_request_key: str
    singleflight_hit: bool
