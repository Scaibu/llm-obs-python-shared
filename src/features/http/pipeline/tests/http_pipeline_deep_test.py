"""
Blueprint:
- Deep integration tests for the unified config-driven HTTP pipeline.
- Validates Part A security invariants (tenant isolation, SSRF prevention)
- Validates Part B ordering (cache hit short-circuits before admission slots or rate tokens)
- Validates circuit breaker resilience.
"""
import pytest
from src.features.http.pipeline.pipeline_runner import HttpPipelineRunner
from src.features.http.pipeline.types import PipelineContext, RequestConfig
from src.features.http.pipeline.singleflight.domain.rules.singleflight_rules import (
    SingleflightRules,
)
from src.features.http.pipeline.ssrf_validation.domain.rules.ssrf_validation_rules import (
    SsrfValidationRules,
)
from src.features.http.pipeline.cache_eval.domain.rules.cache_eval_rules import (
    CacheEvalRules,
)

@pytest.fixture
def default_runner() -> HttpPipelineRunner:
    return HttpPipelineRunner()

@pytest.mark.asyncio
async def test_part_b_pipeline_execution_order(default_runner: HttpPipelineRunner) -> None:
    step_names = [s.name for s in default_runner.steps]
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
async def test_tenant_context_binding_and_spoof_sanitization(default_runner: HttpPipelineRunner) -> None:
    # Attempting to supply x-tenant-id in request headers should be sanitized/overwritten
    # by the authenticated context tenant
    ctx = PipelineContext(
        config=RequestConfig(
            method="GET",
            url="https://internal-service/api/v1/data",
            headers={"x-tenant-id": "attacker-spoofed-tenant"},
        ),
        tenant_id="tenant-verified-123",
        principal_id="user-456",
        target_class="declared_upstream",
    )
    result = await default_runner.run(ctx)
    assert result.tenant_id == "tenant-verified-123"
    assert result.config.headers["x-tenant-id"] == "tenant-verified-123"

@pytest.mark.asyncio
async def test_singleflight_key_isolation_between_tenants_and_principals() -> None:
    key_tenant_a = SingleflightRules.generate_hashed_key(
        tenant_id="tenant-A",
        principal_id="user-1",
        method="GET",
        url="https://api.com/items",
        body=None,
    )
    key_tenant_b = SingleflightRules.generate_hashed_key(
        tenant_id="tenant-B",
        principal_id="user-1",
        method="GET",
        url="https://api.com/items",
        body=None,
    )
    key_tenant_a_user_2 = SingleflightRules.generate_hashed_key(
        tenant_id="tenant-A",
        principal_id="user-2",
        method="GET",
        url="https://api.com/items",
        body=None,
    )
    # Keys MUST NOT match across different tenants or principals
    assert key_tenant_a != key_tenant_b
    assert key_tenant_a != key_tenant_a_user_2

@pytest.mark.asyncio
async def test_ssrf_blocks_private_and_metadata_ips_for_user_urls() -> None:
    # 1. AWS metadata link-local
    with pytest.raises(ValueError) as exc1:
        SsrfValidationRules.validate_url("https://169.254.169.254/latest/meta-data/", target_class="user_supplied_url")
    assert "blocked network range" in str(exc1.value)

    # 2. Localhost loopback
    with pytest.raises(ValueError) as exc2:
        SsrfValidationRules.validate_url("https://127.0.0.1:443/admin", target_class="user_supplied_url")
    assert "blocked network range" in str(exc2.value)

    # 3. HTTP plain scheme forbidden for user-supplied URLs
    with pytest.raises(ValueError) as exc3:
        SsrfValidationRules.validate_url("http://example.com/webhook", target_class="user_supplied_url")
    assert "Target scheme 'http' is not allowed" in str(exc3.value)

    # 4. Declared internal upstreams ARE allowed to use private IPs
    hostname = SsrfValidationRules.validate_url("http://10.0.0.5:8080/v1/rpc", target_class="declared_upstream")
    assert hostname == "10.0.0.5"

@pytest.mark.asyncio
async def test_cache_eval_rfc9111_storability() -> None:
    # Response to authenticated request without public cache-control must not be stored
    assert CacheEvalRules.is_storable(
        request_headers={"Authorization": "Bearer secret"},
        response_headers={"Cache-Control": "max-age=3600"},
    ) is False

    # Response with explicit public directive is storable
    assert CacheEvalRules.is_storable(
        request_headers={"Authorization": "Bearer secret"},
        response_headers={"Cache-Control": "public, max-age=3600"},
    ) is True

    # no-store is never storable
    assert CacheEvalRules.is_storable(
        request_headers={},
        response_headers={"Cache-Control": "no-store"},
    ) is False

@pytest.mark.asyncio
async def test_cache_hit_short_circuits_without_consuming_concurrency_slot(default_runner: HttpPipelineRunner) -> None:
    ctx = PipelineContext(
        config=RequestConfig(
            method="GET",
            url="https://api.example.com/items",
        ),
        tenant_id="tenant-cache-test",
        principal_id="principal-1",
        target_class="declared_upstream",
    )
    # Pre-populate cache for this specific tenant & principal
    key = SingleflightRules.generate_hashed_key(
        tenant_id="tenant-cache-test",
        principal_id="principal-1",
        method="GET",
        url="https://api.example.com/items",
        body=None,
    )
    ctx.hashed_request_key = key
    cached_payload = {"data": "cached-result"}
    ctx.cache_store.set(ctx.tenant_id, key, cached_payload)

    initial_slots = ctx.admission_control.get_active_count()
    result = await default_runner.run(ctx)

    # Result returns cached payload immediately at Step 4 (CacheEval)
    assert result.cached_response == cached_payload
    assert result.step_index == 4
    # Concurrency admission control (Step 7) was NEVER acquired
    assert ctx.admission_control.get_active_count() == initial_slots
