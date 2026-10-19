"""
Blueprint:
- RFC 9457 Problem Details envelope generation rules.
- Translates pipeline rejection reasons and HTTP status codes into standardized RFC 9457 error contracts.
- Injects standard instance URNs (urn:request:<request_id>), retryable indicators, and optional retry counters.
"""
from typing import Any, Dict, Optional
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails


class ProblemDetailsRules:
    """
    Blueprint:
    - Provides standardized factory methods for creating RFC 9457 compliant error responses.
    """

    DEFAULT_PROBLEM_BASE: str = "https://errors.example.com/problems/"

    REJECTION_TYPE_MAP: Dict[str, str] = {
        "admission": "overloaded",
        "priority_shed": "overloaded",
        "priority_shedding": "overloaded",
        "route_not_found": "not-found",
        "method_not_allowed": "method-not-allowed",
        "path_noncanonical": "invalid-path",
        "body_too_large": "payload-too-large",
        "unsupported_media_type": "unsupported-media-type",
        "decompression_limit": "payload-too-large",
        "headers_too_large": "headers-too-large",
        "validation_failed": "validation-failed",
        "rate_limit": "rate-limited",
        "quota": "quota-exceeded",
        "auth": "unauthenticated",
        "authentication": "unauthenticated",
        "authz": "forbidden",
        "authorization": "forbidden",
        "deadline_unviable": "deadline-unviable",
        "idempotency_key_missing": "idempotency-key-missing",
        "idempotency_conflict": "idempotency-conflict",
        "idempotency_key_mismatch": "idempotency-key-mismatch",
        "route_disabled": "route-disabled",
        "upstream_unavailable": "upstream-unavailable",
        "upstream_timeout": "upstream-timeout",
        "internal_error": "internal-error",
        "too_early": "too-early",
    }

    TYPE_TITLES: Dict[str, str] = {
        "overloaded": "Service overloaded",
        "route-disabled": "Operation temporarily disabled",
        "not-found": "Resource not found",
        "method-not-allowed": "Method not allowed",
        "invalid-path": "Invalid request path",
        "payload-too-large": "Request body too large",
        "headers-too-large": "Request headers too large",
        "unsupported-media-type": "Unsupported media type",
        "validation-failed": "Request does not match contract",
        "rate-limited": "Too many requests",
        "quota-exceeded": "Quota exceeded",
        "unauthenticated": "Authentication required",
        "forbidden": "Insufficient permissions",
        "deadline-unviable": "Deadline too short to process",
        "idempotency-key-missing": "Idempotency key required",
        "idempotency-conflict": "Request with this key in progress",
        "idempotency-key-mismatch": "Idempotency key reused with a different request",
        "upstream-unavailable": "Dependency unavailable",
        "upstream-timeout": "Dependency timed out",
        "internal-error": "Internal error",
        "too-early": "Request sent too early",
    }

    STATUS_TITLES: Dict[int, str] = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        413: "Payload Too Large",
        415: "Unsupported Media Type",
        422: "Unprocessable Content",
        425: "Too Early",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        500: "Internal Server Error",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    RETRYABLE_TYPES: set = {
        "overloaded",
        "rate-limited",
        "quota-exceeded",
        "idempotency-conflict",
        "upstream-unavailable",
        "too-early",
    }

    @classmethod
    def resolve_type_slug(cls, reason_or_type: str) -> str:
        return cls.REJECTION_TYPE_MAP.get(reason_or_type, reason_or_type)

    @classmethod
    def create_problem(
        cls,
        status: int,
        detail: str,
        instance: str,
        error_type: Optional[str] = None,
        reason: Optional[str] = None,
        base_url: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> ProblemDetails:
        base = base_url or cls.DEFAULT_PROBLEM_BASE
        if not base.endswith("/"):
            base += "/"
        type_slug = cls.resolve_type_slug(reason or "") if reason else None
        if error_type is not None:
            full_type = error_type
            title = cls.STATUS_TITLES.get(status, "HTTP Error")
            slug_for_retry = error_type.split("/")[-1]
        elif type_slug is not None:
            full_type = f"{base}{type_slug}"
            title = cls.TYPE_TITLES.get(type_slug, cls.STATUS_TITLES.get(status, "HTTP Error"))
            slug_for_retry = type_slug
        else:
            full_type = f"{base}{status}"
            title = cls.STATUS_TITLES.get(status, "HTTP Error")
            slug_for_retry = str(status)

        request_id = instance.replace("urn:request:", "") if instance.startswith("urn:request:") else instance
        formatted_instance = instance if instance.startswith("urn:") else f"urn:request:{instance}"
        is_retryable = slug_for_retry in cls.RETRYABLE_TYPES

        return ProblemDetails(
            type=full_type,
            title=title,
            status=status,
            detail=detail,
            instance=formatted_instance,
            request_id=request_id,
            retryable=is_retryable,
            retry_after_seconds=retry_after_seconds,
            extensions=extensions or {},
        )
