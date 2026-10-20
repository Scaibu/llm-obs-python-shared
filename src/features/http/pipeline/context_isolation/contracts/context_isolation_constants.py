"""
Blueprint:
- Constants contract for context_isolation pipeline step.
"""
from typing import Final

class ContextIsolationConstants:
    STEP_NAME: Final[str] = "ContextIsolation"
    STEP_DESCRIPTION: Final[str] = "Request Context Isolation & Authenticated Tenant Guard"
    HEADER_X_TENANT_ID: Final[str] = "x-tenant-id"
    DEFAULT_MAX_BODY_BYTES: Final[int] = 10485760  # 10 MB
    ERROR_PAYLOAD_TOO_LARGE: Final[str] = (
        "Request payload size ({body_size_bytes} bytes) exceeds maximum limit of {max_body_bytes} bytes"
    )
    ERROR_SERIALIZATION_FAILED: Final[str] = (
        "Invalid request payload: unable to serialize body ({error})"
    )
    ERROR_MISSING_TENANT: Final[str] = "Unauthorized: Missing authenticated tenant identity in request context"
