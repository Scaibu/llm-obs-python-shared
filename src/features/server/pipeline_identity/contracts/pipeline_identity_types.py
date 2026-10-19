"""
Blueprint:
- Defines domain types and DTOs for request identity stage.
- Zero inline comments inside functions.
"""
from typing import Optional, Dict
from pydantic import BaseModel, Field

class IdentityInputDTO(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict)
    is_trusted_hop: bool = Field(default=False)

class IdentityOutputDTO(BaseModel):
    request_id: str
    traceparent: str
    is_propagated_trace: bool
