"""
Blueprint:
- Standard in-memory policy adapter.
"""
from typing import Dict, Optional, Set
from src.features.server.pipeline_authorization.infrastructure.ports.pipeline_authorization_port import AuthzPolicyPort

class InMemoryAuthzPolicyAdapter(AuthzPolicyPort):
    def __init__(self, route_scopes: Optional[Dict[str, Set[str]]] = None) -> None:
        self._route_scopes = route_scopes if route_scopes is not None else {}

    def get_route_scopes(self, route_name: str) -> Set[str]:
        return self._route_scopes.get(route_name, set())
