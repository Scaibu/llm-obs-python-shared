"""
Blueprint:
- RFC 9457 Problem Details envelope generation rules.
- Translates pipeline rejection reasons and HTTP status codes into standardized RFC 9457 error contracts.
- Injects standard instance URNs (urn:request:<request_id>), retryable indicators, and optional retry counters.
"""
from typing import Any, Dict, Optional
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails
from src.features.server.composable_pipeline.contracts.pipeline_constants import (
    PipelineRejectionReasons,
    ProblemTypeSlugs,
)


class ProblemDetailsRules:
    """
    Blueprint:
    - Provides standardized factory methods for creating RFC 9457 compliant error responses.
    """

    DEFAULT_PROBLEM_BASE: str = "https://errors.example.com/problems/"

    REJECTION_TYPE_MAP: Dict[str, str] = {
        PipelineRejectionReasons.ADMISSION: ProblemTypeSlugs.OVERLOADED,
        PipelineRejectionReasons.PRIORITY_SHED: ProblemTypeSlugs.OVERLOADED,
        PipelineRejectionReasons.PRIORITY_SHEDDING: ProblemTypeSlugs.OVERLOADED,
        PipelineRejectionReasons.ROUTE_NOT_FOUND: ProblemTypeSlugs.NOT_FOUND,
        PipelineRejectionReasons.METHOD_NOT_ALLOWED: ProblemTypeSlugs.METHOD_NOT_ALLOWED,
        PipelineRejectionReasons.PATH_NONCANONICAL: ProblemTypeSlugs.INVALID_PATH,
        PipelineRejectionReasons.BODY_TOO_LARGE: ProblemTypeSlugs.PAYLOAD_TOO_LARGE,
        PipelineRejectionReasons.UNSUPPORTED_MEDIA_TYPE: ProblemTypeSlugs.UNSUPPORTED_MEDIA_TYPE,
        PipelineRejectionReasons.DECOMPRESSION_LIMIT: ProblemTypeSlugs.PAYLOAD_TOO_LARGE,
        PipelineRejectionReasons.HEADERS_TOO_LARGE: ProblemTypeSlugs.HEADERS_TOO_LARGE,
        PipelineRejectionReasons.VALIDATION_FAILED: ProblemTypeSlugs.VALIDATION_FAILED,
        PipelineRejectionReasons.RATE_LIMIT: ProblemTypeSlugs.RATE_LIMITED,
        PipelineRejectionReasons.QUOTA: ProblemTypeSlugs.QUOTA_EXCEEDED,
        PipelineRejectionReasons.AUTH: ProblemTypeSlugs.UNAUTHENTICATED,
        PipelineRejectionReasons.AUTHENTICATION: ProblemTypeSlugs.UNAUTHENTICATED,
        PipelineRejectionReasons.AUTHZ: ProblemTypeSlugs.FORBIDDEN,
        PipelineRejectionReasons.AUTHORIZATION: ProblemTypeSlugs.FORBIDDEN,
        PipelineRejectionReasons.DEADLINE_UNVIABLE: ProblemTypeSlugs.DEADLINE_UNVIABLE,
        PipelineRejectionReasons.IDEMPOTENCY_KEY_MISSING: ProblemTypeSlugs.IDEMPOTENCY_KEY_MISSING,
        PipelineRejectionReasons.IDEMPOTENCY_CONFLICT: ProblemTypeSlugs.IDEMPOTENCY_CONFLICT,
        PipelineRejectionReasons.IDEMPOTENCY_KEY_MISMATCH: ProblemTypeSlugs.IDEMPOTENCY_KEY_MISMATCH,
        PipelineRejectionReasons.ROUTE_DISABLED: ProblemTypeSlugs.ROUTE_DISABLED,
        PipelineRejectionReasons.UPSTREAM_UNAVAILABLE: ProblemTypeSlugs.UPSTREAM_UNAVAILABLE,
        PipelineRejectionReasons.UPSTREAM_TIMEOUT: ProblemTypeSlugs.UPSTREAM_TIMEOUT,
        PipelineRejectionReasons.INTERNAL_ERROR: ProblemTypeSlugs.INTERNAL_ERROR,
        PipelineRejectionReasons.TOO_EARLY: ProblemTypeSlugs.TOO_EARLY,
    }

    TYPE_TITLES: Dict[str, str] = {
        ProblemTypeSlugs.OVERLOADED: "Service overloaded",
        ProblemTypeSlugs.ROUTE_DISABLED: "Operation temporarily disabled",
        ProblemTypeSlugs.NOT_FOUND: "Resource not found",
        ProblemTypeSlugs.METHOD_NOT_ALLOWED: "Method not allowed",
        ProblemTypeSlugs.INVALID_PATH: "Invalid request path",
        ProblemTypeSlugs.PAYLOAD_TOO_LARGE: "Request body too large",
        ProblemTypeSlugs.HEADERS_TOO_LARGE: "Request headers too large",
        ProblemTypeSlugs.UNSUPPORTED_MEDIA_TYPE: "Unsupported media type",
        ProblemTypeSlugs.VALIDATION_FAILED: "Request does not match contract",
        ProblemTypeSlugs.RATE_LIMITED: "Too many requests",
        ProblemTypeSlugs.QUOTA_EXCEEDED: "Quota exceeded",
        ProblemTypeSlugs.UNAUTHENTICATED: "Authentication required",
        ProblemTypeSlugs.FORBIDDEN: "Insufficient permissions",
        ProblemTypeSlugs.DEADLINE_UNVIABLE: "Deadline too short to process",
        ProblemTypeSlugs.IDEMPOTENCY_KEY_MISSING: "Idempotency key required",
        ProblemTypeSlugs.IDEMPOTENCY_CONFLICT: "Request with this key in progress",
        ProblemTypeSlugs.IDEMPOTENCY_KEY_MISMATCH: "Idempotency key reused with a different request",
        ProblemTypeSlugs.UPSTREAM_UNAVAILABLE: "Dependency unavailable",
        ProblemTypeSlugs.UPSTREAM_TIMEOUT: "Dependency timed out",
        ProblemTypeSlugs.INTERNAL_ERROR: "Internal error",
        ProblemTypeSlugs.TOO_EARLY: "Request sent too early",
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
        ProblemTypeSlugs.OVERLOADED,
        ProblemTypeSlugs.RATE_LIMITED,
        ProblemTypeSlugs.QUOTA_EXCEEDED,
        ProblemTypeSlugs.IDEMPOTENCY_CONFLICT,
        ProblemTypeSlugs.UPSTREAM_UNAVAILABLE,
        ProblemTypeSlugs.TOO_EARLY,
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
