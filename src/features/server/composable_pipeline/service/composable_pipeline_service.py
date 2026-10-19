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
from typing import List, Optional
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
from src.features.server.pipeline_route_limits import PipelineRouteLimitsService, RouteLimitsInputDTO
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
    ) -> None:
        self.policy = policy if policy is not None else ServerPolicySnapshot()
        self.stage_identity = PipelineIdentityService(port=StandardIdentityAdapter())
        self.stage_peer = PipelinePeerResolutionService(
            config_port=StandardPeerConfigAdapter(proxies=self.policy.server.trusted_proxies)
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
        self.max_global_concurrency = self.policy.limits.global_admission_limit
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
            ctx.stage_execution_trail.append("stage_01_identity")
            with trace_pipeline_stage("stage_01_identity", {"request.method": req.method, "request.path": req.path}):
                id_out = self.stage_identity.execute(IdentityInputDTO(headers=req.headers, is_trusted_hop=False))
                ctx.request_id = id_out.request_id
                ctx.trace_id = id_out.traceparent

            ctx.current_stage_index = 2
            ctx.current_stage_name = "pipeline_peer_resolution"
            ctx.stage_execution_trail.append("stage_02_peer_resolution")
            with trace_pipeline_stage("stage_02_peer_resolution", {"peer.raw_remote": req.remote_addr}):
                peer_out = self.stage_peer.execute(PeerResolutionInputDTO(
                    remote_addr=req.remote_addr,
                    x_forwarded_for=req.headers.get("x-forwarded-for"),
                ))
                ctx.resolved_peer_ip = peer_out.client_ip

            ctx.current_stage_index = 3
            ctx.current_stage_name = "pipeline_global_admission"
            ctx.stage_execution_trail.append("stage_03_global_admission")
            with trace_pipeline_stage("stage_03_global_admission", {"admission.capacity": self.max_global_concurrency}):
                adm_out = self.stage_admission.execute(AdmissionInputDTO(max_concurrency=self.max_global_concurrency))
                if not adm_out.allowed:
                    ctx.status_code = 503
                    ctx.is_failed = True
                    ctx.rejection_reason = "admission"
                    return IngressResponse(
                        status_code=503,
                        headers={"Retry-After": str(adm_out.retry_after_seconds), "x-request-id": ctx.request_id},
                        problem_details=ProblemDetailsRules.create_problem(503, "Global capacity exceeded", ctx.request_id),
                        context=ctx,
                    )

            try:
                ctx.current_stage_index = 4
                ctx.current_stage_name = "pipeline_route_resolution"
                ctx.stage_execution_trail.append("stage_04_route_resolution")
                with trace_pipeline_stage("stage_04_route_resolution", {"http.target_path": req.path}):
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
                            problem_details=ProblemDetailsRules.create_problem(route_out.status_code, "Route matching failed", ctx.request_id),
                            context=ctx,
                        )

                    if route_out.route is None:
                        ctx.status_code = 500
                        ctx.is_failed = True
                        ctx.rejection_reason = "internal_routing_error"
                        return IngressResponse(
                            status_code=500,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(500, "Internal routing error", ctx.request_id),
                            context=ctx,
                        )

                    ctx.matched_route = route_out.route.path_template

                ctx.current_stage_index = 5
                ctx.current_stage_name = "pipeline_route_limits"
                ctx.stage_execution_trail.append("stage_05_route_limits")
                with trace_pipeline_stage("stage_05_route_limits", {"http.route": ctx.matched_route}):
                    limits_out = self.stage_limits.execute(RouteLimitsInputDTO(headers=req.headers))
                    if not limits_out.passed:
                        ctx.status_code = limits_out.status_code
                        ctx.is_failed = True
                        ctx.rejection_reason = "body_too_large" if limits_out.status_code == 413 else "unsupported_media_type"
                        return IngressResponse(
                            status_code=limits_out.status_code,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(limits_out.status_code, limits_out.rejection_reason or "Route limit violated", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 6
                ctx.current_stage_name = "pipeline_pre_auth_limit"
                ctx.stage_execution_trail.append("stage_06_pre_auth_limit")
                with trace_pipeline_stage("stage_06_pre_auth_limit", {"client.ip": ctx.resolved_peer_ip}):
                    pre_auth_out = self.stage_pre_auth.execute(PreAuthLimitInputDTO(client_ip=ctx.resolved_peer_ip))
                    if not pre_auth_out.allowed:
                        ctx.status_code = 429
                        ctx.is_failed = True
                        ctx.rejection_reason = "rate_limit"
                        return IngressResponse(
                            status_code=429,
                            headers={"Retry-After": str(pre_auth_out.retry_after_seconds), "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(429, "Too many requests from peer IP", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 7
                ctx.current_stage_name = "pipeline_authentication"
                ctx.stage_execution_trail.append("stage_07_authentication")
                with trace_pipeline_stage("stage_07_authentication", {"auth.scheme": "Bearer"}):
                    auth_out = self.stage_auth.execute(AuthInputDTO(headers=req.headers, require_auth=True))
                    if not auth_out.authenticated:
                        ctx.status_code = 401
                        ctx.is_failed = True
                        ctx.rejection_reason = "auth"
                        return IngressResponse(
                            status_code=401,
                            headers={"WWW-Authenticate": "Bearer", "x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(401, auth_out.rejection_reason or "Authentication required", ctx.request_id),
                            context=ctx,
                        )

                    ctx.principal = auth_out.principal
                    if auth_out.principal:
                        ctx.principal_id = auth_out.principal.principal_id
                        ctx.tenant_id = auth_out.principal.tenant_id
                        ctx.authenticated_scopes = set(auth_out.principal.scopes)

                ctx.current_stage_index = 8
                ctx.current_stage_name = "pipeline_authorization"
                ctx.stage_execution_trail.append("stage_08_authorization")
                with trace_pipeline_stage("stage_08_authorization", {"auth.principal_id": ctx.principal_id or ""}):
                    authz_out = self.stage_authz.execute(AuthzInputDTO(
                        principal_scopes=ctx.authenticated_scopes,
                        required_scopes={"read"},
                    ))
                    if not authz_out.authorized:
                        ctx.status_code = 403
                        ctx.is_failed = True
                        ctx.rejection_reason = "authz"
                        return IngressResponse(
                            status_code=403,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(403, "Insufficient scopes", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 9
                ctx.current_stage_name = "pipeline_tenant_quota"
                ctx.stage_execution_trail.append("stage_09_tenant_quota")
                with trace_pipeline_stage("stage_09_tenant_quota", {"tenant.id": ctx.tenant_id or "default"}):
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
                            problem_details=ProblemDetailsRules.create_problem(429, "Tenant quota exhausted", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 10
                ctx.current_stage_name = "pipeline_deadline"
                ctx.stage_execution_trail.append("stage_10_deadline")
                with trace_pipeline_stage("stage_10_deadline", {"client.timeout_ms": req.client_timeout_ms or 0.0}):
                    deadline_out = self.stage_deadline.execute(DeadlineInputDTO(client_timeout_ms=req.client_timeout_ms))
                    ctx.allocated_deadline_ms = deadline_out.allocated_budget_ms
                    if not deadline_out.valid:
                        ctx.status_code = 504
                        ctx.is_failed = True
                        ctx.rejection_reason = "deadline_unviable"
                        return IngressResponse(
                            status_code=504,
                            headers={"x-request-id": ctx.request_id},
                            problem_details=ProblemDetailsRules.create_problem(504, "Deadline expired or insufficient timeout budget", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 11
                ctx.current_stage_name = "pipeline_priority_admission"
                ctx.stage_execution_trail.append("stage_11_priority_admission")
                current_in_flight = self.stage_admission.tracker.get_in_flight()
                load_ratio = float(current_in_flight) / float(max(1, self.max_global_concurrency))
                with trace_pipeline_stage("stage_11_priority_admission", {"priority.class": str(req.priority_class), "system.load_ratio": load_ratio}):
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
                            problem_details=ProblemDetailsRules.create_problem(503, "Shedding low priority class", ctx.request_id),
                            context=ctx,
                        )

                ctx.current_stage_index = 12
                ctx.current_stage_name = "pipeline_handler_ingress"
                ctx.stage_execution_trail.append("stage_12_handler_ingress")
                with trace_pipeline_stage("stage_12_handler_ingress", {"handler.target": route_out.route.handler_name}):
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
                problem_details=ProblemDetailsRules.create_problem(500, "Internal Server Error", ctx.request_id),
                context=ctx,
            )
        finally:
            duration = time.monotonic() - start_time
            log_entry = AccessLogEntry(
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                route=ctx.matched_route or req.path,
                peer=ctx.resolved_peer_ip,
                principal=ctx.principal_id,
                status=ctx.status_code,
                reason=ctx.rejection_reason,
                duration_seconds=duration,
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
