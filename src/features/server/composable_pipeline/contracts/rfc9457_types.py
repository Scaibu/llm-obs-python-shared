"""
Blueprint:
- RFC 9457 Problem Details standard error payload model.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ProblemDetails(BaseModel):
    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    request_id: Optional[str] = None
    retryable: bool = False
    retry_after_seconds: Optional[int] = None
    extensions: Dict[str, Any] = Field(default_factory=dict)
