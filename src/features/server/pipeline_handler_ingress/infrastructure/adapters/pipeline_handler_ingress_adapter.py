"""
Blueprint:
- In-memory domain dispatcher adapter.
"""
from typing import Any
from src.features.server.pipeline_handler_ingress.infrastructure.ports.pipeline_handler_ingress_port import DomainDispatcherPort

class InMemoryDomainDispatcherAdapter(DomainDispatcherPort):
    async def dispatch(self, handler_name: str, payload: Any) -> Any:
        return {"status": "success", "handler": handler_name, "data": payload}
