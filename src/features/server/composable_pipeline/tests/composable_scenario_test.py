"""
Blueprint:
- Scenario tests covering concrete production adversity scenarios derived from intent->spec probe bank:
  1. Priority shedding during high traffic (Stage 11 drops batch traffic while admitting interactive).
  2. Expired client deadline (Stage 10 drops request with 504 before handler dispatch).
  3. Pre-auth rate limiting by IP (Stage 6 throttles rogue IP with 429 + Retry-After).
  4. Tenant quota depletion (Stage 9 throttles tenant with 429 + Retry-After).
  5. Method Not Allowed with Allow header (Stage 4 returns 405 + Allow: GET, POST).
  6. Payload size exceeded (Stage 5 returns 413 Payload Too Large).
"""
import time
import pytest
from src.features.server.composable_pipeline import (
    ComposablePipelineService,
    IngressRequest,
)
from src.features.server.pipeline_priority_admission.contracts.pipeline_priority_admission_types import (
    RequestPriorityClass,
)
from src.features.server.pipeline_route_resolution import RouteDefinition
from src.features.server.pipeline_global_admission.infrastructure.adapters.pipeline_global_admission_adapter import (
    InMemoryAdmissionTrackerAdapter,
)
from src.features.server.pipeline_pre_auth_limit.infrastructure.adapters.pipeline_pre_auth_limit_adapter import (
    InMemoryPreAuthRateLimitAdapter,
)
from src.features.server.pipeline_tenant_quota.infrastructure.adapters.pipeline_tenant_quota_adapter import (
    InMemoryTenantQuotaAdapter,
)

@pytest.fixture
def scenario_pipeline() -> ComposablePipelineService:
    routes = [
        RouteDefinition(
            path_template="/api/v1/work",
            allowed_methods={"GET", "POST"},
            handler_name="work_handler",
        )
    ]
    return ComposablePipelineService(routes=routes)

@pytest.mark.asyncio
async def test_scenario_priority_load_shedding(scenario_pipeline: ComposablePipelineService) -> None:
    assert isinstance(scenario_pipeline.stage_admission.tracker, InMemoryAdmissionTrackerAdapter)
    scenario_pipeline.stage_admission.tracker._counter = 960
    batch_req = IngressRequest(
        method="POST",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr="192.168.10.1",
        priority_class=RequestPriorityClass.BATCH,
    )
    batch_res = await scenario_pipeline.execute(batch_req)
    assert batch_res.status_code == 503
    assert "Retry-After" in batch_res.headers
    assert batch_res.context is not None
    assert batch_res.context.rejection_reason == "priority_shedding"

    interactive_req = IngressRequest(
        method="POST",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr="192.168.10.2",
        priority_class=RequestPriorityClass.INTERACTIVE,
    )
    interactive_res = await scenario_pipeline.execute(interactive_req)
    assert interactive_res.status_code == 200

@pytest.mark.asyncio
async def test_scenario_insufficient_client_deadline(scenario_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
        client_timeout_ms=5.0,
    )
    res = await scenario_pipeline.execute(req)
    assert res.status_code == 504
    assert res.problem_details is not None
    assert res.problem_details.status == 504
    assert res.context is not None
    assert res.context.rejection_reason == "deadline_unviable"

@pytest.mark.asyncio
async def test_scenario_pre_auth_ip_exhaustion(scenario_pipeline: ComposablePipelineService) -> None:
    rogue_ip = "203.0.113.42"
    assert isinstance(scenario_pipeline.stage_pre_auth.limiter, InMemoryPreAuthRateLimitAdapter)
    scenario_pipeline.stage_pre_auth.limiter._buckets[rogue_ip] = (0.0, time.monotonic())
    exhausted_req = IngressRequest(
        method="GET",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr=rogue_ip,
    )
    blocked_res = await scenario_pipeline.execute(exhausted_req)
    assert blocked_res.status_code == 429
    assert "Retry-After" in blocked_res.headers
    assert blocked_res.context is not None
    assert blocked_res.context.rejection_reason == "rate_limit"

@pytest.mark.asyncio
async def test_scenario_tenant_quota_exhaustion(scenario_pipeline: ComposablePipelineService) -> None:
    assert isinstance(scenario_pipeline.stage_quota.quota_port, InMemoryTenantQuotaAdapter)
    scenario_pipeline.stage_quota.quota_port._buckets["tenant1"] = (0.0, time.monotonic())
    throttled_req = IngressRequest(
        method="GET",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr="172.20.254.254",
    )
    throttled_res = await scenario_pipeline.execute(throttled_req)
    assert throttled_res.status_code == 429
    assert "Retry-After" in throttled_res.headers
    assert throttled_res.context is not None
    assert throttled_res.context.rejection_reason == "quota"

@pytest.mark.asyncio
async def test_scenario_method_not_allowed_allow_header(scenario_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="DELETE",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await scenario_pipeline.execute(req)
    assert res.status_code == 405
    assert "Allow" in res.headers
    assert "GET" in res.headers["Allow"]
    assert "POST" in res.headers["Allow"]

@pytest.mark.asyncio
async def test_scenario_unhandled_exception_boundary(scenario_pipeline: ComposablePipelineService) -> None:
    async def faulty_dispatch(handler_name: str, body: bytes | None) -> dict:
        raise RuntimeError("Database connection severed mid-write")

    scenario_pipeline.stage_ingress._dispatcher.dispatch = faulty_dispatch  # type: ignore[assignment]
    req = IngressRequest(
        method="POST",
        path="/api/v1/work",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await scenario_pipeline.execute(req)
    assert res.status_code == 500
    assert res.problem_details is not None
    assert res.problem_details.status == 500
    assert res.problem_details.type.endswith("internal-error")
    assert res.problem_details.title == "Internal error"
    assert "Database connection severed" not in (res.problem_details.detail or "")
    assert res.context is not None
    assert res.context.is_failed is True
    assert res.context.rejection_reason == "internal_error"

@pytest.mark.asyncio
async def test_scenario_unsupported_media_type_boundary(scenario_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="POST",
        path="/api/v1/work",
        headers={
            "Authorization": "Bearer test-token-tenant1",
            "Content-Type": "application/xml",
        },
    )
    res = await scenario_pipeline.execute(req)
    assert res.status_code == 415
    assert res.problem_details is not None
    assert res.problem_details.status == 415
    assert res.problem_details.type.endswith("unsupported-media-type")
    assert res.problem_details.title == "Unsupported media type"
    assert res.context is not None
    assert res.context.rejection_reason == "unsupported_media_type"
