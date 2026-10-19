"""
Blueprint:
- End-to-end unit tests for ComposablePipelineService verifying 12-stage sequential execution.
"""
import pytest
from src.features.server.composable_pipeline import (
    ComposablePipelineService,
    IngressRequest,
)
from src.features.server.pipeline_route_resolution import RouteDefinition

@pytest.fixture
def test_pipeline() -> ComposablePipelineService:
    routes = [
        RouteDefinition(
            path_template="/api/v1/resource",
            allowed_methods={"GET", "POST"},
            handler_name="resource_handler",
        )
    ]
    return ComposablePipelineService(routes=routes)

@pytest.mark.asyncio
async def test_pipeline_success_flow(test_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/resource",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr="192.168.1.100",
    )
    res = await test_pipeline.execute(req)
    assert res.status_code == 200
    assert "x-request-id" in res.headers
    assert "traceparent" in res.headers
    assert res.body is not None
    assert res.body["status"] == "success"
    assert res.context is not None
    assert res.context.current_stage_index == 12
    assert res.context.current_stage_name == "pipeline_handler_ingress"
    assert len(res.context.stage_execution_trail) == 12
    assert res.context.tenant_id == "tenant1"
    assert res.context.principal_id == "user-tenant1"
    assert res.context.resolved_peer_ip == "192.168.1.100"

@pytest.mark.asyncio
async def test_pipeline_unauthenticated_flow(test_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/resource",
        headers={},
        remote_addr="192.168.1.100",
    )
    res = await test_pipeline.execute(req)
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert res.problem_details is not None
    assert res.problem_details.status == 401
    assert res.context is not None
    assert res.context.is_failed is True
    assert res.context.rejection_reason == "auth"
    assert res.context.current_stage_index == 7

@pytest.mark.asyncio
async def test_pipeline_route_not_found(test_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/unknown",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await test_pipeline.execute(req)
    assert res.status_code == 404
    assert res.problem_details is not None
    assert res.problem_details.status == 404
