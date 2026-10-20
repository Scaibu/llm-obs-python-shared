"""
Blueprint:
- Contracts and DTOs for circuit_breaker pipeline step.
"""
from pydantic import BaseModel, Field

class CircuitBreakerInputDTO(BaseModel):
    tenant_id: str
    url: str

class CircuitBreakerOutputDTO(BaseModel):
    circuit_key: str
    allowed: bool = Field(default=True)
