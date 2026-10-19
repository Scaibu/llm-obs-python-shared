import pytest
from src.features.server.composable_pipeline import (
    AsgiPipelineAdapter,
    ComposablePipelineService,
    IngressRequest,
)
from src.features.server.composable_pipeline.contracts.pipeline_constants import (
    PipelineHeaders,
    PipelineRejectionReasons,
    ProblemTypeSlugs,
)
from src.features.server.pipeline_route_resolution import RouteDefinition
from src.features.server.composable_pipeline.infrastructure.adapters.distributed_redis_idempotency_store_adapter import (
    DistributedRedisIdempotencyStoreAdapter,
)
from src.features.server.composable_pipeline.infrastructure.adapters.distributed_redis_tenant_quota_adapter import (
    DistributedRedisTenantQuotaAdapter,
)


@pytest.fixture
def e2e_pipeline() -> ComposablePipelineService:
    routes = [
        RouteDefinition(
            path_template="/api/v1/checkout",
            allowed_methods={"POST"},
            handler_name="checkout_handler",
            required_scopes={"write"},
            max_body_bytes=512,
            allowed_media_types=["application/json"],
            idempotency_key_required=True,
        ),
        RouteDefinition(
            path_template="/api/v1/status",
            allowed_methods={"GET"},
            handler_name="status_handler",
            required_scopes={"read"},
            max_body_bytes=0,
            allowed_media_types=["application/json"],
        ),
        RouteDefinition(
            path_template="/api/v1/killswitch-target",
            allowed_methods={"GET", "POST"},
            handler_name="disabled_handler",
            disabled=True,
        ),
    ]
    return ComposablePipelineService(
        routes=routes,
        idempotency_store=DistributedRedisIdempotencyStoreAdapter(redis_client=None),
        quota_port=DistributedRedisTenantQuotaAdapter(redis_client=None),
    )


@pytest.mark.asyncio
async def test_e2e_complete_successful_checkout_flow(e2e_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="POST",
        path="/api/v1/checkout",
        headers={
            PipelineHeaders.AUTHORIZATION: "Bearer test-token-tenant1",
            PipelineHeaders.CONTENT_TYPE: "application/json",
            PipelineHeaders.IDEMPOTENCY_KEY: "chk-uuid-88889999",
        },
        body=b'{"cart_id": "cart_123", "amount": 99.50}',
        remote_addr="10.20.0.15",
    )
    res = await e2e_pipeline.execute(req)
    assert res.status_code == 200
    assert res.body is not None
    assert res.problem_details is None
    assert res.context is not None
    assert res.context.current_stage_index == 12
    assert len(res.context.stage_execution_trail) == 12
    assert PipelineHeaders.REQUEST_ID in res.headers
    assert PipelineHeaders.TRACEPARENT in res.headers


@pytest.mark.asyncio
async def test_e2e_rtl_proxy_traversal_ip_resolution(e2e_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/status",
        headers={
            PipelineHeaders.AUTHORIZATION: "Bearer test-token-tenant1",
            PipelineHeaders.X_FORWARDED_FOR: "203.0.113.195, 10.20.0.10",
        },
        remote_addr="10.20.0.1",
    )
    res = await e2e_pipeline.execute(req)
    assert res.status_code == 200
    assert res.context is not None
    assert res.context.resolved_peer_ip == "203.0.113.195"


@pytest.mark.asyncio
async def test_e2e_path_traversal_and_encoded_slash_attack(e2e_pipeline: ComposablePipelineService) -> None:
    dot_req = IngressRequest(method="GET", path="/api/v1/../secret")
    dot_res = await e2e_pipeline.execute(dot_req)
    assert dot_res.status_code == 400
    assert dot_res.problem_details is not None
    assert dot_res.problem_details.type.endswith(ProblemTypeSlugs.INVALID_PATH)

    encoded_req = IngressRequest(method="GET", path="/api/v1%2Fresource")
    encoded_res = await e2e_pipeline.execute(encoded_req)
    assert encoded_res.status_code == 400
    assert encoded_res.problem_details is not None
    assert encoded_res.problem_details.type.endswith(ProblemTypeSlugs.INVALID_PATH)


@pytest.mark.asyncio
async def test_e2e_cors_preflight_and_browser_origin_rejection() -> None:
    pipeline = ComposablePipelineService()
    pipeline.allowed_origins = ["https://app.verified.com"]

    forbidden_req = IngressRequest(
        method="GET",
        path="/api/v1/resource",
        headers={PipelineHeaders.ORIGIN: "https://evil-attacker.com"},
    )
    forbidden_res = await pipeline.execute(forbidden_req)
    assert forbidden_res.status_code == 403
    assert forbidden_res.problem_details is not None
    assert forbidden_res.problem_details.type.endswith(ProblemTypeSlugs.CORS_FORBIDDEN)

    allowed_preflight = IngressRequest(
        method="OPTIONS",
        path="/api/v1/resource",
        headers={
            PipelineHeaders.ORIGIN: "https://app.verified.com",
            PipelineHeaders.ACCESS_CONTROL_REQUEST_METHOD: "POST",
        },
    )
    preflight_res = await pipeline.execute(allowed_preflight)
    assert preflight_res.status_code == 204
    assert preflight_res.headers.get(PipelineHeaders.ACCESS_CONTROL_ALLOW_ORIGIN) == "https://app.verified.com"
    assert PipelineHeaders.ACCESS_CONTROL_ALLOW_METHODS in preflight_res.headers


@pytest.mark.asyncio
async def test_e2e_csrf_browser_mutating_protection() -> None:
    pipeline = ComposablePipelineService()
    pipeline.csrf_enabled = True

    unprotected_req = IngressRequest(
        method="POST",
        path="/api/v1/resource",
        headers={PipelineHeaders.ORIGIN: "https://app.verified.com"},
    )
    unprotected_res = await pipeline.execute(unprotected_req)
    assert unprotected_res.status_code == 403
    assert unprotected_res.problem_details is not None
    assert unprotected_res.problem_details.type.endswith(ProblemTypeSlugs.CSRF_INVALID)


@pytest.mark.asyncio
async def test_e2e_idempotency_concurrent_duplicate_collision(e2e_pipeline: ComposablePipelineService) -> None:
    first_req = IngressRequest(
        method="POST",
        path="/api/v1/checkout",
        headers={
            PipelineHeaders.AUTHORIZATION: "Bearer test-token-tenant1",
            PipelineHeaders.CONTENT_TYPE: "application/json",
            PipelineHeaders.IDEMPOTENCY_KEY: "collision-key-999",
        },
        body=b'{"cart_id": "cart_1"}',
    )
    first_res = await e2e_pipeline.execute(first_req)
    assert first_res.status_code == 200

    collision_req = IngressRequest(
        method="POST",
        path="/api/v1/checkout",
        headers={
            PipelineHeaders.AUTHORIZATION: "Bearer test-token-tenant1",
            PipelineHeaders.CONTENT_TYPE: "application/json",
            PipelineHeaders.IDEMPOTENCY_KEY: "collision-key-999",
        },
        body=b'{"cart_id": "cart_1"}',
    )
    collision_res = await e2e_pipeline.execute(collision_req)
    assert collision_res.status_code == 409
    assert collision_res.problem_details is not None
    assert collision_res.problem_details.type.endswith(ProblemTypeSlugs.IDEMPOTENCY_CONFLICT)


@pytest.mark.asyncio
async def test_e2e_kill_switch_route_disabled(e2e_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/killswitch-target",
    )
    res = await e2e_pipeline.execute(req)
    assert res.status_code == 503
    assert res.problem_details is not None
    assert res.problem_details.type.endswith(ProblemTypeSlugs.ROUTE_DISABLED)


@pytest.mark.asyncio
async def test_e2e_asgi_full_cycle_streaming_and_headers(e2e_pipeline: ComposablePipelineService) -> None:
    adapter = AsgiPipelineAdapter(e2e_pipeline)
    events: list[dict] = []

    async def mock_receive() -> dict:
        return {"body": b'{"cart_id":"stream_cart"}', "more_body": False}

    async def mock_send(event: dict) -> None:
        events.append(event)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/checkout",
        "headers": [
            (b"authorization", b"Bearer test-token-tenant1"),
            (b"content-type", b"application/json"),
            (b"idempotency-key", b"asgi-stream-key-777"),
        ],
        "client": ("10.20.0.50", 45678),
    }

    await adapter(scope, mock_receive, mock_send)
    assert len(events) == 2
    assert events[0]["type"] == "http.response.start"
    assert events[0]["status"] == 200
    headers_dict = dict(events[0]["headers"])
    assert b"content-type" in headers_dict
    assert b"x-request-id" in headers_dict
    assert events[1]["type"] == "http.response.body"
