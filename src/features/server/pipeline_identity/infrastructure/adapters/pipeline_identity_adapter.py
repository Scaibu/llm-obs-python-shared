"""
Blueprint:
- Concrete adapter implementing IdentityPort.
- Generates RFC-compliant UUID identifiers and W3C traceparent tokens.
"""
import uuid
import os
from src.features.server.pipeline_identity.infrastructure.ports.pipeline_identity_port import IdentityPort

class StandardIdentityAdapter(IdentityPort):
    def generate_request_id(self) -> str:
        return str(uuid.uuid4())

    def generate_traceparent(self) -> str:
        trace_id = os.urandom(16).hex()
        span_id = os.urandom(8).hex()
        return f"00-{trace_id}-{span_id}-01"
