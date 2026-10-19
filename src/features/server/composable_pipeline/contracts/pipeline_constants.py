"""
Blueprint:
- Centralized constants contract defining HTTP headers, rejection reasons, Problem Details URIs, and stage identifiers.
- Eliminates hardcoded magic strings across composable_pipeline stages, services, rules, and adapters.
"""
from typing import Final


class PipelineHeaders:
    REQUEST_ID: Final[str] = "x-request-id"
    TRACEPARENT: Final[str] = "traceparent"
    X_FORWARDED_FOR: Final[str] = "x-forwarded-for"
    IDEMPOTENCY_KEY: Final[str] = "idempotency-key"
    AUTHORIZATION: Final[str] = "authorization"
    CONTENT_TYPE: Final[str] = "content-type"
    CONTENT_LENGTH: Final[str] = "content-length"
    ALLOW: Final[str] = "allow"
    RETRY_AFTER: Final[str] = "retry-after"
    WWW_AUTHENTICATE: Final[str] = "www-authenticate"


class PipelineRejectionReasons:
    ADMISSION: Final[str] = "admission"
    PRIORITY_SHED: Final[str] = "priority_shed"
    PRIORITY_SHEDDING: Final[str] = "priority_shedding"
    ROUTE_NOT_FOUND: Final[str] = "route_not_found"
    METHOD_NOT_ALLOWED: Final[str] = "method_not_allowed"
    PATH_NONCANONICAL: Final[str] = "path_noncanonical"
    BODY_TOO_LARGE: Final[str] = "body_too_large"
    UNSUPPORTED_MEDIA_TYPE: Final[str] = "unsupported_media_type"
    DECOMPRESSION_LIMIT: Final[str] = "decompression_limit"
    HEADERS_TOO_LARGE: Final[str] = "headers_too_large"
    VALIDATION_FAILED: Final[str] = "validation_failed"
    RATE_LIMIT: Final[str] = "rate_limit"
    QUOTA: Final[str] = "quota"
    AUTH: Final[str] = "auth"
    AUTHENTICATION: Final[str] = "authentication"
    AUTHZ: Final[str] = "authz"
    AUTHORIZATION: Final[str] = "authorization"
    DEADLINE_UNVIABLE: Final[str] = "deadline_unviable"
    IDEMPOTENCY_KEY_MISSING: Final[str] = "idempotency_key_missing"
    IDEMPOTENCY_CONFLICT: Final[str] = "idempotency_conflict"
    IDEMPOTENCY_KEY_MISMATCH: Final[str] = "idempotency_key_mismatch"
    ROUTE_DISABLED: Final[str] = "route_disabled"
    UPSTREAM_UNAVAILABLE: Final[str] = "upstream_unavailable"
    UPSTREAM_TIMEOUT: Final[str] = "upstream_timeout"
    INTERNAL_ERROR: Final[str] = "internal_error"
    TOO_EARLY: Final[str] = "too_early"


class ProblemTypeSlugs:
    OVERLOADED: Final[str] = "overloaded"
    ROUTE_DISABLED: Final[str] = "route-disabled"
    NOT_FOUND: Final[str] = "not-found"
    METHOD_NOT_ALLOWED: Final[str] = "method-not-allowed"
    INVALID_PATH: Final[str] = "invalid-path"
    PAYLOAD_TOO_LARGE: Final[str] = "payload-too-large"
    HEADERS_TOO_LARGE: Final[str] = "headers-too-large"
    UNSUPPORTED_MEDIA_TYPE: Final[str] = "unsupported-media-type"
    VALIDATION_FAILED: Final[str] = "validation-failed"
    RATE_LIMITED: Final[str] = "rate-limited"
    QUOTA_EXCEEDED: Final[str] = "quota-exceeded"
    UNAUTHENTICATED: Final[str] = "unauthenticated"
    FORBIDDEN: Final[str] = "forbidden"
    DEADLINE_UNVIABLE: Final[str] = "deadline-unviable"
    IDEMPOTENCY_KEY_MISSING: Final[str] = "idempotency-key-missing"
    IDEMPOTENCY_CONFLICT: Final[str] = "idempotency-conflict"
    IDEMPOTENCY_KEY_MISMATCH: Final[str] = "idempotency-key-mismatch"
    UPSTREAM_UNAVAILABLE: Final[str] = "upstream-unavailable"
    UPSTREAM_TIMEOUT: Final[str] = "upstream-timeout"
    INTERNAL_ERROR: Final[str] = "internal-error"
    TOO_EARLY: Final[str] = "too-early"


class PipelineMediaTypes:
    JSON: Final[str] = "application/json"
    PROBLEM_JSON: Final[str] = "application/problem+json"
