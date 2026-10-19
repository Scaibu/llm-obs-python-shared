"""
Blueprint:
- Priority admission types and DTOs.
"""
from enum import Enum
from pydantic import BaseModel, Field

class RequestPriorityClass(str, Enum):
    INTERACTIVE = "interactive"
    BACKGROUND = "background"
    BATCH = "batch"

class PriorityAdmissionInputDTO(BaseModel):
    priority_class: RequestPriorityClass = RequestPriorityClass.INTERACTIVE
    system_load_ratio: float = Field(default=0.0)

class PriorityAdmissionOutputDTO(BaseModel):
    admitted: bool
    status_code: int = 200
    retry_after_seconds: int = Field(default=0)
