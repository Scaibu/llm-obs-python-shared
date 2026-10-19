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
    ALLOW: Final[str] = "Allow"
    RETRY_AFTER: Final[str] = "Retry-After"
    WWW_AUTHENTICATE: Final[str] = "WWW-Authenticate"


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


class PipelineStageNames:
    INIT: Final[str] = "init"
    IDENTITY: Final[str] = "pipeline_identity"
    PEER_RESOLUTION: Final[str] = "pipeline_peer_resolution"
    GLOBAL_ADMISSION: Final[str] = "pipeline_global_admission"
    ROUTE_RESOLUTION: Final[str] = "pipeline_route_resolution"
    ROUTE_LIMITS: Final[str] = "pipeline_route_limits"
    PRE_AUTH_LIMIT: Final[str] = "pipeline_pre_auth_limit"
    AUTHENTICATION: Final[str] = "pipeline_authentication"
    AUTHORIZATION: Final[str] = "pipeline_authorization"
    TENANT_QUOTA: Final[str] = "pipeline_tenant_quota"
    DEADLINE: Final[str] = "pipeline_deadline"
    PRIORITY_ADMISSION: Final[str] = "pipeline_priority_admission"
    HANDLER_INGRESS: Final[str] = "pipeline_handler_ingress"


class PipelineStageTrails:
    STAGE_REQUEST_IDENTITY: Final[str] = "stage_request_identity"
    STAGE_PEER_RESOLUTION: Final[str] = "stage_peer_resolution"
    STAGE_GLOBAL_ADMISSION: Final[str] = "stage_global_admission"
    STAGE_ROUTE_RESOLUTION: Final[str] = "stage_route_resolution"
    STAGE_ROUTE_LIMITS: Final[str] = "stage_route_limits"
    STAGE_PRE_AUTH_LIMIT: Final[str] = "stage_pre_auth_limit"
    STAGE_AUTHENTICATION: Final[str] = "stage_authentication"
    STAGE_AUTHORIZATION: Final[str] = "stage_authorization"
    STAGE_TENANT_QUOTA: Final[str] = "stage_tenant_quota"
    STAGE_DEADLINE: Final[str] = "stage_deadline"
    STAGE_PRIORITY_ADMISSION: Final[str] = "stage_priority_admission"
    STAGE_HANDLER_INGRESS: Final[str] = "stage_handler_ingress"


class PipelineTenantConstants:
    DEFAULT_TENANT_ID: Final[str] = "default"
    ANONYMOUS_PRINCIPAL: Final[str] = "anonymous"


class PipelineProblemDetails:
    GLOBAL_CAPACITY_EXCEEDED: Final[str] = "Global capacity exceeded"
    PATH_NONCANONICAL_DETAIL: Final[str] = "Path is not canonical. Encoded slashes and dot-segments are rejected."
    ROUTE_NOT_FOUND_DETAIL: Final[str] = "Route matching failed"
    METHOD_NOT_ALLOWED_DETAIL: Final[str] = "Method not allowed for this route"
    INTERNAL_ROUTING_ERROR: Final[str] = "Internal routing error"
    ROUTE_DISABLED_DETAIL: Final[str] = "Route temporarily disabled by kill switch"
    IDEMPOTENCY_KEY_MISSING_DETAIL: Final[str] = "Idempotency-Key header is required for this route"
    IDEMPOTENCY_CONFLICT_DETAIL: Final[str] = "A request with this Idempotency-Key is currently in progress"
    ROUTE_LIMIT_VIOLATED: Final[str] = "Route limit violated"
    PEER_RATE_LIMIT_DETAIL: Final[str] = "Too many requests from peer IP"
    AUTH_REQUIRED_DETAIL: Final[str] = "Authentication required"
    INSUFFICIENT_SCOPES_DETAIL: Final[str] = "Insufficient scopes for route"
    TENANT_QUOTA_EXHAUSTED_DETAIL: Final[str] = "Tenant quota exhausted"
    DEADLINE_UNVIABLE_DETAIL: Final[str] = "Deadline expired or insufficient timeout budget"
    PRIORITY_SHEDDING_DETAIL: Final[str] = "Shedding low priority class"
    INTERNAL_SERVER_ERROR: Final[str] = "Internal Server Error"
