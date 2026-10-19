"""
Blueprint:
- Handler ingress types and DTOs.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class HandlerIngressInputDTO(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    target_handler: str

class HandlerIngressOutputDTO(BaseModel):
    dispatched: bool
    status_code: int = 200
    sent_continue: bool = False
    response_body: Optional[Any] = None
