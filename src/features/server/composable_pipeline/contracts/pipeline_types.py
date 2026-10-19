"""
Blueprint:
- Ingress request and response context across the 12 stages.
"""
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails
from src.features.server.pipeline_priority_admission.contracts.pipeline_priority_admission_types import (
    RequestPriorityClass,
)

class PayloadTooLargeError(Exception):
    """Raised by a streaming body reader when the body exceeds the route limit."""


class IngressRequest(BaseModel):
    method: str = "GET"
    path: str = "/"
    headers: Dict[str, str] = Field(default_factory=dict)
    remote_addr: str = "127.0.0.1"
    body: Optional[Any] = None
    priority_class: RequestPriorityClass = RequestPriorityClass.INTERACTIVE
    client_timeout_ms: Optional[float] = None

class PipelineRequestContext(BaseModel):
    request: IngressRequest
    current_stage_index: int = 0
    current_stage_name: str = "init"
    stage_execution_trail: List[str] = Field(default_factory=list)
    request_id: str = "unknown"
    trace_id: str = "unknown"
    resolved_peer_ip: str = "127.0.0.1"
    matched_route: Optional[str] = None
    principal: Optional[Any] = None
    principal_id: Optional[str] = None
    tenant_id: Optional[str] = None
    authenticated_scopes: Set[str] = Field(default_factory=set)
    allocated_deadline_ms: float = 0.0
    is_failed: bool = False
    rejection_reason: Optional[str] = None
    status_code: int = 200
    bytes_out: int = 0

class IngressResponse(BaseModel):
    status_code: int = 200
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    problem_details: Optional[ProblemDetails] = None
    context: Optional[PipelineRequestContext] = None
