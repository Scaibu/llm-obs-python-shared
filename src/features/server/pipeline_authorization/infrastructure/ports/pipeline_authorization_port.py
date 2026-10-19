"""
Blueprint:
- Port for authorization policy configuration.
"""
from typing import Protocol, Set

class AuthzPolicyPort(Protocol):
    def get_route_scopes(self, route_name: str) -> Set[str]: ...
