"""
Blueprint:
- Constants contract for singleflight pipeline step.
"""
from typing import Final

class SingleflightConstants:
    STEP_NAME: Final[str] = "Singleflight"
    STEP_DESCRIPTION: Final[str] = "SHA-256 Concurrent Request Collapsing & Deduplication"
    METHOD_GET: Final[str] = "GET"
