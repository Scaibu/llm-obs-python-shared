"""
Blueprint:
- Regression tests for pipeline gap fixes:
  1. Stage 5 rejects oversized headers with 431.
  2. Stage 10 honours per-route min/max timeout.
  3. Rejection envelopes carry CORS headers for allowed origins only.
"""
import pytest
from src.features.server.composable_pipeline import ComposablePipelineService, IngressRequest
from src.features.server.pipeline_route_resolution import RouteDefinition


@pytest.fixture
def service() -> ComposablePipelineService:
    routes = [
        RouteDefinition(path_template="/api/v1/ping", allowed_methods={"GET"}, handler_name="h"),
        RouteDefinition(
            path_template="/api/v1/slow",
            allowed_methods={"GET"},
            handler_name="h",
            min_timeout_ms=500.0,
            max_timeout_ms=2000.0,
        ),
    ]
    return ComposablePipelineService(routes=routes)


@pytest.mark.asyncio
async def test_oversized_headers_rejected_with_431(service: ComposablePipelineService) -> None:
    req = IngressRequest(path="/api/v1/ping", headers={"x-big": "a" * 40000})
    resp = await service.execute(req)
    assert resp.status_code == 431
    assert resp.context.rejection_reason == "headers_too_large"


@pytest.mark.asyncio
async def test_route_min_timeout_fails_fast_with_504(service: ComposablePipelineService) -> None:
    req = IngressRequest(
        path="/api/v1/slow",
        headers={"authorization": "Bearer test-token-tenant1"},
        client_timeout_ms=300.0,
    )
    resp = await service.execute(req)
    assert resp.status_code == 504


@pytest.mark.asyncio
async def test_route_max_timeout_clamps_budget(service: ComposablePipelineService) -> None:
    req = IngressRequest(
        path="/api/v1/slow",
        headers={"authorization": "Bearer test-token-tenant1"},
        client_timeout_ms=9000.0,
    )
    resp = await service.execute(req)
    assert resp.context.allocated_deadline_ms == 2000.0


@pytest.mark.asyncio
async def test_rejection_includes_cors_header_for_allowed_origin(service: ComposablePipelineService) -> None:
    req = IngressRequest(path="/api/v1/ping", headers={"origin": "https://app.example.com"})
    resp = await service.execute(req)
    assert resp.status_code == 401
    assert resp.headers["access-control-allow-origin"] == "https://app.example.com"


@pytest.mark.asyncio
async def test_rejection_has_no_cors_header_without_origin(service: ComposablePipelineService) -> None:
    resp = await service.execute(IngressRequest(path="/api/v1/ping"))
    assert resp.status_code == 401
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_asgi_does_not_read_body_when_unauthenticated(service: ComposablePipelineService) -> None:
    from src.features.server.composable_pipeline import AsgiPipelineAdapter

    reads = 0

    async def receive() -> dict:
        nonlocal reads
        reads += 1
        return {"body": b"x", "more_body": False}

    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    scope = {"type": "http", "method": "GET", "path": "/api/v1/ping", "headers": [], "client": ("1.2.3.4", 1)}
    await AsgiPipelineAdapter(service)(scope, receive, send)
    assert sent[0]["status"] == 401
    assert reads == 0


@pytest.mark.asyncio
async def test_asgi_chunked_body_over_limit_rejected_with_413() -> None:
    from src.features.server.composable_pipeline import AsgiPipelineAdapter

    svc = ComposablePipelineService(routes=[
        RouteDefinition(path_template="/up", allowed_methods={"POST"}, handler_name="h", max_body_bytes=10)
    ])
    chunks = [{"body": b"a" * 8, "more_body": True}, {"body": b"a" * 8, "more_body": False}]

    async def receive() -> dict:
        return chunks.pop(0)

    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    scope = {
        "type": "http", "method": "POST", "path": "/up", "client": ("1.2.3.4", 1),
        "headers": [(b"authorization", b"Bearer test-token-tenant1"), (b"content-type", b"application/json")],
    }
    await AsgiPipelineAdapter(svc)(scope, receive, send)
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_idempotency_key_released_when_request_rejected_after_acquire() -> None:
    svc = ComposablePipelineService(routes=[
        RouteDefinition(
            path_template="/pay", allowed_methods={"POST"}, handler_name="h", idempotency_key_required=True
        )
    ])
    headers = {"idempotency-key": "retry-key-1"}
    first = await svc.execute(IngressRequest(method="POST", path="/pay", headers=headers))
    assert first.status_code == 401
    second = await svc.execute(IngressRequest(method="POST", path="/pay", headers=headers))
    assert second.status_code == 401
