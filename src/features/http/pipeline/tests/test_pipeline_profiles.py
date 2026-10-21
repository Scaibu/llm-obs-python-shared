import pytest
from src.features.http.pipeline.pipeline_runner import (
    HttpPipelineRunner,
    get_pipeline_runner,
)
from src.features.http.client.scalable_http_client import (
    PipelineHttpClient,
    ResilientHttpClient,
)
from src.features.http.pipeline.types import PipelineContext, RequestConfig

@pytest.mark.asyncio
async def test_temporal_worker_profile_steps() -> None:
    runner = get_pipeline_runner(profile="temporal_worker")
    step_names = [s.name for s in runner.steps]
    assert step_names == ["ContextIsolation", "CircuitBreaker"]

@pytest.mark.asyncio
async def test_internal_fast_profile_steps() -> None:
    runner = get_pipeline_runner(profile="internal_fast")
    step_names = [s.name for s in runner.steps]
    assert step_names == ["ContextIsolation"]

@pytest.mark.asyncio
async def test_api_service_profile_steps() -> None:
    runner = get_pipeline_runner(profile="api_service")
    step_names = [s.name for s in runner.steps]
    assert step_names == [
        "InputHardening",
        "SsrfValidation",
        "ContextIsolation",
        "CacheEval",
        "Singleflight",
        "CircuitBreaker",
        "RateLimit",
        "AdmissionControl",
    ]

@pytest.mark.asyncio
async def test_client_initialization_with_profiles() -> None:
    worker_client = ResilientHttpClient(profile="temporal_worker")
    assert worker_client.profile == "temporal_worker"
    assert len(worker_client.runner.steps) == 2
    assert [s.name for s in worker_client.runner.steps] == ["ContextIsolation", "CircuitBreaker"]

    api_client = ResilientHttpClient(profile="api_service")
    assert api_client.profile == "api_service"
    assert len(api_client.runner.steps) == 8

@pytest.mark.asyncio
async def test_temporal_worker_context_execution() -> None:
    runner = get_pipeline_runner(profile="temporal_worker")
    ctx = PipelineContext(
        config=RequestConfig(
            method="POST",
            url="https://internal-service/api/v1/forecast",
            headers={"x-tenant-id": "custom-tenant"},
        ),
        tenant_id="tenant-activity-456",
        principal_id="worker-principal-789",
        target_class="declared_upstream",
    )
    result = await runner.run(ctx)
    assert result.tenant_id == "tenant-activity-456"
    assert result.config.headers["x-tenant-id"] == "tenant-activity-456"

@pytest.mark.asyncio
async def test_custom_string_step_names_resolution() -> None:
    runner = HttpPipelineRunner(steps=["context_isolation", "circuit_breaker"])
    assert len(runner.steps) == 2
    assert [s.name for s in runner.steps] == ["ContextIsolation", "CircuitBreaker"]

@pytest.mark.asyncio
async def test_client_custom_step_override() -> None:
    client = ResilientHttpClient(steps=["context_isolation"])
    assert len(client.runner.steps) == 1
    assert client.runner.steps[0].name == "ContextIsolation"

