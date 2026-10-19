"""
Blueprint:
- ComposablePipelineService strictly implementing:
  1. Outer Wrapper (Exception boundary, RFC 9457 envelope, metrics, structured access log)
  2. Strict 12-Stage Ingress Pipeline:
     - Stage 1: Request Identity (always generate request_id; sanitize W3C traceparent)
     - Stage 2: Peer Resolution (RTL proxy traversal)
     - Stage 3: Global Admission (Little's Law limit check with 503 + Retry-After)
     - Stage 4: Route Resolution (path & method check with 404 / 405 + Allow)
     - Stage 5: Per-Route Limits (413 body too large / 415 content type / 431 headers too large)
     - Stage 6: Pre-Auth Rate Limit (keyed by resolved peer IP; 429 + Retry-After)
     - Stage 7: Authentication (headers-only, zero body read; 401 + WWW-Authenticate)
     - Stage 8: Coarse Authorization (principal scopes vs route scopes; 403)
     - Stage 9: Per-Identity Quota (keyed by principal/tenant; 429 + Retry-After)
     - Stage 10: Deadline Computation (clamp budget = min(route.max, inherited - margin); 504)
     - Stage 11: Priority Admission (load shedding batch -> background -> interactive; 503)
     - Stage 12: Handler Ingress (100-continue, body streamed, domain dispatch)
"""
import json
import time
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional
from src.features.server.composable_pipeline.contracts.pipeline_types import (
    IngressRequest,
    IngressResponse,
    PayloadTooLargeError,
    PipelineRequestContext,
)
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails
from src.features.server.composable_pipeline.contracts.telemetry_types import AccessLogEntry, PipelineMetricsRecord
from src.features.server.composable_pipeline.contracts.pipeline_constants import (
    PipelineHeaders,
    PipelineRejectionReasons,
    PipelineStageNames,
    PipelineStageTrails,
    PipelineTenantConstants,
    PipelineProblemDetails,
)
from src.features.server.composable_pipeline.domain.rules.rfc9457_rules import ProblemDetailsRules
from src.features.server.composable_pipeline.domain.rules.response_factory_rules import (
    ResponseFactoryRules,
)
from src.features.server.composable_pipeline.domain.rules.path_canonicalization_rules import (
    PathCanonicalizationRules,
    RequestMutationRules,
)
from src.features.server.composable_pipeline.domain.rules.cors_csrf_rules import CorsAndCsrfRules
from src.python_shared.telemetry.tracer import trace_pipeline_stage
from src.features.server.pipeline_identity import PipelineIdentityService, StandardIdentityAdapter, IdentityInputDTO
from src.features.server.pipeline_peer_resolution import PipelinePeerResolutionService, StandardPeerConfigAdapter, PeerResolutionInputDTO
from src.features.server.pipeline_global_admission import PipelineGlobalAdmissionService, InMemoryAdmissionTrackerAdapter, AdmissionInputDTO
from src.features.server.pipeline_route_resolution import PipelineRouteResolutionService, InMemoryRouteCatalogAdapter, RouteResolutionInputDTO, RouteDefinition
from src.features.server.pipeline_route_limits import (
    PipelineRouteLimitsService,
    RouteLimitsConfig,
    RouteLimitsInputDTO,
)
from src.features.server.pipeline_pre_auth_limit import PipelinePreAuthLimitService, InMemoryPreAuthRateLimitAdapter, PreAuthLimitInputDTO
from src.features.server.pipeline_authentication import PipelineAuthenticationService, StandardTokenVerifierAdapter, AuthInputDTO
from src.features.server.pipeline_authorization import PipelineAuthorizationService, AuthzInputDTO
from src.features.server.pipeline_tenant_quota import PipelineTenantQuotaService, InMemoryTenantQuotaAdapter, TenantQuotaInputDTO
from src.features.server.pipeline_deadline import PipelineDeadlineService, DeadlineInputDTO
from src.features.server.pipeline_priority_admission import PipelinePriorityAdmissionService, PriorityAdmissionInputDTO
from src.features.server.pipeline_handler_ingress import PipelineHandlerIngressService, InMemoryDomainDispatcherAdapter, HandlerIngressInputDTO

from src.features.server.server_configuration import ServerPolicySnapshot

logger = logging.getLogger("server.ingress.pipeline")

class ComposablePipelineService:
    def __init__(
        self,
        routes: Optional[List[RouteDefinition]] = None,
        policy: Optional[ServerPolicySnapshot] = None,
        config_path: Optional[str] = None,
        idempotency_store: Optional[Any] = None,
        quota_port: Optional[Any] = None,
    ) -> None:
        import os
        import yaml  # type: ignore[import-untyped]
        cfg_file = config_path or os.path.join(os.path.dirname(__file__), "../config.yml")
        unified_cfg: Dict[str, Any] = {}
        if os.path.exists(cfg_file):
            with open(cfg_file, "r") as f:
                unified_cfg = yaml.safe_load(f) or {}

        from src.features.server.composable_pipeline.domain.rules.pipeline_config_validation_rules import (
            PipelineConfigValidationRules,
        )

        validation_errors = PipelineConfigValidationRules.validate_configuration(unified_cfg)
        if validation_errors:
            for err in validation_errors:
                logger.warning("Pipeline configuration validation warning: %s", err)

        self.policy = policy if policy is not None else ServerPolicySnapshot()
        self.stage_identity = PipelineIdentityService(port=StandardIdentityAdapter())

        peer_cfg = unified_cfg.get("peer_resolution", {})
        trusted_proxies = peer_cfg.get("trusted_proxies", self.policy.server.trusted_proxies)
        self.stage_peer = PipelinePeerResolutionService(
            config_port=StandardPeerConfigAdapter(proxies=trusted_proxies)
        )

        self.stage_admission = PipelineGlobalAdmissionService(tracker=InMemoryAdmissionTrackerAdapter())
        self.stage_route = PipelineRouteResolutionService(catalog=InMemoryRouteCatalogAdapter(routes=routes))
        self.stage_limits = PipelineRouteLimitsService()
        self.stage_pre_auth = PipelinePreAuthLimitService(limiter=InMemoryPreAuthRateLimitAdapter())
        self.stage_auth = PipelineAuthenticationService(verifier=StandardTokenVerifierAdapter())
        self.stage_authz = PipelineAuthorizationService()

        from src.features.server.composable_pipeline.infrastructure.adapters.in_memory_idempotency_store_adapter import (
            InMemoryIdempotencyStoreAdapter,
        )
        self.idempotency_store = idempotency_store if idempotency_store is not None else InMemoryIdempotencyStoreAdapter()

        tenant_port = quota_port if quota_port is not None else InMemoryTenantQuotaAdapter()
        self.stage_quota = PipelineTenantQuotaService(quota_port=tenant_port)
        self.stage_deadline = PipelineDeadlineService()
        self.stage_priority = PipelinePriorityAdmissionService()
        self.stage_ingress = PipelineHandlerIngressService(dispatcher=InMemoryDomainDispatcherAdapter())

        outer_cfg = unified_cfg.get("outer_wrapper", {})
        pipeline_cfg = unified_cfg.get("pipeline", {})
        self.problem_base_url: str = outer_cfg.get(
            "problem_type_base",
            pipeline_cfg.get("problem_details_type_base", "https://errors.example.com/problems/"),
        )

        admission_cfg = unified_cfg.get("global_admission", {})
        self.max_global_concurrency = admission_cfg.get("max_concurrency", self.policy.limits.global_admission_limit)
        self.access_logs: List[AccessLogEntry] = []

        cors_cfg = unified_cfg.get("cors", {})
        self.cors_enabled: bool = cors_cfg.get("enabled", True)
        self.allowed_origins: List[str] = cors_cfg.get("allowed_origins", ["*"])
        self.cors_allowed_methods: List[str] = cors_cfg.get("allowed_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        self.cors_allowed_headers: List[str] = cors_cfg.get("allowed_headers", ["authorization", "content-type", "x-request-id", "x-csrf-token", "idempotency-key"])
        self.cors_max_age_seconds: int = cors_cfg.get("max_age_seconds", 86400)
        self.cors_allow_credentials: bool = cors_cfg.get("allow_credentials", False)

        csrf_cfg = unified_cfg.get("csrf", {})
        self.csrf_enabled: bool = csrf_cfg.get("enabled", False)
        self.csrf_header_name: str = csrf_cfg.get("header_name", PipelineHeaders.X_CSRF_TOKEN)

    async def execute(
        self,
        req: IngressRequest,
        body_reader: Optional[Callable[[int], Awaitable[bytes]]] = None,
    ) -> IngressResponse:
        response = await self._execute(req, body_reader)
        origin = req.headers.get(PipelineHeaders.ORIGIN)
        if (
            self.cors_enabled
            and origin
            and CorsAndCsrfRules.is_cors_request(origin)
            and CorsAndCsrfRules.is_origin_allowed(origin, self.allowed_origins)
        ):
            response.headers.update(CorsAndCsrfRules.build_cors_headers(origin, self.cors_allow_credentials))
        return response

    async def _execute(
        self,
        req: IngressRequest,
        body_reader: Optional[Callable[[int], Awaitable[bytes]]] = None,
    ) -> IngressResponse:
        start_time = time.monotonic()
        ctx = PipelineRequestContext(
            request=req,
            resolved_peer_ip=req.remote_addr,
            matched_route=req.path,
        )

        held_idempotency_key: Optional[str] = None
        try:
            ctx.current_stage_index = 1
            ctx.current_stage_name = PipelineStageNames.IDENTITY
            ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_REQUEST_IDENTITY)
            with trace_pipeline_stage(PipelineStageTrails.STAGE_REQUEST_IDENTITY, {"request.method": req.method, "request.path": req.path}):
                id_out = self.stage_identity.execute(IdentityInputDTO(headers=req.headers, is_trusted_hop=False))
                ctx.request_id = id_out.request_id
                ctx.trace_id = id_out.traceparent

            ctx.current_stage_index = 2
            ctx.current_stage_name = PipelineStageNames.PEER_RESOLUTION
            ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_PEER_RESOLUTION)
            with trace_pipeline_stage(PipelineStageTrails.STAGE_PEER_RESOLUTION, {"peer.raw_remote": req.remote_addr}):
                peer_out = self.stage_peer.execute(PeerResolutionInputDTO(
                    remote_addr=req.remote_addr,
                    x_forwarded_for=req.headers.get(PipelineHeaders.X_FORWARDED_FOR),
                ))
                ctx.resolved_peer_ip = peer_out.client_ip

            ctx.current_stage_index = 3
            ctx.current_stage_name = PipelineStageNames.GLOBAL_ADMISSION
            ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_GLOBAL_ADMISSION)
            with trace_pipeline_stage(PipelineStageTrails.STAGE_GLOBAL_ADMISSION, {"admission.capacity": self.max_global_concurrency}):
                adm_out = self.stage_admission.execute(AdmissionInputDTO(max_concurrency=self.max_global_concurrency))
                if not adm_out.allowed:
                    return ResponseFactoryRules.create_rejection(
                        ctx=ctx,
                        status_code=503,
                        reason=PipelineRejectionReasons.ADMISSION,
                        detail=PipelineProblemDetails.GLOBAL_CAPACITY_EXCEEDED,
                        problem_base_url=self.problem_base_url,
                        retry_after_seconds=adm_out.retry_after_seconds,
                    )

            try:
                origin_header = req.headers.get(PipelineHeaders.ORIGIN)
                if self.cors_enabled and CorsAndCsrfRules.is_cors_request(origin_header):
                    if not CorsAndCsrfRules.is_origin_allowed(origin_header or "", self.allowed_origins):
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=403,
                            reason=PipelineRejectionReasons.CORS_FORBIDDEN,
                            detail=PipelineProblemDetails.CORS_ORIGIN_NOT_ALLOWED,
                            problem_base_url=self.problem_base_url,
                        )
                    if CorsAndCsrfRules.is_preflight_request(req.method, bool(origin_header)):
                        cors_headers = {
                            PipelineHeaders.ACCESS_CONTROL_ALLOW_ORIGIN: origin_header or "*",
                            PipelineHeaders.ACCESS_CONTROL_ALLOW_METHODS: ", ".join(self.cors_allowed_methods),
                            PipelineHeaders.ACCESS_CONTROL_ALLOW_HEADERS: ", ".join(self.cors_allowed_headers),
                            PipelineHeaders.ACCESS_CONTROL_MAX_AGE: str(self.cors_max_age_seconds),
                        }
                        return ResponseFactoryRules.create_success(
                            ctx=ctx,
                            status_code=204,
                            response_body=None,
                            extra_headers=cors_headers,
                        )

                if CorsAndCsrfRules.is_csrf_check_required(
                    req.method,
                    bool(origin_header),
                    req.headers.get(PipelineHeaders.AUTHORIZATION),
                    self.csrf_enabled,
                ):
                    client_csrf = req.headers.get(self.csrf_header_name)
                    if not client_csrf:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=403,
                            reason=PipelineRejectionReasons.CSRF_INVALID,
                            detail=PipelineProblemDetails.CSRF_TOKEN_MISSING_OR_INVALID,
                            problem_base_url=self.problem_base_url,
                        )

                if not PathCanonicalizationRules.is_canonical_path(req.path):
                    return ResponseFactoryRules.create_rejection(
                        ctx=ctx,
                        status_code=400,
                        reason=PipelineRejectionReasons.PATH_NONCANONICAL,
                        detail=PipelineProblemDetails.PATH_NONCANONICAL_DETAIL,
                        problem_base_url=self.problem_base_url,
                    )

                ctx.current_stage_index = 4
                ctx.current_stage_name = PipelineStageNames.ROUTE_RESOLUTION
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_ROUTE_RESOLUTION)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_ROUTE_RESOLUTION, {"http.target_path": req.path}):
                    route_out = self.stage_route.execute(RouteResolutionInputDTO(path=req.path, method=req.method))
                    if not route_out.matched:
                        reason = PipelineRejectionReasons.ROUTE_NOT_FOUND if route_out.status_code == 404 else PipelineRejectionReasons.METHOD_NOT_ALLOWED
                        extra_headers = {PipelineHeaders.ALLOW: ", ".join(route_out.allowed_methods)} if route_out.status_code == 405 else None
                        detail = PipelineProblemDetails.ROUTE_NOT_FOUND_DETAIL if route_out.status_code == 404 else PipelineProblemDetails.METHOD_NOT_ALLOWED_DETAIL
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=route_out.status_code,
                            reason=reason,
                            detail=detail,
                            problem_base_url=self.problem_base_url,
                            extra_headers=extra_headers,
                        )

                    if route_out.route is None:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=500,
                            reason=PipelineRejectionReasons.INTERNAL_ERROR,
                            detail=PipelineProblemDetails.INTERNAL_ROUTING_ERROR,
                            problem_base_url=self.problem_base_url,
                        )

                    if route_out.route.disabled:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=503,
                            reason=PipelineRejectionReasons.ROUTE_DISABLED,
                            detail=PipelineProblemDetails.ROUTE_DISABLED_DETAIL,
                            problem_base_url=self.problem_base_url,
                        )

                    if route_out.route.idempotency_key_required and RequestMutationRules.is_mutating_method(req.method):
                        idempotency_header = req.headers.get(PipelineHeaders.IDEMPOTENCY_KEY)
                        if not idempotency_header:
                            return ResponseFactoryRules.create_rejection(
                                ctx=ctx,
                                status_code=400,
                                reason=PipelineRejectionReasons.IDEMPOTENCY_KEY_MISSING,
                                detail=PipelineProblemDetails.IDEMPOTENCY_KEY_MISSING_DETAIL,
                                problem_base_url=self.problem_base_url,
                            )
                        cached_record = await self.idempotency_store.get_response(idempotency_header)
                        if cached_record is not None:
                            cached_status, cached_bytes = cached_record
                            cached_body: Any
                            try:
                                cached_body = json.loads(cached_bytes.decode("utf-8"))
                            except Exception:
                                cached_body = cached_bytes
                            return ResponseFactoryRules.create_success(
                                ctx=ctx,
                                status_code=cached_status,
                                response_body=cached_body,
                                extra_headers={PipelineHeaders.IDEMPOTENT_REPLAY: "true"},
                            )
                        acquired = await self.idempotency_store.try_acquire(idempotency_header)
                        if not acquired:
                            return ResponseFactoryRules.create_rejection(
                                ctx=ctx,
                                status_code=409,
                                reason=PipelineRejectionReasons.IDEMPOTENCY_CONFLICT,
                                detail=PipelineProblemDetails.IDEMPOTENCY_CONFLICT_DETAIL,
                                problem_base_url=self.problem_base_url,
                            )
                        held_idempotency_key = idempotency_header

                    ctx.matched_route = route_out.route.path_template

                ctx.current_stage_index = 5
                ctx.current_stage_name = PipelineStageNames.ROUTE_LIMITS
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_ROUTE_LIMITS)
                route_limits_cfg = RouteLimitsConfig(
                    max_body_bytes=route_out.route.max_body_bytes,
                    allowed_media_types=route_out.route.allowed_media_types,
                )
                with trace_pipeline_stage(PipelineStageTrails.STAGE_ROUTE_LIMITS, {"http.route": ctx.matched_route}):
                    limits_out = self.stage_limits.execute(RouteLimitsInputDTO(headers=req.headers, limits=route_limits_cfg))
                    if not limits_out.passed:
                        reason = {
                            413: PipelineRejectionReasons.BODY_TOO_LARGE,
                            431: PipelineRejectionReasons.HEADERS_TOO_LARGE,
                        }.get(limits_out.status_code, PipelineRejectionReasons.UNSUPPORTED_MEDIA_TYPE)
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=limits_out.status_code,
                            reason=reason,
                            detail=limits_out.rejection_reason or PipelineProblemDetails.ROUTE_LIMIT_VIOLATED,
                            problem_base_url=self.problem_base_url,
                        )

                ctx.current_stage_index = 6
                ctx.current_stage_name = PipelineStageNames.PRE_AUTH_LIMIT
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_PRE_AUTH_LIMIT)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_PRE_AUTH_LIMIT, {"client.ip": ctx.resolved_peer_ip}):
                    pre_auth_out = self.stage_pre_auth.execute(PreAuthLimitInputDTO(client_ip=ctx.resolved_peer_ip))
                    if not pre_auth_out.allowed:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=429,
                            reason=PipelineRejectionReasons.RATE_LIMIT,
                            detail=PipelineProblemDetails.PEER_RATE_LIMIT_DETAIL,
                            problem_base_url=self.problem_base_url,
                            retry_after_seconds=pre_auth_out.retry_after_seconds,
                        )

                ctx.current_stage_index = 7
                ctx.current_stage_name = PipelineStageNames.AUTHENTICATION
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_AUTHENTICATION)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_AUTHENTICATION, {"auth.scheme": "Bearer"}):
                    auth_out = self.stage_auth.execute(AuthInputDTO(headers=req.headers, require_auth=True))
                    if not auth_out.authenticated:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=401,
                            reason=PipelineRejectionReasons.AUTH,
                            detail=auth_out.rejection_reason or PipelineProblemDetails.AUTH_REQUIRED_DETAIL,
                            problem_base_url=self.problem_base_url,
                            extra_headers={PipelineHeaders.WWW_AUTHENTICATE: "Bearer"},
                        )

                    ctx.principal = auth_out.principal
                    if auth_out.principal:
                        ctx.principal_id = auth_out.principal.principal_id
                        ctx.tenant_id = auth_out.principal.tenant_id
                        ctx.authenticated_scopes = set(auth_out.principal.scopes)

                ctx.current_stage_index = 8
                ctx.current_stage_name = PipelineStageNames.AUTHORIZATION
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_AUTHORIZATION)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_AUTHORIZATION, {"auth.principal_id": ctx.principal_id or ""}):
                    authz_out = self.stage_authz.execute(AuthzInputDTO(
                        principal_scopes=ctx.authenticated_scopes,
                        required_scopes=route_out.route.required_scopes,
                    ))
                    if not authz_out.authorized:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=403,
                            reason=PipelineRejectionReasons.AUTHZ,
                            detail=PipelineProblemDetails.INSUFFICIENT_SCOPES_DETAIL,
                            problem_base_url=self.problem_base_url,
                        )

                ctx.current_stage_index = 9
                ctx.current_stage_name = PipelineStageNames.TENANT_QUOTA
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_TENANT_QUOTA)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_TENANT_QUOTA, {"tenant.id": ctx.tenant_id or PipelineTenantConstants.DEFAULT_TENANT_ID}):
                    quota_out = self.stage_quota.execute(TenantQuotaInputDTO(
                        tenant_id=ctx.tenant_id or PipelineTenantConstants.DEFAULT_TENANT_ID,
                        tokens=self.policy.limits.tenant_quota_tokens,
                        refill_rate=self.policy.limits.tenant_quota_refill_per_sec,
                    ))
                    if not quota_out.allowed:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=429,
                            reason=PipelineRejectionReasons.QUOTA,
                            detail=PipelineProblemDetails.TENANT_QUOTA_EXHAUSTED_DETAIL,
                            problem_base_url=self.problem_base_url,
                            retry_after_seconds=quota_out.retry_after_seconds,
                        )

                ctx.current_stage_index = 10
                ctx.current_stage_name = PipelineStageNames.DEADLINE
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_DEADLINE)
                with trace_pipeline_stage(PipelineStageTrails.STAGE_DEADLINE, {"client.timeout_ms": req.client_timeout_ms or 0.0}):
                    deadline_out = self.stage_deadline.execute(DeadlineInputDTO(
                        client_timeout_ms=req.client_timeout_ms,
                        route_min_ms=route_out.route.min_timeout_ms,
                        route_max_ms=route_out.route.max_timeout_ms,
                    ))
                    ctx.allocated_deadline_ms = deadline_out.allocated_budget_ms
                    if not deadline_out.valid:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=504,
                            reason=PipelineRejectionReasons.DEADLINE_UNVIABLE,
                            detail=PipelineProblemDetails.DEADLINE_UNVIABLE_DETAIL,
                            problem_base_url=self.problem_base_url,
                        )

                ctx.current_stage_index = 11
                ctx.current_stage_name = PipelineStageNames.PRIORITY_ADMISSION
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_PRIORITY_ADMISSION)
                current_in_flight = self.stage_admission.tracker.get_in_flight()
                load_ratio = float(current_in_flight) / float(max(1, self.max_global_concurrency))
                with trace_pipeline_stage(PipelineStageTrails.STAGE_PRIORITY_ADMISSION, {"priority.class": str(req.priority_class), "system.load_ratio": load_ratio}):
                    priority_out = self.stage_priority.execute(PriorityAdmissionInputDTO(
                        priority_class=req.priority_class,
                        system_load_ratio=load_ratio,
                    ))
                    if not priority_out.admitted:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=503,
                            reason=PipelineRejectionReasons.PRIORITY_SHEDDING,
                            detail=PipelineProblemDetails.PRIORITY_SHEDDING_DETAIL,
                            problem_base_url=self.problem_base_url,
                            retry_after_seconds=priority_out.retry_after_seconds,
                        )

                ctx.current_stage_index = 12
                ctx.current_stage_name = PipelineStageNames.HANDLER_INGRESS
                ctx.stage_execution_trail.append(PipelineStageTrails.STAGE_HANDLER_INGRESS)
                if body_reader is not None:
                    try:
                        req.body = await body_reader(route_out.route.max_body_bytes)
                    except PayloadTooLargeError:
                        return ResponseFactoryRules.create_rejection(
                            ctx=ctx,
                            status_code=413,
                            reason=PipelineRejectionReasons.BODY_TOO_LARGE,
                            detail="Payload Too Large",
                            problem_base_url=self.problem_base_url,
                        )
                with trace_pipeline_stage(PipelineStageTrails.STAGE_HANDLER_INGRESS, {"handler.target": route_out.route.handler_name}):
                    ingress_out = await self.stage_ingress.execute(HandlerIngressInputDTO(
                        headers=req.headers,
                        body=req.body,
                        target_handler=route_out.route.handler_name,
                    ))

                if route_out.route.idempotency_key_required and RequestMutationRules.is_mutating_method(req.method):
                    idempotency_header = req.headers.get(PipelineHeaders.IDEMPOTENCY_KEY)
                    if idempotency_header:
                        resp_bytes: bytes
                        if isinstance(ingress_out.response_body, bytes):
                            resp_bytes = ingress_out.response_body
                        elif isinstance(ingress_out.response_body, str):
                            resp_bytes = ingress_out.response_body.encode("utf-8")
                        else:
                            try:
                                resp_bytes = json.dumps(
                                    ingress_out.response_body,
                                    default=lambda o: o.decode("utf-8", errors="replace") if isinstance(o, bytes) else str(o),
                                ).encode("utf-8")
                            except Exception:
                                resp_bytes = str(ingress_out.response_body).encode("utf-8")
                        await self.idempotency_store.record_response(
                            key=idempotency_header,
                            status_code=ingress_out.status_code,
                            response_body=resp_bytes,
                        )
                        held_idempotency_key = None

                return ResponseFactoryRules.create_success(
                    ctx=ctx,
                    status_code=ingress_out.status_code,
                    response_body=ingress_out.response_body,
                )
            finally:
                if held_idempotency_key is not None:
                    await self.idempotency_store.release(held_idempotency_key)
                self.stage_admission.release()
        except Exception as e:
            logger.error("Unhandled pipeline exception: %s", str(e), exc_info=True)
            return ResponseFactoryRules.create_rejection(
                ctx=ctx,
                status_code=500,
                reason=PipelineRejectionReasons.INTERNAL_ERROR,
                detail=PipelineProblemDetails.INTERNAL_SERVER_ERROR,
                problem_base_url=self.problem_base_url,
            )
        finally:
            duration = time.monotonic() - start_time
            bytes_in = len(req.body) if req.body else 0
            log_entry = AccessLogEntry(
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                route=ctx.matched_route or req.path,
                method=req.method,
                peer=ctx.resolved_peer_ip,
                principal=ctx.principal_id,
                tenant_id=ctx.tenant_id,
                status=ctx.status_code,
                reason=ctx.rejection_reason,
                duration_seconds=duration,
                bytes_in=bytes_in,
                bytes_out=ctx.bytes_out,
            )
            self.access_logs.append(log_entry)
            if ctx.status_code >= 400:
                logger.warning(
                    "ingress_request_completed status=%d reason=%s route=%s peer=%s principal=%s duration_ms=%.2f req_id=%s trace=%s",
                    ctx.status_code,
                    ctx.rejection_reason or "none",
                    ctx.matched_route or req.path,
                    ctx.resolved_peer_ip,
                    ctx.principal_id or PipelineTenantConstants.ANONYMOUS_PRINCIPAL,
                    duration * 1000.0,
                    ctx.request_id,
                    ctx.trace_id,
                )
            else:
                logger.info(
                    "ingress_request_completed status=%d route=%s peer=%s principal=%s duration_ms=%.2f req_id=%s trace=%s",
                    ctx.status_code,
                    ctx.matched_route or req.path,
                    ctx.resolved_peer_ip,
                    ctx.principal_id or PipelineTenantConstants.ANONYMOUS_PRINCIPAL,
                    duration * 1000.0,
                    ctx.request_id,
                    ctx.trace_id,
                )

    async def asgi(self, scope: dict, receive: Any, send: Any) -> None:
        from src.features.server.composable_pipeline.infrastructure.adapters.asgi_pipeline_adapter import (
            AsgiPipelineAdapter,
        )

        adapter = AsgiPipelineAdapter(self)
        await adapter(scope, receive, send)
