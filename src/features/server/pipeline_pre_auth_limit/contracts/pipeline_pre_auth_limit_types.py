"""
Blueprint:
- Pre-auth rate limit types and DTOs.
"""
from pydantic import BaseModel, Field

class PreAuthLimitInputDTO(BaseModel):
    client_ip: str
    max_tokens: int = Field(default=100)
    refill_rate_per_sec: float = Field(default=10.0)

class PreAuthLimitOutputDTO(BaseModel):
    allowed: bool
    status_code: int = 200
    retry_after_seconds: int = Field(default=0)
