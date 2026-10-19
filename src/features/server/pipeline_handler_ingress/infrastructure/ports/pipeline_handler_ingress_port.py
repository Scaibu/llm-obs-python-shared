"""
Blueprint:
- Port for domain service dispatch.
"""
from typing import Any, Protocol

class DomainDispatcherPort(Protocol):
    async def dispatch(self, handler_name: str, payload: Any) -> Any: ...
