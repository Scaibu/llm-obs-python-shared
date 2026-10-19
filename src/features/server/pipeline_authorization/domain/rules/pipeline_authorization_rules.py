"""
Blueprint:
- Scope superset checking rules.
"""
from typing import Set

class AuthorizationRules:
    @staticmethod
    def is_authorized(principal_scopes: Set[str], required_scopes: Set[str]) -> bool:
        if not required_scopes:
            return True
        return required_scopes.issubset(principal_scopes)
