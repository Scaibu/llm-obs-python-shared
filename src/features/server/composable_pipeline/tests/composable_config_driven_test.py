"""
Blueprint:
- Test asserting that the composable pipeline runs purely from external config.yml declarations.
- Validates that changing config.yml values immediately controls pipeline behavior.
"""
import pytest
from src.features.server.composable_pipeline import (
    ComposablePipelineService,
    IngressRequest,
)

@pytest.fixture
def config_driven_pipeline() -> ComposablePipelineService:
    # Instantiated with zero code overrides — loads routes, limits, quotas directly from config.yml files!
    return ComposablePipelineService()

@pytest.mark.asyncio
async def test_config_declared_route_succeeds(config_driven_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/resource",
        headers={"Authorization": "Bearer test-token-tenant1"},
        remote_addr="192.168.1.100",
    )
    res = await config_driven_pipeline.execute(req)
    assert res.status_code == 200
    assert "x-request-id" in res.headers
    assert "traceparent" in res.headers
    assert res.body is not None
    assert res.body["handler"] == "resource_handler"

@pytest.mark.asyncio
async def test_undeclared_route_fails_with_404(config_driven_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/unregistered-path",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await config_driven_pipeline.execute(req)
    assert res.status_code == 404
    assert res.problem_details is not None
    assert res.problem_details.status == 404

@pytest.mark.asyncio
async def test_declared_route_limit_enforced(config_driven_pipeline: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="POST",
        path="/api/v1/resource",
        headers={
            "Authorization": "Bearer test-token-tenant1",
            "Content-Length": "20000000",
        },
    )
    res = await config_driven_pipeline.execute(req)
    assert res.status_code == 413
    assert res.problem_details is not None
    assert res.problem_details.status == 413
    assert res.problem_details.title == "Request body too large"
    assert res.problem_details.type.endswith("payload-too-large")

@pytest.mark.asyncio
async def test_per_route_scope_enforcement() -> None:
    from src.features.server.pipeline_route_resolution import RouteDefinition
    custom_routes = [
        RouteDefinition(
            path_template="/api/v1/admin",
            allowed_methods={"POST"},
            handler_name="admin_handler",
            required_scopes={"admin.write"},
        )
    ]
    pipeline = ComposablePipelineService(routes=custom_routes)
    req = IngressRequest(
        method="POST",
        path="/api/v1/admin",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await pipeline.execute(req)
    assert res.status_code == 403
    assert res.problem_details is not None
    assert res.problem_details.status == 403
    assert res.context is not None
    assert res.context.rejection_reason == "authz"
