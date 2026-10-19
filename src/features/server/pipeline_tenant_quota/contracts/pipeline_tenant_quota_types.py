"""
Blueprint:
- Tenant quota contracts and DTOs.
"""
from pydantic import BaseModel, Field

class TenantQuotaInputDTO(BaseModel):
    tenant_id: str
    tokens: int = Field(default=500)
    refill_rate: float = Field(default=50.0)

class TenantQuotaOutputDTO(BaseModel):
    allowed: bool
    status_code: int = 200
    retry_after_seconds: int = Field(default=0)
