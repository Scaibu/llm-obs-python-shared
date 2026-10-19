"""
Blueprint:
- Deadline computation contracts and DTOs.
"""
from typing import Optional
from pydantic import BaseModel, Field

class DeadlineInputDTO(BaseModel):
    client_timeout_ms: Optional[float] = None
    route_min_ms: float = Field(default=50.0)
    route_max_ms: float = Field(default=10000.0)
    safety_margin_ms: float = Field(default=50.0)

class DeadlineOutputDTO(BaseModel):
    valid: bool
    status_code: int = 200
    allocated_budget_ms: float = 0.0
