"""
Blueprint:
- Contracts and DTOs for ssrf_validation pipeline step.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class SsrfValidationInputDTO(BaseModel):
    url: str
    allowed_hosts: Optional[List[str]] = Field(default=None)

class SsrfValidationOutputDTO(BaseModel):
    valid: bool
    hostname: Optional[str] = None
