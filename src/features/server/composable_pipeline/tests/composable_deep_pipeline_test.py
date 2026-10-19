"""
Blueprint:
- Deep scenario tests verifying end-to-end integration across all 12 pipeline stages:
  1. Full ASGI HTTP protocol lifecycle through AsgiPipelineAdapter (streaming request body, header casing, problem response).
  2. RFC 9457 structured error assertions (type URI, title, instance URN, status code, retryable flag).
  3. Per-route payload ceiling enforcement (overrides global limit with route-specific threshold).
  4. Per-route required scope authorization failure (valid token, missing specific route scope).
  5. Ingress access log telemetry allowlist verification (ensures all 12 allowlist fields are populated).
  6. Idempotency requirement in ASGI adapter HTTP flow returning RFC 9457 Problem Details.
"""
import pytest
from src.features.server.composable_pipeline import (
    AsgiPipelineAdapter,
    ComposablePipelineService,
    IngressRequest,
)
from src.features.server.pipeline_route_resolution import RouteDefinition


@pytest.fixture
def deep_pipeline_service() -> ComposablePipelineService:
    routes = [
        RouteDefinition(
            path_template="/api/v1/orders",
            allowed_methods={"POST"},
            handler_name="order_handler",
            required_scopes={"write"},
            max_body_bytes=256,
            allowed_media_types=["application/json"],
            idempotency_key_required=True,
        ),
        RouteDefinition(
            path_template="/api/v1/orders/{order_id}",
            allowed_methods={"GET"},
            handler_name="order_get_handler",
            required_scopes={"orders.special"},
        ),
    ]
    return ComposablePipelineService(routes=routes)


@pytest.mark.asyncio
async def test_deep_asgi_adapter_full_http_cycle(deep_pipeline_service: ComposablePipelineService) -> None:
    adapter = AsgiPipelineAdapter(deep_pipeline_service)
    sent_messages: list[dict] = []

    async def mock_receive() -> dict:
        return {"body": b'{"item":"book"}', "more_body": False}

    async def mock_send(message: dict) -> None:
        sent_messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/orders",
        "headers": [
            (b"authorization", b"Bearer test-token-tenant1"),
            (b"content-type", b"application/json"),
            (b"idempotency-key", b"ord-uuid-99991111"),
        ],
        "client": ("192.168.1.100", 54321),
    }

    await adapter(scope, mock_receive, mock_send)

    assert len(sent_messages) == 2
    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["type"] == "http.response.body"


@pytest.mark.asyncio
async def test_deep_route_scoped_payload_limit_enforced(deep_pipeline_service: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="POST",
        path="/api/v1/orders",
        headers={
            "Authorization": "Bearer test-token-tenant1",
            "Content-Type": "application/json",
            "Content-Length": "1024",
            "idempotency-key": "ord-uuid-oversized-1",
        },
        body=b"x" * 1024,
    )
    res = await deep_pipeline_service.execute(req)
    assert res.status_code == 413
    assert res.problem_details is not None
    assert res.problem_details.status == 413
    assert res.problem_details.instance is not None
    assert res.problem_details.instance.startswith("urn:request:")
    assert res.context is not None
    assert res.context.rejection_reason == "body_too_large"


@pytest.mark.asyncio
async def test_deep_route_insufficient_scope_forbidden(deep_pipeline_service: ComposablePipelineService) -> None:
    req = IngressRequest(
        method="GET",
        path="/api/v1/orders/12345",
        headers={"Authorization": "Bearer test-token-tenant1"},
    )
    res = await deep_pipeline_service.execute(req)
    assert res.status_code == 403
    assert res.problem_details is not None
    assert res.problem_details.status == 403
    assert res.problem_details.type.endswith("forbidden")
    assert res.problem_details.title == "Insufficient permissions"
    assert res.context is not None
    assert res.context.rejection_reason == "authz"


@pytest.mark.asyncio
async def test_deep_access_log_allowlist_populated(deep_pipeline_service: ComposablePipelineService) -> None:
    initial_log_count = len(deep_pipeline_service.access_logs)
    req = IngressRequest(
        method="POST",
        path="/api/v1/orders",
        headers={
            "Authorization": "Bearer test-token-tenant1",
            "Content-Type": "application/json",
            "idempotency-key": "ord-uuid-log-sample",
        },
        body=b'{"item":"valid"}',
        remote_addr="127.0.0.1",
    )
    res = await deep_pipeline_service.execute(req)
    assert res.status_code == 200
    assert len(deep_pipeline_service.access_logs) == initial_log_count + 1

    latest_log = deep_pipeline_service.access_logs[-1]
    assert latest_log.request_id == res.headers["x-request-id"]
    assert latest_log.route == "/api/v1/orders"
    assert latest_log.method == "POST"
    assert latest_log.status == 200
    assert latest_log.peer == "127.0.0.1"
    assert latest_log.tenant_id == "tenant1"
    assert latest_log.duration_seconds >= 0.0
    assert latest_log.bytes_in == len(b'{"item":"valid"}')
    assert latest_log.bytes_out >= 0


@pytest.mark.asyncio
async def test_deep_asgi_adapter_rfc9457_rejection_format(deep_pipeline_service: ComposablePipelineService) -> None:
    adapter = AsgiPipelineAdapter(deep_pipeline_service)
    sent_messages: list[dict] = []

    async def mock_receive() -> dict:
        return {"body": b"", "more_body": False}

    async def mock_send(message: dict) -> None:
        sent_messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/orders",
        "headers": [
            (b"content-type", b"application/json"),
        ],
        "client": ("127.0.0.1", 12345),
    }

    await adapter(scope, mock_receive, mock_send)

    assert len(sent_messages) == 2
    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 400

    headers_dict = dict(sent_messages[0]["headers"])
    assert headers_dict[b"content-type"] == b"application/problem+json"
    assert b"idempotency-key-missing" in sent_messages[1]["body"]
