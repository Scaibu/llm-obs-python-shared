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
