"""
Blueprint:
- Pure predicate rules evaluating path canonicalization and mutation eligibility invariants.
- Conforms to Rule 06 (Writing Conditions):
  - Named predicates with explicit types (C7, C10)
  - Pure deterministic functions (C20)
  - Explicit canonical forms and totality (C2, C8, C27)
"""
from typing import Final, Set

INVALID_PATH_SUBSTRINGS: Final[Set[str]] = {
    "//",
    "/../",
    "/./",
    "%2f",
    "%5c",
}

MUTATING_HTTP_METHODS: Final[Set[str]] = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


class PathCanonicalizationRules:
    @staticmethod
    def is_canonical_path(path: str) -> bool:
        if not path:
            return False
        normalized = path.lower()
        if normalized.endswith("/.."):
            return False
        for token in INVALID_PATH_SUBSTRINGS:
            if token in normalized:
                return False
        return True


class RequestMutationRules:
    @staticmethod
    def is_mutating_method(method: str) -> bool:
        if not method:
            return False
        return method.upper() in MUTATING_HTTP_METHODS
