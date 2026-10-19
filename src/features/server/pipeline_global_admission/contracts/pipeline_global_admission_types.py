"""
Blueprint:
- Global admission contracts and DTOs.
"""
from pydantic import BaseModel, Field

class AdmissionInputDTO(BaseModel):
    max_concurrency: int = Field(default=1000)

class AdmissionOutputDTO(BaseModel):
    allowed: bool
    current_inflight: int
    retry_after_seconds: int = Field(default=0)
