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
import time
import logging
from typing import Any, Dict, List, Optional
from src.features.server.composable_pipeline.contracts.pipeline_types import (
    IngressRequest,
    IngressResponse,
    PipelineRequestContext,
)
from src.features.server.composable_pipeline.contracts.rfc9457_types import ProblemDetails
from src.features.server.composable_pipeline.contracts.telemetry_types import AccessLogEntry, PipelineMetricsRecord
from src.features.server.composable_pipeline.domain.rules.rfc9457_rules import ProblemDetailsRules
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
        self.stage_quota = PipelineTenantQuotaService(quota_port=InMemoryTenantQuotaAdapter())
        self.stage_deadline = PipelineDeadlineService()
        self.stage_priority = PipelinePriorityAdmissionService()
        self.stage_ingress = PipelineHandlerIngressService(dispatcher=InMemoryDomainDispatcherAdapter())

        outer_cfg = unified_cfg.get("outer_wrapper", {})
        pipeline_cfg = unified_cfg.get("pipeline", {})
        self.problem_base_url: str = outer_cfg.get(
            "problem_type_base",
            pipeline_cfg.get("problem_details_type_base", "https://errors.example.com/problems/"),
        )

        from src.features.server.composable_pipeline.infrastructure.adapters.in_memory_idempotency_store_adapter import (
            InMemoryIdempotencyStoreAdapter,
        )

        self.idempotency_store = InMemoryIdempotencyStoreAdapter()
        admission_cfg = unified_cfg.get("global_admission", {})
        self.max_global_concurrency = admission_cfg.get("max_concurrency", self.policy.limits.global_admission_limit)
        self.access_logs: List[AccessLogEntry] = []

    async def execute(self, req: IngressRequest) -> IngressResponse:
        start_time = time.monotonic()
        ctx = PipelineRequestContext(
            request=req,
            resolved_peer_ip=req.remote_addr,
            matched_route=req.path,
        )

        try:
            ctx.current_stage_index = 1
            ctx.current_stage_name = "pipeline_identity"
            ctx.stage_execution_trail.append("stage_request_identity")
            with trace_pipeline_stage("stage_request_identity", {"request.method": req.method, "request.path": req.path}):
                id_out = self.stage_identity.execute(IdentityInputDTO(headers=req.headers, is_trusted_hop=False))
                ctx.request_id = id_out.request_id
                ctx.trace_id = id_out.traceparent

            ctx.current_stage_index = 2
            ctx.current_stage_name = "pipeline_peer_resolution"
            ctx.stage_execution_trail.append("stage_peer_resolution")
            with trace_pipeline_stage("stage_peer_resolution", {"peer.raw_remote": req.remote_addr}):
                peer_out = self.stage_peer.execute(PeerResolutionInputDTO(
                    remote_addr=req.remote_addr,
                    x_forwarded_for=req.headers.get("x-forwarded-for"),
                ))
                ctx.resolved_peer_ip = peer_out.client_ip

            ctx.current_stage_index = 3
            ctx.current_stage_name = "pipeline_global_admission"
            ctx.stage_execution_trail.append("stage_global_admission")
            with trace_pipeline_stage("stage_global_admission", {"admission.capacity": self.max_global_concurrency}):
                adm_out = self.stage_admission.execute(AdmissionInputDTO(max_concurrency=self.max_global_concurrency))
                if not adm_out.allowed:
                    ctx.status_code = 503
                    ctx.is_failed = True
                    ctx.rejection_reason = "admission"
                    return IngressResponse(
                        status_code=503,
                        headers={"Retry-After": str(adm_out.retry_after_seconds), "x-request-id": ctx.request_id},
                        problem_details=ProblemDetailsRules.create_problem(
                            status=503,
                            detail="Global capacity exceeded",
                            instance=ctx.request_id,
                            reason=ctx.rejection_reason,
                            base_url=self.problem_base_url,
                            retry_after_seconds=adm_out.retry_after_seconds,
                        ),
                        context=ctx,
                    )

            try:
                raw_path = req.path
                if "//" in raw_path or "/../" in raw_path or raw_path.endswith("/..") or "/./" in raw_path or "%2f" in raw_path.lower() or "%5c" in raw_path.lower():
                    ctx.status_code = 400
                    ctx.is_failed = True
                    ctx.rejection_reason = "path_noncanonical"
                    return IngressResponse(
                        status_code=400,
                        headers={"x-request-id": ctx.request_id},
                        problem_details=ProblemDetailsRules.create_problem(
                            status=400,
                            detail="Path is not canonical. Encoded slashes and dot-segments are rejected.",
                            instance=ctx.request_id,
                            reason="path_noncanonical",
                            base_url=self.problem_base_url,
                        ),
                        context=ctx,
                    )

                ctx.current_stage_index = 4
                ctx.current_stage_name = "pipeline_route_resolution"
                ctx.stage_execution_trail.append("stage_route_resolution")
                with trace_pipeline_stage("stage_route_resolution", {"http.target_path": req.path}):
                    route_out = self.stage_route.execute(RouteResolutionInputDTO(path=req.path, method=req.method))
                    if not route_out.matched:
                        ctx.status_code = route_out.status_code
                        ctx.is_failed = True
                        ctx.rejection_reason = "route_not_found" if route_out.status_code == 404 else "method_not_allowed"
                        headers = {"x-request-id": ctx.request_id}
                        if route_out.status_code == 405:
                            headers["Allow"] = ", ".join(route_out.allowed_methods)
                        return IngressResponse(
                            status_code=route_out.status_code,
                            headers=headers,
                            problem_details=ProblemDetailsRules.create_problem(
                                status=route_out.status_code,
                                detail="Route matching failed" if route_out.status_code == 404 else "Method not allowed for this route",
                                instance=ctx.request_id,
                                reason=ctx.rejection_reason,
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                    if route_out.route is None:
                        ctx.status_code = 500
                        ctx.is_failed = True
                        ctx.rejection_reason = "internal_error"
                        return IngressResponse(
                            status_code=500,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=500,
                                detail="Internal routing error",
                                instance=ctx.request_id,
                                reason="internal_error",
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                    if route_out.route.disabled:
                        ctx.status_code = 503
                        ctx.is_failed = True
                        ctx.rejection_reason = "route_disabled"
                        return IngressResponse(
                            status_code=503,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=503,
                                detail="Route temporarily disabled by kill switch",
                                instance=ctx.request_id,
                                reason="route_disabled",
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                    if route_out.route.idempotency_key_required and req.method.upper() in {"POST", "PUT", "PATCH"}:
                        idempotency_header = req.headers.get("idempotency-key")
                        if not idempotency_header:
                            ctx.status_code = 400
                            ctx.is_failed = True
                            ctx.rejection_reason = "idempotency_key_missing"
                            return IngressResponse(
                                status_code=400,
                                headers={"x-request-id": ctx.request_id},
                                problem_details=ProblemDetailsRules.create_problem(
                                    status=400,
                                    detail="Idempotency-Key header is required for this route",
                                    instance=ctx.request_id,
                                    reason="idempotency_key_missing",
                                    base_url=self.problem_base_url,
                                ),
                                context=ctx,
                            )
                        acquired = await self.idempotency_store.try_acquire(idempotency_header)
                        if not acquired:
                            ctx.status_code = 409
                            ctx.is_failed = True
                            ctx.rejection_reason = "idempotency_conflict"
                            return IngressResponse(
                                status_code=409,
                                headers={"x-request-id": ctx.request_id},
                                problem_details=ProblemDetailsRules.create_problem(
                                    status=409,
                                    detail="A request with this Idempotency-Key is currently in progress",
                                    instance=ctx.request_id,
                                    reason="idempotency_conflict",
                                    base_url=self.problem_base_url,
                                ),
                                context=ctx,
                            )

                    ctx.matched_route = route_out.route.path_template

                ctx.current_stage_index = 5
                ctx.current_stage_name = "pipeline_route_limits"
                ctx.stage_execution_trail.append("stage_route_limits")
                route_limits_cfg = RouteLimitsConfig(
                    max_body_bytes=route_out.route.max_body_bytes,
                    allowed_media_types=route_out.route.allowed_media_types,
                )
                with trace_pipeline_stage("stage_route_limits", {"http.route": ctx.matched_route}):
                    limits_out = self.stage_limits.execute(RouteLimitsInputDTO(headers=req.headers, limits=route_limits_cfg))
                    if not limits_out.passed:
                        ctx.status_code = limits_out.status_code
                        ctx.is_failed = True
                        ctx.rejection_reason = "body_too_large" if limits_out.status_code == 413 else "unsupported_media_type"
                        return IngressResponse(
                            status_code=limits_out.status_code,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=limits_out.status_code,
                                detail=limits_out.rejection_reason or "Route limit violated",
                                instance=ctx.request_id,
                                reason=ctx.rejection_reason,
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 6
                ctx.current_stage_name = "pipeline_pre_auth_limit"
                ctx.stage_execution_trail.append("stage_pre_auth_limit")
                with trace_pipeline_stage("stage_pre_auth_limit", {"client.ip": ctx.resolved_peer_ip}):
                    pre_auth_out = self.stage_pre_auth.execute(PreAuthLimitInputDTO(client_ip=ctx.resolved_peer_ip))
                    if not pre_auth_out.allowed:
                        ctx.status_code = 429
                        ctx.is_failed = True
                        ctx.rejection_reason = "rate_limit"
                        return IngressResponse(
                            status_code=429,
                            headers={"Retry-After": str(pre_auth_out.retry_after_seconds), "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=429,
                                detail="Too many requests from peer IP",
                                instance=ctx.request_id,
                                reason="rate_limit",
                                base_url=self.problem_base_url,
                                retry_after_seconds=pre_auth_out.retry_after_seconds,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 7
                ctx.current_stage_name = "pipeline_authentication"
                ctx.stage_execution_trail.append("stage_authentication")
                with trace_pipeline_stage("stage_authentication", {"auth.scheme": "Bearer"}):
                    auth_out = self.stage_auth.execute(AuthInputDTO(headers=req.headers, require_auth=True))
                    if not auth_out.authenticated:
                        ctx.status_code = 401
                        ctx.is_failed = True
                        ctx.rejection_reason = "auth"
                        return IngressResponse(
                            status_code=401,
                            headers={"WWW-Authenticate": "Bearer", "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=401,
                                detail=auth_out.rejection_reason or "Authentication required",
                                instance=ctx.request_id,
                                reason="auth",
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                    ctx.principal = auth_out.principal
                    if auth_out.principal:
                        ctx.principal_id = auth_out.principal.principal_id
                        ctx.tenant_id = auth_out.principal.tenant_id
                        ctx.authenticated_scopes = set(auth_out.principal.scopes)

                ctx.current_stage_index = 8
                ctx.current_stage_name = "pipeline_authorization"
                ctx.stage_execution_trail.append("stage_authorization")
                required_route_scopes = route_out.route.required_scopes if route_out.route.required_scopes else {"read"}
                with trace_pipeline_stage("stage_authorization", {"auth.principal_id": ctx.principal_id or ""}):
                    authz_out = self.stage_authz.execute(AuthzInputDTO(
                        principal_scopes=ctx.authenticated_scopes,
                        required_scopes=required_route_scopes,
                    ))
                    if not authz_out.authorized:
                        ctx.status_code = 403
                        ctx.is_failed = True
                        ctx.rejection_reason = "authz"
                        return IngressResponse(
                            status_code=403,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=403,
                                detail="Insufficient scopes for route",
                                instance=ctx.request_id,
                                reason="authz",
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 9
                ctx.current_stage_name = "pipeline_tenant_quota"
                ctx.stage_execution_trail.append("stage_tenant_quota")
                with trace_pipeline_stage("stage_tenant_quota", {"tenant.id": ctx.tenant_id or "default"}):
                    quota_out = self.stage_quota.execute(TenantQuotaInputDTO(
                        tenant_id=ctx.tenant_id or "default",
                        tokens=self.policy.limits.tenant_quota_tokens,
                        refill_rate=self.policy.limits.tenant_quota_refill_per_sec,
                    ))
                    if not quota_out.allowed:
                        ctx.status_code = 429
                        ctx.is_failed = True
                        ctx.rejection_reason = "quota"
                        return IngressResponse(
                            status_code=429,
                            headers={"Retry-After": str(quota_out.retry_after_seconds), "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=429,
                                detail="Tenant quota exhausted",
                                instance=ctx.request_id,
                                reason="quota",
                                base_url=self.problem_base_url,
                                retry_after_seconds=quota_out.retry_after_seconds,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 10
                ctx.current_stage_name = "pipeline_deadline"
                ctx.stage_execution_trail.append("stage_deadline")
                with trace_pipeline_stage("stage_deadline", {"client.timeout_ms": req.client_timeout_ms or 0.0}):
                    deadline_out = self.stage_deadline.execute(DeadlineInputDTO(client_timeout_ms=req.client_timeout_ms))
                    ctx.allocated_deadline_ms = deadline_out.allocated_budget_ms
                    if not deadline_out.valid:
                        ctx.status_code = 504
                        ctx.is_failed = True
                        ctx.rejection_reason = "deadline_unviable"
                        return IngressResponse(
                            status_code=504,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=504,
                                detail="Deadline expired or insufficient timeout budget",
                                instance=ctx.request_id,
                                reason="deadline_unviable",
                                base_url=self.problem_base_url,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 11
                ctx.current_stage_name = "pipeline_priority_admission"
                ctx.stage_execution_trail.append("stage_priority_admission")
                current_in_flight = self.stage_admission.tracker.get_in_flight()
                load_ratio = float(current_in_flight) / float(max(1, self.max_global_concurrency))
                with trace_pipeline_stage("stage_priority_admission", {"priority.class": str(req.priority_class), "system.load_ratio": load_ratio}):
                    priority_out = self.stage_priority.execute(PriorityAdmissionInputDTO(
                        priority_class=req.priority_class,
                        system_load_ratio=load_ratio,
                    ))
                    if not priority_out.admitted:
                        ctx.status_code = 503
                        ctx.is_failed = True
                        ctx.rejection_reason = "priority_shedding"
                        return IngressResponse(
                            status_code=503,
                            headers={"Retry-After": str(priority_out.retry_after_seconds), "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(
                                status=503,
                                detail="Shedding low priority class",
                                instance=ctx.request_id,
                                reason="priority_shedding",
                                base_url=self.problem_base_url,
                                retry_after_seconds=priority_out.retry_after_seconds,
                            ),
                            context=ctx,
                        )

                ctx.current_stage_index = 12
                ctx.current_stage_name = "pipeline_handler_ingress"
                ctx.stage_execution_trail.append("stage_handler_ingress")
                with trace_pipeline_stage("stage_handler_ingress", {"handler.target": route_out.route.handler_name}):
                    ingress_out = await self.stage_ingress.execute(HandlerIngressInputDTO(
                        headers=req.headers,
                        body=req.body,
                        target_handler=route_out.route.handler_name,
                    ))

                ctx.status_code = ingress_out.status_code
                return IngressResponse(
                    status_code=ingress_out.status_code,
                    headers={"x-request-id": ctx.request_id, "traceparent": ctx.trace_id},
                    body=ingress_out.response_body,
                    context=ctx,
                )
            finally:
                self.stage_admission.release()
        except Exception as e:
            ctx.status_code = 500
            ctx.is_failed = True
            ctx.rejection_reason = "internal_error"
            logger.error("Unhandled pipeline exception: %s", str(e), exc_info=True)
            return IngressResponse(
                status_code=500,
                headers={"x-request-id": ctx.request_id},
                problem_details=ProblemDetailsRules.create_problem(
                    status=500,
                    detail="Internal Server Error",
                    instance=ctx.request_id,
                    reason="internal_error",
                    base_url=self.problem_base_url,
                ),
                context=ctx,
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
                bytes_out=0,
            )
            self.access_logs.append(log_entry)
            if ctx.status_code >= 400:
                logger.warning(
                    "ingress_request_completed status=%d reason=%s route=%s peer=%s principal=%s duration_ms=%.2f req_id=%s trace=%s",
                    ctx.status_code,
                    ctx.rejection_reason or "none",
                    ctx.matched_route or req.path,
                    ctx.resolved_peer_ip,
                    ctx.principal_id or "anonymous",
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
                    ctx.principal_id or "anonymous",
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
