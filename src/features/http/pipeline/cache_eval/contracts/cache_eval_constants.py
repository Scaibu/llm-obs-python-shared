"""
Blueprint:
- Constants contract for cache_eval pipeline step.
"""
from typing import Final, Tuple

class CacheEvalConstants:
    STEP_NAME: Final[str] = "CacheEval"
    STEP_DESCRIPTION: Final[str] = "Tenant Partitioned LRU Cache Lookup & Invalidation"
    METHOD_GET: Final[str] = "GET"
    METHOD_POST: Final[str] = "POST"
    METHOD_PUT: Final[str] = "PUT"
    METHOD_PATCH: Final[str] = "PATCH"
    METHOD_DELETE: Final[str] = "DELETE"
    MUTATING_METHODS: Final[Tuple[str, ...]] = (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    )
