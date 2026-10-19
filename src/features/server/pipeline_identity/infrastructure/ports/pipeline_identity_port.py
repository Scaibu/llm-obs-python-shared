"""
Blueprint:
- Abstract port interface for generating unique request identifiers and trace context.
"""
from typing import Protocol

class IdentityPort(Protocol):
    def generate_request_id(self) -> str: ...
    def generate_traceparent(self) -> str: ...
