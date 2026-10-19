"""
Blueprint:
- Telemetry, metrics, and structured access log models adhering strictly to OpenTelemetry HTTP semantic conventions.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class AccessLogEntry(BaseModel):
    request_id: str
    trace_id: str
    route: str
    peer: str
    principal: Optional[str] = None
    status: int
    reason: Optional[str] = None
    duration_seconds: float
    bytes_in: int = 0
    bytes_out: int = 0

class PipelineMetricsRecord(BaseModel):
    duration_seconds: float
    active_requests: int
    rejection_reason: Optional[str] = None
