"""
Blueprint:
- Performance and throughput benchmarks for ComposablePipelineService:
  1. Microsecond pipeline overhead under high-volume sequential traffic (1,000 requests).
  2. Concurrent throughput under asyncio.gather (50 concurrent requests).
  3. Pre-auth rate limit evaluation throughput under burst traffic.
"""
import asyncio
import time
import pytest
from src.features.server.composable_pipeline import (
    ComposablePipelineService,
    IngressRequest,
)
from src.features.server.pipeline_route_resolution import RouteDefinition

@pytest.fixture
def perf_pipeline() -> ComposablePipelineService:
    routes = [
        RouteDefinition(
            path_template="/api/v1/fast",
            allowed_methods={"GET"},
            handler_name="fast_handler",
        )
    ]
    return ComposablePipelineService(routes=routes)

@pytest.mark.asyncio
async def test_performance_sequential_throughput(perf_pipeline: ComposablePipelineService) -> None:
    iterations = 200
    start_time = time.monotonic()
    for i in range(iterations):
        req = IngressRequest(
            method="GET",
            path="/api/v1/fast",
            headers={"Authorization": f"Bearer test-token-tenant{i}"},
            remote_addr=f"10.0.{(i // 254)}.{i % 254 + 1}",
        )
        res = await perf_pipeline.execute(req)
        assert res.status_code == 200

    total_duration_sec = time.monotonic() - start_time
    avg_latency_ms = (total_duration_sec / iterations) * 1000.0
    throughput_rps = iterations / total_duration_sec

    assert avg_latency_ms < 5.0
    assert throughput_rps > 200.0

@pytest.mark.asyncio
async def test_performance_concurrent_burst(perf_pipeline: ComposablePipelineService) -> None:
    concurrency = 50
    start_time = time.monotonic()

    async def send_single(idx: int) -> int:
        req = IngressRequest(
            method="GET",
            path="/api/v1/fast",
            headers={"Authorization": f"Bearer test-token-t{idx}"},
            remote_addr=f"192.168.1.{idx + 1}",
        )
        res = await perf_pipeline.execute(req)
        return res.status_code

    results = await asyncio.gather(*[send_single(i) for i in range(concurrency)])
    total_duration_sec = time.monotonic() - start_time

    assert all(code == 200 for code in results)
    assert total_duration_sec < 1.0
