# ADR 0001: Declarative Feature HTTP Configuration (`http-config.yml`) and Composable Pipeline Client Usage

- **Status:** Accepted
- **Date:** 2026-10-21
- **Scope:** `python-shared` (`features/http`), Monorepo Microservices (All Domain Features)
- **Author:** Antigravity Platform Engineering & Architecture Guild

---

## 1. Context and Problem Statement

Microservices across the monorepo previously used ad-hoc, divergent HTTP invocation patterns:
- Raw, unmonitored `httpx.Client()` or `httpx.AsyncClient()` calls without centralized timeout budgets or keep-alive pooling.
- Inconsistent retry policies and lack of circuit breaking across internal cluster boundaries.
- Context dropping where W3C `traceparent`, `x-request-id`, and tenant isolation headers (`x-tenant-id`, `x-principal-id`) failed to propagate across outbound network calls.
- Mismatched execution models: Temporal activities were exposed to aggressive in-memory bulkheads and rate-limiters designed for API endpoints, causing worker thread starvation.

We require a unified, declarative, per-feature configuration file (`http-config.yml`) and an accompanying resilient HTTP client that automatically binds to process-model execution profiles while supporting feature-specific tuning.

---

## 2. Decision Outcome

We standardize on a declarative, per-feature configuration file named **`http-config.yml`** placed directly inside each domain feature folder (`src/features/<feature>/http-config.yml`), paired with `python-shared/src/features/http`'s **`ResilientHttpClient`** (`PipelineHttpClient`).

### Key Capabilities
1. **Per-Feature Isolation**: Every feature declares its own timeouts, connection pool parameters, and pipeline steps in its local `http-config.yml`.
2. **Process-Model Profiles**:
   - `api_service`: Full 8-step pipeline (`input_hardening`, `ssrf_validation`, `context_isolation`, `cache_eval`, `singleflight`, `circuit_breaker`, `rate_limit`, `admission_control`).
   - `temporal_worker`: Lean 2-step pipeline (`context_isolation`, `circuit_breaker`), leaving concurrency and retry management to the Temporal engine.
   - `internal_fast`: Ultra-low overhead 1-step pipeline (`context_isolation`) for high-throughput cluster-internal SDK calls.
3. **Single-Line Zero-Boilerplate Loading**:
   ```python
   client = ResilientHttpClient.from_config("src/features/my_feature")
   ```

---

## 3. Schema Specification: `http-config.yml`

Below is the complete structural contract for `http-config.yml`:

```yaml
schema_version: "1.0.0"
feature_name: "quality_baseline"
profile: "api_service" # Options: api_service | temporal_worker | internal_fast

client:
  timeout_seconds: 30.0          # Maximum wall-clock time for total request lifecycle
  connect_timeout_seconds: 5.0   # TCP connect & TLS handshake deadline
  max_connections: 100           # Maximum total concurrent connections in client pool
  max_keepalive_connections: 20  # Idle connections retained in keepalive pool
  keepalive_expiry_seconds: 30.0 # Time before an idle keepalive connection is evicted
  verify_ssl: true               # Enable/disable TLS certificate authority verification
  retries: 3                     # Number of connection/transport level retry attempts

pipeline:
  steps:                         # Explicit pipeline execution order (overrides profile default if present)
    - input_hardening
    - ssrf_validation
    - context_isolation
    - cache_eval
    - singleflight
    - circuit_breaker
    - rate_limit
    - admission_control

  circuit_breaker:
    failure_threshold: 5         # Consecutive 5xx/timeout errors before tripping circuit to OPEN
    recovery_timeout_seconds: 30.0 # Duration circuit stays OPEN before entering HALF-OPEN probe state
    half_open_requests: 3        # Number of successful trial requests before resetting to CLOSED

  rate_limit:
    requests_per_second: 100     # Leaky-bucket / token-bucket refill rate
    burst: 200                   # Maximum burst token capacity

  cache_eval:
    enabled: true                # Enable in-memory or Redis response caching
    default_ttl_seconds: 60      # Cache expiration TTL

  security:
    input_hardening: true        # Enforce header and path injection sanitization
    ssrf_validation: true        # Block private IP ranges (RFC 1918) from outbound user URLs
```

### Field Definitions & Constraints

| Field Path | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `schema_version` | `string` | `"1.0.0"` | SemVer format | Version of the configuration schema. |
| `feature_name` | `string` | Directory name | Snake-case identifier | Name of the owning domain feature. |
| `profile` | `string` | `"api_service"` | `api_service`, `temporal_worker`, `internal_fast` | Target execution profile governing active pipeline steps. |
| `client.timeout_seconds` | `float` | `30.0` | `0.1` to `300.0` | Maximum request duration before `TimeoutError`. |
| `client.connect_timeout_seconds` | `float` | `5.0` | `0.1` to `30.0` | Transport socket connect deadline. |
| `client.max_connections` | `int` | `100` | `> 0` | Total connection pool ceiling. |
| `client.max_keepalive_connections`| `int` | `20` | `<= max_connections` | Reusable pooled TCP connection slots. |
| `client.verify_ssl` | `bool` | `true` | Boolean | Enforces TLS trust chain validation. |
| `pipeline.steps` | `list[str]` | Profile derived | Registered step names | Explicit list of pipeline steps to execute in sequence. |
| `pipeline.circuit_breaker.failure_threshold` | `int` | `5` | `1` to `100` | Failures required to trip the circuit. |
| `pipeline.circuit_breaker.recovery_timeout_seconds` | `float` | `30.0` | `1.0` to `300.0` | Sleep duration before testing backend recovery. |
| `pipeline.rate_limit.requests_per_second` | `int` | `100` | `> 0` | Rate limiter token refill rate. |

---

## 4. Comprehensive Operations & Implementation Manual

### 1. Creating `http-config.yml` for an API Feature
For an outbound HTTP client in a high-concurrency API microservice:

```bash
cat << 'EOF' > src/features/score_composite/http-config.yml
schema_version: "1.0.0"
feature_name: "score_composite"
profile: "api_service"

client:
  timeout_seconds: 30.0
  connect_timeout_seconds: 5.0
  max_connections: 100
  max_keepalive_connections: 20
  keepalive_expiry_seconds: 30.0
  verify_ssl: true
  retries: 3

pipeline:
  steps:
    - input_hardening
    - ssrf_validation
    - context_isolation
    - cache_eval
    - singleflight
    - circuit_breaker
    - rate_limit
    - admission_control
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 30.0
    half_open_requests: 3
  rate_limit:
    requests_per_second: 100
    burst: 200
  cache_eval:
    enabled: true
    default_ttl_seconds: 60
  security:
    input_hardening: true
    ssrf_validation: true
EOF
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
import yaml
with open('src/features/score_composite/http-config.yml') as f:
    cfg = yaml.safe_load(f)
assert cfg['profile'] == 'api_service'
assert len(cfg['pipeline']['steps']) == 8
print('HTTP config syntax valid!')
"
```

---

### 2. Creating `http-config.yml` for a Temporal Worker Feature
Temporal activities manage their own retry loops and timeout heartbeats. A lean 2-step pipeline avoids duplicate retries and bulkhead deadlocks:

```bash
cat << 'EOF' > src/features/forecast/http-config.yml
schema_version: "1.0.0"
feature_name: "forecast"
profile: "temporal_worker"

client:
  timeout_seconds: 60.0
  connect_timeout_seconds: 5.0
  max_connections: 50
  max_keepalive_connections: 10
  keepalive_expiry_seconds: 30.0
  verify_ssl: true
  retries: 2

pipeline:
  steps:
    - context_isolation
    - circuit_breaker
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 30.0
    half_open_requests: 3
EOF
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
import yaml
with open('src/features/forecast/http-config.yml') as f:
    cfg = yaml.safe_load(f)
assert cfg['profile'] == 'temporal_worker'
assert cfg['pipeline']['steps'] == ['context_isolation', 'circuit_breaker']
print('Temporal worker HTTP config syntax valid!')
"
```

---

### 3. Using `ResilientHttpClient` in a Hexagonal Outbound Adapter
In accordance with Rule 1 (`1-feature-folder-writing-rule.md`), domain logic remains in `service/`, while external HTTP calls reside strictly in `infrastructure/adapters/`:

```python
from pathlib import Path
from typing import Dict, Any
from python_shared.http import ResilientHttpClient
from src.infra.ports.external_scorer_port import ExternalScorerPort

class HttpScorerAdapter(ExternalScorerPort):
    def __init__(self, base_url: str = "http://scorer-service:8000") -> None:
        feature_dir = Path(__file__).resolve().parents[2]
        self._client = ResilientHttpClient.from_config(
            config_path=feature_dir,
            base_url=base_url
        )

    async def score_text(self, text: str, tenant_id: str) -> Dict[str, Any]:
        response = await self._client.execute_async(
            method="POST",
            url="/api/v1/score",
            json={"text": text},
            tenant_id=tenant_id
        )
        response.raise_for_status()
        return response.json()
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
from python_shared.http import ResilientHttpClient
client = ResilientHttpClient.from_config('quality-engine/src/features/quality_baseline')
assert client.profile == 'api_service'
assert client.timeout == 30.0
assert len(client.runner.steps) == 8
print('Successfully instantiated client with 8-step pipeline!')
"
```

---

### 4. Executing Synchronous Calls (Worker / Batch Context)
While `execute_async` is preferred for async frameworks, `execute` provides synchronous execution with identical pipeline guarantees:

```python
from python_shared.http import ResilientHttpClient

client = ResilientHttpClient.from_config("src/features/my_feature")
response = client.execute(
    method="GET",
    url="https://api.internal/v1/health",
    headers={"Accept": "application/json"}
)
print("Status:", response.status_code)
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
from python_shared.http import ResilientHttpClient
client = ResilientHttpClient(base_url='https://httpbin.org', profile='internal_fast')
resp = client.execute('GET', '/get')
assert resp.status_code == 200
print('Synchronous execution verified!')
"
```

---

## 5. Failure Diagnosis & Resolution Matrix

| Symptom / Error | Root Cause | Diagnosis Command | Corrective Action |
|---|---|---|---|
| `ModuleNotFoundError: No module named 'src.features.http'` | Broken PEP 420 namespace packaging caused by `src/features/__init__.py`. | `po file-search --root . --pattern "__init__.py"` | Delete `src/__init__.py` and `src/features/__init__.py`. Use `from python_shared.http import ResilientHttpClient`. |
| `CircuitBreakerOpenException` | Downstream service returned >5 consecutive 5xx errors within recovery window. | Inspect active circuit breaker state in pipeline context. | Check downstream service health logs. If downstream is healthy, wait for `recovery_timeout_seconds` to lapse into half-open. |
| `RateLimitExceededException (429)` | Outbound traffic exceeded `requests_per_second` burst bucket. | Check client call rate against `http-config.yml`. | Increase `rate_limit.requests_per_second` and `burst` in `http-config.yml`. |
| Worker thread freeze in Temporal activities | Using `api_service` profile inside Temporal activities, triggering in-memory bulkheads. | Inspect `profile` in `http-config.yml`. | Change `profile: "api_service"` to `profile: "temporal_worker"`. |
| Missing W3C `traceparent` downstream | Request invoked without initializing context isolation step. | Verify `context_isolation` is present in `pipeline.steps`. | Ensure `context_isolation` step is included in `pipeline.steps`. |
