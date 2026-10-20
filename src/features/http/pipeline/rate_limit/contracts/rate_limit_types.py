"""
Blueprint:
- Contracts and DTOs for rate_limit pipeline step.
"""
from pydantic import BaseModel, Field

class RateLimitInputDTO(BaseModel):
    tenant_id: str

class RateLimitOutputDTO(BaseModel):
    allowed: bool = Field(default=True)
    tenant_id: str
