"""
Blueprint:
- Contracts and DTOs for admission_control pipeline step.
"""
from pydantic import BaseModel, Field

class AdmissionControlInputDTO(BaseModel):
    pass

class AdmissionControlOutputDTO(BaseModel):
    admitted: bool = Field(default=True)
    active_count: int = Field(default=0)
