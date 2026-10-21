# ADR 0002: Declarative Feature Server Configuration (`server-config.yml`) and FastAPI Middleware Lifecycle Usage

- **Status:** Accepted
- **Date:** 2026-10-21
- **Scope:** `python-shared` (`features/server`), Monorepo Microservices (All FastAPI Services)
- **Author:** Antigravity Platform Engineering & Architecture Guild

---

## 1. Context and Problem Statement

Across the monorepo's 16 microservices, FastAPI server setup and network configurations suffered from significant inconsistencies:
- Hardcoded host and port arguments in `uvicorn.run()` without centralized network policy bounds.
- Missing correlation and telemetry middleware, resulting in dropped W3C `traceparent` headers and untraced HTTP request lifecycles.
- Undefined connection caps, body size limits, and timeout parameters, leaving services vulnerable to slowloris attacks and memory exhaustion from unbounded payloads.
- Lack of graceful shutdown orchestration: SIGTERM signals terminated worker processes abruptly without draining active in-flight requests or awaiting upstream load-balancer deregistration.

We require a standardized, declarative, per-feature server configuration specification (`server-config.yml`) backed by strictly validated Pydantic snapshot contracts, immutable CEL cross-field validation, and unified telemetry middleware.

---

## 2. Decision Outcome

We standardize on a declarative, per-feature configuration file named **`server-config.yml`** placed directly inside each domain feature folder (`src/features/<feature>/server-config.yml`), integrated with `python-shared/src/features/server`'s **`ServerConfigurationService`**, **`ServerPolicySnapshot`**, and **`CorrelationAndTelemetryMiddleware`**.

### Key Architectural Invariants
1. **Immutable Snapshot Pattern**: Server configuration is loaded once at boot, cross-field validated against Common Expression Language (CEL) rules, and frozen into a read-only `ServerPolicySnapshot`.
2. **Centralized Correlation & Telemetry**: Every FastAPI service mounts `CorrelationAndTelemetryMiddleware` as its outermost ingress layer to extract/inject W3C `traceparent`, `x-request-id`, and `x-correlation-id`.
3. **Graceful Drain Lifecycle**: Server shutdowns respect a 3-phase sequence: propagation wait (allowing upstream proxy health checks to fail), connection draining deadline, and forced resource cleanup.
4. **Single-Line Zero-Boilerplate Loading**:
   ```python
   snapshot = ServerConfigurationService.from_file("src/features/my_feature").build_snapshot()
   ```

---

## 3. Schema Specification: `server-config.yml`

Below is the complete structural contract for `server-config.yml`:

```yaml
schema_version: "1.0.0"
feature_name: "quality_baseline"

server:
  public_bind: "0.0.0.0:8003"           # Ingress socket bind address (interface:port)
  admin_bind: "127.0.0.1:9003"           # Management & metrics probe bind address
  max_request_timeout: "60s"            # Maximum duration allowed for complete request processing
  idle_connection_timeout: "65s"        # TCP keepalive idle connection deadline
  header_read_timeout: "10s"            # Maximum time allowed to receive full HTTP headers
  handshake_timeout: "5s"               # TLS negotiation timeout budget
  upstream_lb_idle_timeout: "60s"       # Expected idle timeout of upstream edge proxy
  tls_mode: "off"                       # Options: off | strict | permissive | mtls
  trusted_proxies:                      # CIDR blocks permitted to populate X-Forwarded-For
    - "127.0.0.1/32"
    - "10.0.0.0/8"
    - "172.16.0.0/12"
    - "192.168.0.0/16"

lifecycle:
  propagation_wait: "2s"                # Sleep after SIGTERM before closing listener (lets LB deregister)
  drain_deadline: "15s"                 # Maximum time to await completion of in-flight active requests
  force_cleanup_margin: "3s"            # Buffer to close persistent DB/Redis pools before SIGKILL
  orchestrator_kill_timeout: "30s"      # Kubernetes terminationGracePeriodSeconds ceiling

limits:
  total_connection_cap: 10000           # Global maximum concurrent TCP connections admitted
  per_client_cap: 100                   # Maximum concurrent connections permitted per peer IP
  max_body_bytes: 10485760              # Maximum request body size in bytes (10 MiB)
  global_admission_limit: 1000          # Maximum concurrent requests admitted to pipeline queue
  ip_rate_limit_tokens: 100             # Pre-auth IP token bucket capacity
  ip_rate_limit_refill_per_sec: 10.0    # Token bucket refill rate per second
  tenant_quota_tokens: 500              # Per-tenant burst token quota
  tenant_quota_refill_per_sec: 50.0     # Tenant refill rate per second

middleware:
  correlation_telemetry:
    enabled: true                       # Mount CorrelationAndTelemetryMiddleware
    header_name: "x-correlation-id"     # Primary correlation header key
    propagate_w3c: true                 # Propagate W3C Trace Context (traceparent)
    record_latency: true                # Measure and log total request duration
```

### Field Definitions & CEL Validation Rules

| Section | Field | Type | Default | Validation Rule / Constraint |
|---|---|---|---|---|
| `server` | `public_bind` | `string` | `"0.0.0.0:8000"` | Valid `IP:PORT` format; port `1024`–`65535`. |
| `server` | `admin_bind` | `string` | `"127.0.0.1:9090"` | Must NOT collide with `public_bind` (`public_bind != admin_bind`). |
| `server` | `idle_connection_timeout` | `string` | `"65s"` | Must exceed upstream LB idle timeout (`idle_timeout > upstream_lb_idle_timeout`). |
| `server` | `header_read_timeout` | `string` | `"10s"` | Must be less than idle timeout (`header_timeout < idle_timeout`). |
| `lifecycle`| `drain_deadline` | `string` | `"15s"` | Total shutdown budget constraint (`drain + propagation < orchestrator_kill`). |
| `limits` | `total_connection_cap` | `int` | `10000` | Positive integer (`gt=0`). |
| `limits` | `max_body_bytes` | `int` | `10485760` | Positive integer (`gt=0`); default 10 MiB. |
| `limits` | `global_admission_limit` | `int` | `1000` | Positive integer (`gt=0`). |

---

## 4. Comprehensive Operations & Implementation Manual

### 1. Creating `server-config.yml` for a Microservice Feature

Generate a feature-specific server config file:

```bash
cat << 'EOF' > src/features/quality_baseline/server-config.yml
schema_version: "1.0.0"
feature_name: "quality_baseline"

server:
  public_bind: "0.0.0.0:8003"
  admin_bind: "127.0.0.1:9003"
  max_request_timeout: "60s"
  idle_connection_timeout: "65s"
  header_read_timeout: "10s"
  handshake_timeout: "5s"
  upstream_lb_idle_timeout: "60s"
  tls_mode: "off"
  trusted_proxies:
    - "127.0.0.1/32"
    - "10.0.0.0/8"

lifecycle:
  propagation_wait: "2s"
  drain_deadline: "15s"
  force_cleanup_margin: "3s"
  orchestrator_kill_timeout: "30s"

limits:
  total_connection_cap: 10000
  per_client_cap: 100
  max_body_bytes: 10485760
  global_admission_limit: 1000
  ip_rate_limit_tokens: 100
  ip_rate_limit_refill_per_sec: 10.0
  tenant_quota_tokens: 500
  tenant_quota_refill_per_sec: 50.0

middleware:
  correlation_telemetry:
    enabled: true
    header_name: "x-correlation-id"
    propagate_w3c: true
    record_latency: true
EOF
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
from src.features.server.server_configuration.service.server_config_service import ServerConfigurationService
service = ServerConfigurationService.from_file('src/features/quality_baseline')
snapshot = service.build_snapshot()
assert snapshot.server.public_bind == '0.0.0.0:8003'
assert snapshot.limits.total_connection_cap == 10000
print('Server policy snapshot successfully built and validated!')
"
```

---

### 2. Bootstrapping FastAPI with Configuration & Middleware
Inside `src/api/rest/v1/app.py`:

```python
from pathlib import Path
from fastapi import FastAPI
from python_shared.http import CorrelationAndTelemetryMiddleware
from src.features.server.server_configuration.service.server_config_service import ServerConfigurationService

def create_app() -> FastAPI:
    feature_dir = Path(__file__).resolve().parents[3] / "features" / "quality_baseline"
    snapshot = ServerConfigurationService.from_file(str(feature_dir)).build_snapshot()

    app = FastAPI(
        title="Quality Engine Service",
        version="1.0.0"
    )
    
    app.state.server_snapshot = snapshot

    app.add_middleware(
        CorrelationAndTelemetryMiddleware,
        service_name="quality-engine",
        header_name="x-correlation-id"
    )

    @app.get("/healthz")
    async def health_check():
        return {"status": "ok", "bind": snapshot.server.public_bind}

    return app
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
from fastapi.testclient import TestClient
from src.api.rest.v1.app import create_app
app = create_app()
client = TestClient(app)
resp = client.get('/healthz')
assert resp.status_code == 200
assert 'x-correlation-id' in resp.headers
assert 'x-request-id' in resp.headers
print('FastAPI app middleware & config verified!')
"
```

---

### 3. Running Uvicorn from Validated Policy Snapshot
In `src/main.py`:

```python
import uvicorn
from pathlib import Path
from src.api.rest.v1.app import create_app
from src.features.server.server_configuration.service.server_config_service import ServerConfigurationService

def main():
    feature_dir = Path(__file__).resolve().parent / "features" / "quality_baseline"
    snapshot = ServerConfigurationService.from_file(str(feature_dir)).build_snapshot()

    host, port_str = snapshot.server.public_bind.split(":")
    port = int(port_str)

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        timeout_keep_alive=65,
        limit_concurrency=snapshot.limits.global_admission_limit,
        limit_max_requests=None
    )

if __name__ == "__main__":
    main()
```

#### How to Verify Configuration Correctness:
```bash
python3 -c "
from src.features.server.server_configuration.service.server_config_service import ServerConfigurationService
snapshot = ServerConfigurationService.from_file('quality-engine/src/features/quality_baseline').build_snapshot()
host, port = snapshot.server.public_bind.split(':')
assert host == '0.0.0.0'
assert port == '8003'
print('Uvicorn runner parameters verified!')
"
```

---

### 4. Testing End-to-End W3C Trace & Correlation Propagation
Verify that incoming traceparents are preserved and returned in response headers:

```bash
# Execute request with synthetic W3C traceparent
curl -i -X GET http://localhost:8003/healthz \
  -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" \
  -H "x-correlation-id: corr-txn-9941"
```

#### How to Verify Configuration Correctness:
```bash
# Expected HTTP Response Headers:
# HTTP/1.1 200 OK
# x-correlation-id: corr-txn-9441
# x-request-id: <uuid4>
# Content-Type: application/json
```

---

## 5. Failure Diagnosis & Resolution Matrix

| Symptom / Error | Root Cause | Diagnosis Command | Corrective Action |
|---|---|---|---|
| `ValueError: Configuration validation failed: header_read_timeout must be < idle_connection_timeout` | CEL cross-field validation rule triggered due to invalid timeout combination. | Inspect `server-config.yml` timeouts. | Ensure `header_read_timeout` (e.g. `10s`) is strictly smaller than `idle_connection_timeout` (e.g. `65s`). |
| `ValueError: public_bind and admin_bind cannot share identical port` | Port collision between public API and admin management interface. | Check `public_bind` and `admin_bind` in `server-config.yml`. | Separate ports (e.g. `public_bind: "0.0.0.0:8000"`, `admin_bind: "127.0.0.1:9090"`). |
| `HTTP 413 Payload Too Large` | Client sent request body exceeding `limits.max_body_bytes`. | Check `Content-Length` header against `limits.max_body_bytes`. | Increase `max_body_bytes` in `server-config.yml` if larger payloads are expected. |
| Ingress requests dropped during Kubernetes rolling update | Immediate SIGTERM termination before upstream proxy drains connections. | Check `propagation_wait` in `lifecycle`. | Ensure `propagation_wait` is at least `2s` to allow proxy endpoint table updates. |
| Missing `x-correlation-id` in response | Service bypassed `CorrelationAndTelemetryMiddleware`. | Check middleware chain in `src/api/rest/v1/app.py`. | Mount `app.add_middleware(CorrelationAndTelemetryMiddleware)` as the first middleware. |
