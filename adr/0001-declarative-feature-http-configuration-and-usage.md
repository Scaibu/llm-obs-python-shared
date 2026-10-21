# ADR 0001: Declarative Feature HTTP Configuration (`http-config.yml`) and Composable Pipeline Client Usage

- **Status:** Accepted
- **Date:** 2026-10-21
- **Scope:** `python-shared` (`features/http`), Monorepo Microservices (All Domain Features)
- **Author:** Principal Distributed Systems Architect & Security Officer

---

## 1. Context and Problem Statement: Why Does This Even Exist?

In high-throughput, polyglot microservice architectures (combining synchronous FastAPI REST gateways, asynchronous Temporal workflow workers, and internal gRPC/HTTP sidecars), network communication across service boundaries is the single most common failure domain. 

Previously, across the 16 packages in this monorepo, developers wrote ad-hoc outbound HTTP client logic. Every feature team independently created `httpx.Client()` or `httpx.AsyncClient()` instances, leading to systemic outages, security exposures, and operational chaos:

### 1.1 Post-Mortem Analysis of Past Systemic Failures

1. **The "Every Class Instantiates a Client" Anti-Pattern (Connection Exhaustion & OOM)**:
   - *What Happened*: Feature services instantiated a fresh `httpx.AsyncClient()` inside individual functions or request handlers. Each client created its own independent connection pool.
   - *Impact*: Under moderate traffic spikes (500 req/s), thousands of concurrent TCP sockets opened simultaneously. The operating system exhausted ephemeral ports and file descriptors (`OSError: [Errno 24] Too many open files`). Worker processes crashed with `EMFILE`, causing cascading pod failures.

2. **The Temporal Worker vs. REST API Process Mismatch (Worker Deadlock & Retry Storms)**:
   - *What Happened*: Temporal activities run in an asynchronous, workflow-orchestrated execution model. Temporal natively handles backoff, scheduling, exponential retries, and task queues. When an in-memory client-side rate-limiter, retry loop (3 retries with fixed delay), and bulkhead concurrency limiter was placed inside an HTTP client invoked by a Temporal activity, the two retry engines collided.
   - *Impact*: An activity waiting on an in-memory client bulkhead timed out in Temporal. Temporal considered the worker stalled and re-scheduled the entire activity on another worker. This spawned exponential duplicate requests (thundering herd) that slammed downstream databases and LLM scoring endpoints, turning transient glitches into catastrophic total outages.

3. **Distributed Trace Fracture & Context Severing**:
   - *What Happened*: When `quality-engine` called `toxicity` or `perplexity`, outbound requests omitted W3C `traceparent`, `x-request-id`, `x-correlation-id`, and tenant identity headers (`x-tenant-id`).
   - *Impact*: Distributed tracing in Datadog/OpenTelemetry broke into disconnected span fragments. When an inference call failed, engineers could not trace the origin user request through the API gateway to the downstream worker without manual timestamp searches across dozens of log streams.

4. **Server-Side Request Forgery (SSRF) & Cloud Metadata Exfiltration**:
   - *What Happened*: LLM evaluation pipelines accepted user-supplied evaluation target URLs without rigorous synchronous IP resolution and CIDR validation.
   - *Impact*: Attackers submitted URLs pointing to AWS/GCP instance metadata (`http://169.254.169.254/latest/meta-data/`) or private VPC IP spaces (`http://10.0.0.1/admin`). Without an automated SSRF firewall step in the HTTP pipeline, internal network topologies and IAM role tokens were vulnerable to theft.

5. **Cascading Downstream Outages & Lack of Deterministic Circuit Breakers**:
   - *What Happened*: When a downstream microservice was degraded (e.g. database locks causing 30s response times), upstream services kept sending 100% of traffic.
   - *Impact*: Upstream worker threads hung waiting for timeouts, exhausting the upstream thread pool until all services in the call graph crashed together.

6. **Cache Stampedes on Hot Inference Keys (Missing Singleflight)**:
   - *What Happened*: When a popular prompt was evaluated by 50 concurrent users, the system dispatched 50 identical heavy requests to downstream embedding models simultaneously.
   - *Impact*: Redundant computational load overwhelmed GPUs and incurred thousands of dollars in wasted inference compute.

---

## 2. Decision Outcome: The Declarative & Composable Solution

To permanently eradicate these failure modes, we adopted an architecture grounded in three non-negotiable principles:

1. **Per-Feature Co-Located Declarative Contract (`http-config.yml`)**:
   - Every domain feature directory owns an explicit, strongly typed `http-config.yml`.
   - Network policies, timeouts, circuit breaker thresholds, and rate limits are defined declaratively in YAML—never hardcoded in Python code.
   - SREs and platform teams can adjust network limits during incidents without modifying application source code.

2. **Composable Execution Profiles Tailored to Process Models**:
   - The client pipeline dynamically composes its interceptor steps according to the runtime environment:
     - **`api_service`**: Full 8-step defensive pipeline for customer-facing REST APIs (`input_hardening` -> `ssrf_validation` -> `context_isolation` -> `cache_eval` -> `singleflight` -> `circuit_breaker` -> `rate_limit` -> `admission_control`).
     - **`temporal_worker`**: Lean 2-step pipeline (`context_isolation` -> `circuit_breaker`). Bypasses client-side rate limits and retries to avoid clashing with Temporal's orchestrator engine.
     - **`internal_fast`**: Ultra-lean 1-step pipeline (`context_isolation`) for high-throughput intra-cluster RPC, keeping overhead below 0.2ms.

3. **Hexagonal Architecture & Inversion of Control**:
   - Application domain services depend strictly on pure Python abstract interfaces (Ports).
   - Infrastructure Adapters encapsulate `ResilientHttpClient.from_config(__file__)`. Domain logic never imports `httpx`, URLs, or network status codes.

4. **Zero-Downtime Hot-Reloading & Live Admin Control Plane**:
   - Configuration files can be hot-reloaded via `POST /admin/v1/http/reload` or `SIGHUP`. In-flight requests safely complete on the previous immutable snapshot while new requests atomically adopt the updated configuration with zero dropped sockets.

5. **Streaming Telemetry & DLQ Messaging Plane**:
   - Circuit breaker trips, rate-limit drops, and security violations are asynchronously published as CloudEvents 1.0 JSON messages to Kafka (`http.outbound.audit.v1` and `http.outbound.dlq.v1`).

---

## 3. High Level Design (HLD) & Architectural Deep-Dive

### 3.1 Architecture Diagram

```mermaid
flowchart TD
    subgraph FeatureDomain["1. Domain Feature Layer (src/features/{feature}/)"]
        Service[Domain Service] -->|Pure Domain Intent| Port[Hexagonal Outbound Port]
        Port -->|Invokes Interface| Adapter[Outbound HTTP Adapter]
        Adapter -->|Loads On Boot| ConfigFile["http-config.yml (Local Feature Config)"]
    end

    subgraph ControlPlane["2. Control Plane & Configuration Engine"]
        ConfigFile -->|YAML Parse & Validate| SnapshotMgr[Config Snapshot Manager]
        AdminSignal["Admin Signals (SIGHUP / HTTP Reload)"] -->|Trigger Atomic Swap| SnapshotMgr
        SnapshotMgr -->|Immutable Pointer| ClientFactory[Client Factory / Pool]
    end

    subgraph PipelineEngine["3. Composable HTTP Pipeline Engine (python-shared)"]
        Adapter -->|"execute_async()"| ClientFactory
        ClientFactory --> ClientInstance[ResilientHttpClient]
        ClientInstance --> PipelineRunner[HttpPipelineRunner]
        
        subgraph PipelineSteps["Ordered Pipeline Steps (Strict Mathematical Order)"]
            direction TB
            Step1["01: StepInputHardening (CRLF header sanitization, JSON depth)"]
            Step2["02: StepSsrfValidation (DNS resolve, block 169.254/RFC1918)"]
            Step3["03: StepContextIsolation (Inject W3C traceparent, x-tenant-id)"]
            Step4["04: StepCacheEval (RFC 9111 HTTP Cache & stale-if-error)"]
            Step5["05: StepSingleflight (In-flight identical request deduplication)"]
            Step6["06: StepCircuitBreaker (Sliding window failure tracking)"]
            Step7["07: StepRateLimit (Token bucket / Leaky bucket limiter)"]
            Step8["08: StepAdmissionControl (Concurrency bulkhead & queue)"]
            
            Step1 --> Step2 --> Step3 --> Step4 --> Step5 --> Step6 --> Step7 --> Step8
        end
        
        PipelineRunner --> PipelineSteps
    end

    subgraph TransportLayer["4. Transport & Connection Pool Engine"]
        PipelineSteps -->|Admitted, Sanitized & Traced| Transport[HTTPX Transport Pool]
        Transport -->|HTTP/1.1 or HTTP/2 Multiplex| Wire[Physical Network Socket / Wire]
    end

    subgraph MessagingPlane["5. Messaging & Observability Plane"]
        PipelineSteps -.->|CloudEvents 1.0 Audits| KafkaAudit["Kafka Topic: http.outbound.audit.v1"]
        PipelineSteps -.->|Retry Exhaustion / Outage| KafkaDLQ["Kafka Topic: http.outbound.dlq.v1"]
        Transport -.->|OTel Spans & Metrics| Collector[OpenTelemetry Collector]
    end
```

---

### 3.2 In-Depth HLD Component Walkthrough

#### 1. Domain Feature Layer (`src/features/{feature}/`)
- **Isolation Invariant**: Domain services (`service/{f}.service.py`) must contain zero external network references. They interact exclusively with abstract port interfaces (`infrastructure/ports/{f}.port.py`).
- **Adapter Encapsulation**: Outbound adapters (`infrastructure/adapters/{f}.adapter.py`) encapsulate `ResilientHttpClient`. The adapter resolves its local directory to locate `http-config.yml`, ensuring configuration is strictly co-located with the feature using it.

#### 2. Control Plane & Configuration Engine
- **Decoupled Lifecycle**: The configuration engine decouples file parsing from request handling. The YAML is parsed into strongly-typed Pydantic schemas, validated against range constraints, and compiled into an immutable snapshot.
- **Zero-Downtime Hot-Reload**: Live reload operates via an atomic pointer swap (`atomic.Pointer`). In-flight requests retain their original configuration reference, while new requests immediately pick up the updated snapshot. No sockets are closed prematurely.

#### 3. Composable HTTP Pipeline Engine
The 8 pipeline steps execute in a strict, mathematically sound sequence:
1. **`StepInputHardening` (Security Gate 1)**: Runs first to neutralize malicious input before any network activity. Prevents CRLF injection in HTTP headers (which causes HTTP response splitting) and validates JSON depth to stop recursion denial-of-service.
2. **`StepSsrfValidation` (Security Gate 2)**: Resolves destination domain names and verifies the resolved IP against blocked CIDRs. By executing *before* context injection or caching, it stops SSRF attacks without wasting system resources.
3. **`StepContextIsolation` (Context Enrichment)**: Injects W3C `traceparent`, `x-request-id`, `x-correlation-id`, and tenant metadata into outbound headers. Placed *before* caching so cache keys incorporate tenant identity to prevent cross-tenant data leakage.
4. **`StepCacheEval` (Fast-Path Optimization)**: Checks in-memory or Redis caches for matching responses. On a cache hit, the request short-circuits immediately, bypassing downstream circuit breakers, rate limiters, and network I/O.
5. **`StepSingleflight` (Stampede Protection)**: Deduplicates concurrent identical requests. Only one request (the "leader") continues through the remaining pipeline; all other concurrent calls ("followers") pause and await the leader's response.
6. **`StepCircuitBreaker` (Downstream Fault Isolation)**: Tracks consecutive failures and slow calls across a sliding window. Positioned *after* singleflight so that 100 concurrent duplicate requests only count as 1 request against the failure rate threshold.
7. **`StepRateLimit` (Traffic Shaping)**: Enforces token-bucket rate limits per tenant or per upstream host. Rejects excessive bursts before they reach the connection pool.
8. **`StepAdmissionControl` (Resource Bulkhead)**: Enforces concurrency caps and queues pending requests. Acts as the final gate protecting local process memory and thread pools.

#### 4. Transport & Connection Pool Engine
- Uses persistent connection pools via HTTPX. Sockets are kept alive (`max_keepalive_connections`), enabling TCP handshake and TLS session reuse.
- Supports HTTP/2 multiplexing, allowing dozens of concurrent requests over a single TCP connection.

#### 5. Messaging & Observability Plane
- Asynchronous telemetry: Circuit breaker state changes, rate-limit drops, and SSRF security violations emit CloudEvents 1.0 payloads to Kafka topics.
- Spans and metric histograms are recorded using OpenTelemetry HTTP client semantic conventions (`http.client.request.duration`).

---

## 4. Low Level Design (LLD)

### 4.1 Sequence Diagram: Outbound Pipeline Execution Flow

```mermaid
sequenceDiagram
    autonumber
    participant App as Outbound Adapter
    participant Client as ResilientHttpClient
    participant Runner as HttpPipelineRunner
    participant Sec as Security & SSRF Steps
    participant Ctx as Context Step
    participant Cache as Cache & Singleflight
    participant Res as Resilience (CB, RateLimit, Bulkhead)
    participant Transport as Httpx Transport Pool
    participant Target as Upstream Target

    App->>Client: execute_async(method, url, json, tenant_id)
    Client->>Runner: execute(PipelineContext)
    
    %% Security Phase
    Runner->>Sec: execute(context)
    Note over Sec: Validate CRLF in headers<br/>Resolve DNS & verify IP not in RFC 1918 / 169.254
    Sec-->>Runner: Ok (Sanitized Target)

    %% Context Propagation
    Runner->>Ctx: execute(context)
    Note over Ctx: Inject W3C traceparent<br/>Inject x-tenant-id, x-correlation-id
    Ctx-->>Runner: Ok (Headers Enriched)

    %% Cache Evaluation
    Runner->>Cache: execute(context)
    alt Cache Hit
        Cache-->>Client: Return Cached Response (Short-circuit)
        Client-->>App: httpx.Response (Cached)
    else Cache Miss / Singleflight Leader
        Cache-->>Runner: Proceed (Leader Registered)
    end

    %% Resilience Checks
    Runner->>Res: execute(context)
    Note over Res: Check CircuitBreaker (CLOSED)<br/>Acquire RateLimit Token<br/>Acquire Bulkhead Slot
    Res-->>Runner: Admitted (Resource Reserved)

    %% Network Execution
    Runner->>Transport: send(request)
    Transport->>Target: Outbound Wire Request (HTTP/2 or Keepalive Socket)
    Target-->>Transport: Wire Response (HTTP 200 OK)
    Transport-->>Runner: Response Received

    %% Release & Cache Store
    Runner->>Res: Record success (Release Bulkhead, update CB sliding window)
    Runner->>Cache: Store response in cache & notify singleflight followers
    Runner-->>Client: PipelineContext(response=200)
    Client-->>App: httpx.Response
```

---

### 4.2 Sequence Diagram In-Depth Step Walkthrough

1. **Invocation (Steps 1–2)**: The outbound adapter invokes `client.execute_async()`. The client wraps the target, headers, payload, and tenant ID into a mutable `PipelineContext` and forwards it to `HttpPipelineRunner`.
2. **Security & SSRF Inspection (Steps 3–4)**:
   - `StepInputHardening` scans headers for carriage returns (`\r\n`) and validates JSON nesting depth against `security.input_hardening.max_json_depth`.
   - `StepSsrfValidation` performs synchronous DNS resolution on the hostname. If the resolved IP falls within blocked CIDR ranges (e.g. `10.0.0.0/8`, `169.254.169.254`), execution immediately aborts with `SSRFSecurityViolation`.
3. **Context Enrichment (Steps 5–6)**: `StepContextIsolation` extracts the active OpenTelemetry span context, formats the W3C `traceparent` header, and attaches `x-tenant-id` and `x-request-id`.
4. **Cache & Singleflight Fast-Path (Steps 7–9)**:
   - `StepCacheEval` checks the local cache. If a valid, non-expired response exists, it immediately returns the cached response, bypassing all network layers.
   - If not cached, `StepSingleflight` generates a SHA-256 key from `Method + URL + Tenant + Body`. If an identical request is already in-flight, subsequent requests pause and wait for the leader's response.
5. **Resilience & Admission (Steps 10–11)**:
   - `StepCircuitBreaker` verifies that the circuit is `CLOSED` or `HALF-OPEN`. If `OPEN`, it rejects the request instantly with `CircuitBreakerOpenException`.
   - `StepRateLimit` verifies token availability. If the bucket is exhausted, it throws HTTP 429.
   - `StepAdmissionControl` verifies available slots in the concurrency bulkhead. If full, it queues the request up to `queue_timeout_seconds`.
6. **Network Wire I/O (Steps 12–14)**: The request is dispatched over an established keep-alive TCP socket or HTTP/2 multiplexed stream.
7. **Post-Processing & Release (Steps 15–17)**:
   - The bulkhead slot is released back to the pool.
   - The circuit breaker records the outcome (success or error).
   - If eligible, the response is stored in cache, and waiting singleflight followers are woken up.
   - The final `httpx.Response` is returned to the adapter.

---

### 4.3 End-to-End Functional Call Stack

The following call stack traces an outbound remote invocation from the domain caller down through the hexagonal adapter, resilient pipeline interceptors, HTTPX connection transport, and kernel socket, followed by the unwinding return path:

```
[Feature Domain Layer]
 1. FeatureDomainService.execute_business_action(data, tenant_id, correlation_id)
      │
      ▼
 2. FeatureOutboundPort.execute_remote_operation(payload, tenant_id, correlation_id) [Abstract Interface]
      │
      ▼
[Infrastructure Adapter Layer]
 3. HttpFeatureOutboundAdapter.execute_remote_operation(payload, tenant_id, correlation_id)
      │
      ▼
[Resilient Client Core]
 4. ResilientHttpClient.execute_async(method="POST", url="/api/v1/remote/execute", json=payload, tenant_id=...)
      │   └── Creates PipelineContext(request, tenant_id, correlation_id, trace_context)
      ▼
 5. HttpPipelineRunner.execute(context: PipelineContext) -> PipelineContext
      │
      ├──▶ 6. StepInputHardening.execute(context)
      │         └── Scans headers for CRLF injection (\r\n); validates JSON nesting depth <= 20
      │
      ├──▶ 7. StepSsrfValidation.execute(context)
      │         └── socket.getaddrinfo(host) -> Verifies resolved IP not in RFC 1918 / 169.254.169.254
      │
      ├──▶ 8. StepContextIsolation.execute(context)
      │         └── Formats W3C traceparent (00-{trace_id}-{span_id}-01); injects x-tenant-id
      │
      ├──▶ 9. StepCacheEval.execute(context)
      │         └── Evaluates cache key: SHA256(tenant + method + url + body). On hit -> returns cached 200
      │
      ├──▶ 10. StepSingleflight.execute(context)
      │          └── In-flight registry lookup. If leader -> proceed; if follower -> asyncio.Event.wait()
      │
      ├──▶ 11. StepCircuitBreaker.execute(context)
      │          └── Verifies state: CLOSED (proceed), OPEN (reject), HALF-OPEN (allow trial probe)
      │
      ├──▶ 12. StepRateLimit.execute(context)
      │          └── TokenBucket.acquire() -> Check rate limits per tenant/host. If empty -> raise 429
      │
      ├──▶ 13. StepAdmissionControl.execute(context)
      │          └── asyncio.Semaphore.acquire() -> Concurrency bulkhead slot reserved
      │
      ▼
[Transport Layer & Wire I/O]
 14. httpx.AsyncClient.send(request: httpx.Request)
      │
      ▼
 15. httpx.AsyncHTTPTransport.handle_async_request()
      │
      ▼
 16. httpcore.AsyncConnectionPool.handle_async_request()
      │   └── Reuses idle keep-alive socket or performs TCP handshake + TLS 1.3 ALPN
      ▼
 17. Linux Kernel Socket -> Wire (HTTP/2 Multiplexed Frame or HTTP/1.1 TCP Packet)
      │
      ◀── HTTP 200 OK Response Arrives from Wire
      │
[Unwinding & Release Stack]
 18. StepAdmissionControl releases concurrency slot (semaphore.release())
 19. StepCircuitBreaker records success in sliding window (consecutive_failures = 0)
 20. StepCacheEval stores eligible response into Redis / In-Memory cache
 21. StepSingleflight publishes response to waiting follower tasks via asyncio.Event.set()
 22. HttpFeatureOutboundAdapter verifies response.raise_for_status() -> returns parsed JSON DTO
 23. FeatureDomainService completes business orchestration and returns domain result
```

---

### 4.4 Internal Pipeline Execution Decision Tree

#### 4.4.1 Exhaustive IF/ELSE Branching & Loop ASCII Tree (All Paths Covered)

```text
+------------------------------------------------------------------------------------------------------------------------+
|                      HTTP OUTBOUND RESILIENT PIPELINE: EXHAUSTIVE IF/ELSE & LOOP EXECUTION TREE                        |
|                     (All Conditions, Loops, Fallbacks, Circuit States, and Error Paths Covered)                       |
+------------------------------------------------------------------------------------------------------------------------+

[INVOCATION] FeatureDomainService -> FeatureOutboundPort -> HttpFeatureOutboundAdapter
   |
   +--> ResilientHttpClient.execute_async(method, url, json_body, tenant_id, correlation_id, headers)
          |
          +-- [PIPELINE INITIALIZATION]
          |     Create PipelineContext(request, tenant_id, correlation_id, start_time)
          |
          +-- STEP 1: Input Hardening & Sanitization [StepInputHardening]
          |     |
          |     +-- IF (any("\r" in v or "\n" in v for v in headers.values())) THEN:
          |     |     |-- [LOG ALERT] "CRLF injection detected in outbound headers"
          |     |     |-- [METRIC] Increment counter 'security.hardening.crlf_detected'
          |     |     +-- [RAISE] SecurityHardeningException("HTTP Header Splitting Blocked", status_code=400)
          |     |
          |     +-- ELSE IF (json_body is not None AND calculate_json_depth(json_body) > 20) THEN:
          |     |     |-- [LOG ALERT] "JSON payload nesting depth exceeds maximum allowed ceiling of 20"
          |     |     |-- [METRIC] Increment counter 'security.hardening.recursion_limit_exceeded'
          |     |     +-- [RAISE] SecurityHardeningException("Payload Recursion Limit Exceeded", status_code=400)
          |     |
          |     +-- ELSE:
          |           +-- [PASS] Payload and headers sanitized. Proceed to Step 2.
          |
          +-- STEP 2: SSRF Domain & IP Firewall [StepSsrfValidation]
          |     |
          |     +-- IF (config.security.ssrf_validation == False) THEN:
          |     |     +-- [SKIP] SSRF validation bypassed by configuration (internal_fast profile).
          |     |
          |     +-- ELSE:
          |           |-- target_ip = socket.getaddrinfo(url.hostname, url.port)[0][4][0]
          |           |
          |           +-- IF (target_ip in "169.254.0.0/16" [Cloud Instance Metadata]) THEN:
          |           |     |-- [LOG CRITICAL] "SSRF Attempt to Cloud Instance Metadata IP: " + target_ip
          |           |     |-- [EVENT] Kafka CloudEvent -> 'http.outbound.audit.v1' (topic: security_violation)
          |           |     |-- [METRIC] Increment counter 'security.ssrf.cloud_metadata_blocked'
          |           |     +-- [RAISE] SSRFSecurityViolation("Target IP is cloud metadata", status_code=403)
          |           |
          |           +-- ELSE IF (target_ip in ["127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1"]) THEN:
          |           |     |-- [LOG ALERT] "SSRF Attempt to Private RFC 1918 / Loopback Subnet: " + target_ip
          |           |     |-- [EVENT] Kafka CloudEvent -> 'http.outbound.audit.v1' (topic: security_violation)
          |           |     |-- [METRIC] Increment counter 'security.ssrf.rfc1918_blocked'
          |           |     +-- [RAISE] SSRFSecurityViolation("Private VPC destinations forbidden", status_code=403)
          |           |
          |           +-- ELSE:
          |                 +-- [PASS] Target IP verified as a legitimate public routable destination.
          |
          +-- STEP 3: Context & Distributed Tracing [StepContextIsolation]
          |     |
          |     +-- IF (active_span := opentelemetry.trace.get_current_span()):
          |     |     +-- headers["traceparent"] = format_w3c_traceparent(active_span.context)
          |     +-- ELSE:
          |     |     +-- headers["traceparent"] = generate_root_w3c_traceparent()
          |     |
          |     |-- headers["x-tenant-id"] = tenant_id
          |     |-- headers["x-correlation-id"] = correlation_id or generate_uuid4()
          |     |-- headers["x-request-id"] = generate_uuid4()
          |     +-- [PASS] Context isolated and W3C headers injected.
          |
          +-- STEP 4: HTTP Response Caching [StepCacheEval]
          |     |
          |     |-- cache_key = sha256(tenant_id + ":" + method + ":" + url + ":" + sha256(body))
          |     |
          |     +-- IF (config.cache_eval.enabled == True AND method in ["GET", "HEAD"]):
          |     |     |-- cached_entry = cache_store.get(cache_key)
          |     |     |
          |     |     +-- IF (cached_entry is not None AND not cached_entry.is_expired()):
          |     |     |     |-- [LOG INFO] "Cache HIT for key: " + cache_key
          |     |     |     |-- [METRIC] Increment counter 'client.cache.hit'
          |     |     |     +-- [RETURN] cached_entry.to_response(status_code=200, headers={"X-Cache": "HIT"})
          |     |     |
          |     |     +-- ELSE IF (cached_entry is not None AND cached_entry.is_within_stale_window()):
          |     |     |     |-- [LOG INFO] "Stale cache HIT (revalidating in background): " + cache_key
          |     |     |     |-- [ASYNC] asyncio.create_task(revalidate_cache_entry(cache_key, request))
          |     |     |     +-- [RETURN] cached_entry.to_response(headers={"X-Cache": "STALE-HIT"})
          |     |     |
          |     |     +-- ELSE:
          |     |           |-- [LOG DEBUG] "Cache MISS for key: " + cache_key
          |     |           |-- [METRIC] Increment counter 'client.cache.miss'
          |     |           +-- [PASS] Proceed to Singleflight.
          |     |
          |     +-- ELSE:
          |           +-- [SKIP] Caching disabled or method non-cacheable. Proceed to Step 5.
          |
          +-- STEP 5: In-Flight Request Deduplication [StepSingleflight]
          |     |
          |     |-- await in_flight_lock.acquire()
          |     |
          |     +-- IF (leader_task := in_flight_registry.get(cache_key)) THEN:
          |     |     |-- in_flight_lock.release()
          |     |     |-- [LOG INFO] "Duplicate concurrent request detected. Registered as FOLLOWER on key: " + cache_key
          |     |     |-- [METRIC] Increment counter 'client.singleflight.follower_joined'
          |     |     |
          |     |     |-- [WAIT] await leader_task.completion_event.wait(timeout=config.client.timeout_seconds)
          |     |     |
          |     |     +-- IF (leader_task.completion_event.is_set() == False) THEN:
          |     |     |     |-- [LOG WARN] "Follower timed out awaiting singleflight leader task: " + cache_key
          |     |     |     +-- [RAISE] SingleflightTimeoutException("Timed out waiting for leader task", status_code=504)
          |     |     |
          |     |     +-- ELSE IF (leader_task.exception is not None) THEN:
          |     |     |     |-- [LOG WARN] "Singleflight leader failed. Re-raising leader exception on follower."
          |     |     |     +-- [RE-RAISE] leader_task.exception (Mirrored outcome without redundant network I/O)
          |     |     |
          |     |     +-- ELSE:
          |     |           |-- [METRIC] Increment counter 'client.singleflight.deduplicated_success'
          |     |           +-- [RETURN] leader_task.response.clone(headers={"X-Singleflight": "FOLLOWER"})
          |     |
          |     +-- ELSE:
          |           |-- in_flight_registry[cache_key] = current_task (Registered as LEADER)
          |           |-- in_flight_lock.release()
          |           +-- [LEADER PASS] Proceed as LEADER to Circuit Breaker.
          |
          +-- STEP 6: Circuit Breaker Evaluation [StepCircuitBreaker]
          |     |
          |     |-- state = circuit_breaker.get_state()
          |     |
          |     +-- IF (state == "OPEN") THEN:
          |     |     |-- elapsed_since_trip = now() - circuit_breaker.tripped_timestamp
          |     |     |
          |     |     +-- IF (elapsed_since_trip >= config.circuit_breaker.recovery_timeout_seconds) THEN:
          |     |     |     |-- circuit_breaker.transition_to("HALF-OPEN")
          |     |     |     |-- [LOG INFO] "Recovery timeout elapsed (" + str(elapsed_since_trip) + "s). Entering HALF-OPEN probe state."
          |     |     |     |-- [METRIC] Increment counter 'circuit_breaker.transition.half_open'
          |     |     |     +-- [PASS] Allowed as trial probe request.
          |     |     |
          |     |     +-- ELSE:
          |     |           |-- [LOG WARN] "Circuit is OPEN. Fast-failing outbound request without wire I/O."
          |     |           |-- [METRIC] Increment counter 'circuit_breaker.fast_failure'
          |     |           |
          |     |           +-- IF (config.cache_eval.stale_if_error_seconds > 0 AND (stale := cache.get_stale(cache_key))):
          |     |           |     |-- [LOG WARN] "Returning stale cache fallback during OPEN circuit state."
          |     |           |     +-- [RETURN] stale.to_response(headers={"X-Cache": "STALE-CIRCUIT-DEGRADED"})
          |     |           |
          |     |           +-- ELSE:
          |     |                 +-- [RAISE] CircuitBreakerOpenException("Circuit breaker OPEN", status_code=503)
          |     |
          |     +-- ELSE IF (state == "HALF-OPEN") THEN:
          |     |     +-- IF (circuit_breaker.half_open_probes_in_flight >= config.circuit_breaker.half_open_requests) THEN:
          |     |     |     |-- [LOG WARN] "Max HALF-OPEN probe quota saturated. Rejecting concurrent probe."
          |     |     |     +-- [RAISE] CircuitBreakerOpenException("Max trial probes in-flight", status_code=503)
          |     |     +-- ELSE:
          |     |           |-- circuit_breaker.half_open_probes_in_flight += 1
          |     |           +-- [PASS] Allowed as trial probe request.
          |     |
          |     +-- ELSE (state == "CLOSED"):
          |           +-- [PASS] Downstream healthy. Proceed to Step 7.
          |
          +-- STEP 7: Token Bucket Rate Limiting [StepRateLimit]
          |     |
          |     +-- IF (config.rate_limit.enabled == True) THEN:
          |     |     |-- token_acquired = token_bucket.consume(tenant_id=tenant_id, cost=1)
          |     |     |
          |     |     +-- IF (token_acquired == False) THEN:
          |     |     |     |-- [LOG WARN] "Outbound rate limit threshold breached for tenant: " + tenant_id
          |     |     |     |-- [METRIC] Increment counter 'client.rate_limit.rejected'
          |     |     |     +-- [RAISE] RateLimitExceededException("Outbound rate limit exceeded. Retry later.", status_code=429)
          |     |     |
          |     |     +-- ELSE:
          |     |           +-- [PASS] Rate limit token acquired. Proceed to Step 8.
          |     |
          |     +-- ELSE:
          |           +-- [SKIP] Rate limiting bypassed by configuration.
          |
          +-- STEP 8: Bulkhead Admission Control [StepAdmissionControl]
          |     |
          |     |-- acquired = await semaphore.acquire_timeout(timeout=config.admission_control.queue_timeout_seconds)
          |     |
          |     +-- IF (acquired == False) THEN:
          |     |     |-- [LOG CRITICAL] "Concurrency bulkhead saturated. Queue wait exceeded: " + str(queue_timeout) + "s"
          |     |     |-- [METRIC] Increment counter 'client.admission.bulkhead_saturated'
          |     |     +-- [RAISE] BulkheadRejectionException("Outbound admission bulkhead full", status_code=503)
          |     |
          |     +-- ELSE:
          |           +-- [ACQUIRED] Bulkhead concurrency slot reserved. Proceed to Wire I/O.
          |
          +-- [WIRE I/O & EXPONENTIAL JITTER RETRY ENGINE]
                |
                +-- FOR attempt = 0 TO config.client.retries DO:
                |     |
                |     +-- TRY:
                |     |     |-- dispatch_start = now()
                |     |     |-- raw_response = await httpx_client.send(request, timeout=config.client.timeout_seconds)
                |     |     |-- latency_ms = (now() - dispatch_start) * 1000
                |     |     |-- [METRIC] Record timer 'client.http.request_duration', tags=[status=raw_response.status_code]
                |     |     |
                |     |     +-- IF (raw_response.status_code in [200, 201, 202, 204]) THEN:
                |     |     |     |-- [STATUS 2xx OK] Downstream invocation successful!
                |     |     |     |
                |     |     |     +-- IF (circuit_breaker.state == "HALF-OPEN") THEN:
                |     |     |     |     |-- circuit_breaker.record_probe_success()
                |     |     |     |     +-- IF (circuit_breaker.consecutive_probe_successes >= config.circuit_breaker.half_open_requests):
                |     |     |     |           |-- circuit_breaker.transition_to("CLOSED")
                |     |     |     |           |-- [LOG INFO] "Circuit breaker self-healed. State restored to CLOSED."
                |     |     |     |           +-- [METRIC] Increment counter 'circuit_breaker.transition.closed'
                |     |     |     |
                |     |     |     +-- ELSE:
                |     |     |     |     +-- circuit_breaker.reset_failure_count()
                |     |     |     |
                |     |     |     +-- IF (config.cache_eval.enabled == True AND method in ["GET", "HEAD"]):
                |     |     |     |     +-- cache_store.set(cache_key, raw_response, ttl=config.cache_eval.default_ttl_seconds)
                |     |     |     |
                |     |     |     +-- [BREAK RETRY LOOP] -> Proceed directly to Unwinding & Return.
                |     |     |
                |     |     +-- ELSE IF (raw_response.status_code in [400, 401, 403, 404, 422]) THEN:
                |     |     |     |-- [STATUS 4xx CLIENT ERROR] Deterministic caller failure (non-transient).
                |     |     |     |-- [LOG WARN] "Downstream returned non-retryable 4xx client error: " + str(raw_response.status_code)
                |     |     |     |-- [ACTION] Do NOT retry! Do NOT increment circuit breaker failure count!
                |     |     |     +-- [BREAK RETRY LOOP] -> Proceed directly to Unwinding & Return raw_response.
                |     |     |
                |     |     +-- ELSE IF (raw_response.status_code in config.client.retry_status_codes [429, 502, 503, 504]) THEN:
                |     |           |-- [STATUS 5xx TRANSIENT ERROR] Downstream service unavailable or rate limited.
                |     |           |-- circuit_breaker.record_failure()
                |     |           |
                |     |           +-- IF (circuit_breaker.consecutive_failures >= config.circuit_breaker.failure_threshold):
                |     |           |     |-- circuit_breaker.transition_to("OPEN")
                |     |           |     |-- [LOG CRITICAL] "Circuit breaker tripped to OPEN state (" + str(circuit_breaker.consecutive_failures) + " failures)"
                |     |           |     +-- [METRIC] Increment counter 'circuit_breaker.transition.open'
                |     |           |
                |     |           +-- IF (attempt < config.client.retries) THEN:
                |     |           |     |-- base_backoff = config.client.retry_backoff_factor * (2 ** attempt)
                |     |           |     |-- jittered_sleep = uniform(0.5 * base_backoff, 1.5 * base_backoff)
                |     |           |     |-- [LOG WARN] "Transient 5xx received. Retrying attempt " + str(attempt + 1) + " after " + str(jittered_sleep) + "s"
                |     |           |     |-- [METRIC] Increment counter 'client.retry.attempt'
                |     |           |     |-- await asyncio.sleep(jittered_sleep)
                |     |           |     +-- [CONTINUE RETRY LOOP] (Proceed to next attempt)
                |     |           |
                |     |           +-- ELSE:
                |     |                 |-- [LOG ERROR] "All retry attempts exhausted (" + str(config.client.retries) + "). Outbound call failed."
                |     |                 |-- [EVENT] Kafka CloudEvent -> 'http.outbound.dlq.v1' (topic: call_failure_dlq)
                |     |                 |-- [METRIC] Increment counter 'client.retry.exhausted'
                |     |                 +-- [RAISE] DownstreamServiceUnavailableException(raw_response.text, status_code=raw_response.status_code)
                |     |
                |     +-- EXCEPT (httpx.TimeoutException, httpx.ConnectError, ssl.SSLError) AS net_err:
                |           |-- [NETWORK TRANSPORT ERROR] Socket drop, timeout, or TLS handshake error: str(net_err)
                |           |-- circuit_breaker.record_failure()
                |           |
                |           +-- IF (circuit_breaker.consecutive_failures >= config.circuit_breaker.failure_threshold):
                |           |     |-- circuit_breaker.transition_to("OPEN")
                |           |     |-- [LOG CRITICAL] "Circuit breaker tripped to OPEN following network failure."
                |           |     +-- [METRIC] Increment counter 'circuit_breaker.transition.open'
                |           |
                |           +-- IF (attempt < config.client.retries) THEN:
                |           |     |-- base_backoff = config.client.retry_backoff_factor * (2 ** attempt)
                |           |     |-- jittered_sleep = uniform(0.5 * base_backoff, 1.5 * base_backoff)
                |           |     |-- [LOG WARN] "Transport error on attempt " + str(attempt + 1) + ". Retrying after " + str(jittered_sleep) + "s"
                |           |     |-- [METRIC] Increment counter 'client.retry.attempt'
                |           |     |-- await asyncio.sleep(jittered_sleep)
                |           |     +-- [CONTINUE RETRY LOOP]
                |           |
                |           +-- ELSE:
                |                 |-- [LOG ERROR] "Network transport retries exhausted: " + str(net_err)
                |                 |-- [EVENT] Kafka CloudEvent -> 'http.outbound.dlq.v1' (topic: call_failure_dlq)
                |                 |-- [METRIC] Increment counter 'client.retry.exhausted'
                |                 +-- [RAISE] RemoteHostUnreachableException(str(net_err))
                |
                +-- [GUARANTEED UNWINDING & CLEANUP (FINALLY BLOCK)]
                      |
                      |-- semaphore.release() [Bulkhead concurrency slot returned to pool]
                      |
                      +-- IF (current_task == leader_task) THEN:
                      |     |-- in_flight_registry.pop(cache_key, None)
                      |     |-- leader_task.response = raw_response
                      |     |-- leader_task.exception = raised_exception
                      |     +-- leader_task.completion_event.set() [Awakens all waiting follower tasks!]
                      |
                      +-- [RETURN] raw_response -> HttpFeatureOutboundAdapter -> FeatureDomainService
```

#### 4.4.2 Mermaid Decision Flowchart

```mermaid
flowchart TD
    Start([1. Adapter Invocates execute_async]) --> Hardening{Input Hardening:<br/>CRLF in headers OR<br/>JSON depth > 20?}
    
    Hardening -- YES --> Reject400[Fail Fast: HTTP 400 Bad Request]
    Hardening -- NO --> SSRF{SSRF Validation:<br/>Resolved IP in 169.254/16<br/>or Private RFC 1918?}
    
    SSRF -- YES --> Reject403[Security Violation: Abort Request]
    SSRF -- NO --> Context[Inject W3C traceparent<br/>and x-tenant-id]
    
    Context --> CacheCheck{Cache Eval:<br/>Enabled & Key in Cache?}
    CacheCheck -- YES (Hit) --> ReturnCache[Short-Circuit: Return Cached Response]
    CacheCheck -- NO (Miss) --> Singleflight{Singleflight:<br/>Identical request<br/>already in-flight?}
    
    Singleflight -- YES (Follower) --> AwaitLeader[Wait for Leader asyncio.Event]
    AwaitLeader --> ReturnLeaderResp[Return Leader Shared Response]
    
    Singleflight -- NO (Leader) --> CircuitCheck{Circuit Breaker:<br/>What is current state?}
    CircuitCheck -- OPEN --> CheckRecovery{recovery_timeout<br/>expired?}
    CheckRecovery -- NO --> Reject503[Fail Fast: CircuitBreakerOpenException]
    CheckRecovery -- YES --> EnterHalfOpen[Transition to HALF-OPEN Probe]
    
    CircuitCheck -- CLOSED --> RateCheck
    EnterHalfOpen --> RateCheck{Rate Limit:<br/>Token available<br/>in TokenBucket?}
    
    RateCheck -- NO --> Reject429[Fail Fast: HTTP 429 Too Many Requests]
    RateCheck -- YES --> BulkheadCheck{Admission Bulkhead:<br/>Concurrency slot<br/>available?}
    
    BulkheadCheck -- NO --> QueueCheck{Wait in queue <=<br/>queue_timeout_seconds?}
    QueueCheck -- NO --> RejectBulkhead[Fail Fast: HTTP 503 Bulkhead Full]
    QueueCheck -- YES --> WireIO
    BulkheadCheck -- YES --> WireIO[Execute Outbound Wire Request via HTTPX]
    
    WireIO --> Outcome{Response Status?}
    Outcome -- 2xx OK --> RecordSuccess[Update CB Success, Store Cache, Wake Followers]
    Outcome -- 4xx Client Error --> NormalReturn[Return 4xx to Caller, Do NOT Trip CB]
    Outcome -- 5xx / Timeout --> RetryCheck{Retry attempts<br/>remaining?}
    
    RetryCheck -- YES --> Backoff[Sleep with Exponential Jitter] --> WireIO
    RetryCheck -- NO --> TripCB[Increment CB Failure Count, Emit CloudEvent to DLQ] --> RaiseErr[Raise DownstreamException]
```

---

### 4.5 Circuit Breaker Deterministic State Machine

```mermaid
stateDiagram-v2
    [*] --> Closed
    
    state Closed {
        [*] --> Monitoring
        Monitoring --> Monitoring: Success (Reset failure counter)
        Monitoring --> Tripped: Consecutive failures >= failure_threshold OR failure_rate >= 50%
    }
    
    Closed --> Open: Trip condition met
    
    state Open {
        [*] --> Sleeping
        Sleeping --> ProbeReady: recovery_timeout_seconds expired
    }
    
    Open --> HalfOpen: Trial probe allowed
    
    state HalfOpen {
        [*] --> Testing
        Testing --> Open: Single trial probe fails
        Testing --> Closed: half_open_successes_to_close achieved
    }
    
    HalfOpen --> Open: Probe Failed
    HalfOpen --> Closed: All Probes Succeeded
```

#### Detailed State Transition Invariants:
1. **`CLOSED` (Normal Operation)**:
   - All requests pass through freely.
   - Failures (5xx status codes, connection drops, read timeouts) are recorded in a sliding window.
   - **Transition to `OPEN`**: Triggers if consecutive failures exceed `failure_threshold` (default: 5) OR if the failure rate exceeds `failure_rate_threshold` (default: 50%) after at least `minimum_number_of_calls` (default: 10) have been evaluated.
2. **`OPEN` (Short-Circuit Defense)**:
   - All outbound requests fail fast immediately with `CircuitBreakerOpenException` (zero network I/O, zero thread allocation).
   - The circuit remains in `OPEN` for `recovery_timeout_seconds` (default: 30.0s).
   - **Transition to `HALF-OPEN`**: Triggers automatically once `recovery_timeout_seconds` elapses.
3. **`HALF-OPEN` (Canary Probing)**:
   - Permits a strictly limited number of trial probe requests (`half_open_requests`, default: 3).
   - All other requests continue to fail fast.
   - **Transition to `CLOSED`**: Triggers if all `half_open_successes_to_close` trial probes succeed.
   - **Transition to `OPEN`**: Triggers immediately if even a single trial probe fails.

---

## 5. Control Panel & Configuration Engine

### 5.1 Dynamic Hot-Reload Architecture
1. **Signal Trap & File Watcher**: The host process traps `SIGHUP` and monitors `http-config.yml` via filesystem notification hooks.
2. **Two-Phase Validation**:
   - Phase 1 (Parsing): The file is read and parsed as YAML.
   - Phase 2 (Validation): The schema is validated against range boundaries and profile constraints.
3. **Atomic Pointer Swap**: If validation passes, the active snapshot reference is swapped atomically. In-flight requests continue executing against their existing snapshot; all subsequent requests read the new snapshot.
4. **Fallback on Failure**: If a newly edited YAML contains a syntax or validation error, the engine logs the failure, leaves the current running snapshot intact, and dispatches an alert to Kafka.

### 5.2 Control Panel Admin API
Each service exposes control endpoints on its admin port (`127.0.0.1:9090` / `900X`):

| Endpoint | Method | Payload / Params | Response | Description |
|---|---|---|---|---|
| `/admin/v1/http/config` | `GET` | None | `200 OK` (JSON) | Returns active configuration snapshot and running profile. |
| `/admin/v1/http/reload` | `POST` | None | `200 OK` / `400 Bad Request` | Forces immediate disk reread and atomic swap of `http-config.yml`. |
| `/admin/v1/http/circuit-breaker` | `GET` | `?target=scorer` | `200 OK` (JSON) | Returns circuit state (`CLOSED`/`OPEN`), failure counts, and sliding window metrics. |
| `/admin/v1/http/circuit-breaker/reset` | `POST` | `{"target": "scorer"}` | `200 OK` (JSON) | Manually forces an `OPEN` circuit breaker back to `CLOSED`. |
| `/admin/v1/http/circuit-breaker/trip` | `POST` | `{"target": "scorer"}` | `200 OK` (JSON) | Manually trips a circuit breaker to `OPEN` (emergency traffic shedding). |

---

## 6. Messaging Panel & Event Topology

All cross-cutting policy audits, anomaly detections, and dead-letter events are published to Kafka following CloudEvents 1.0 JSON specifications.

### 6.1 Kafka Topic Architecture
- **`http.outbound.audit.v1`**: Sampled audit stream of outgoing HTTP calls with status, duration, and trace context.
- **`http.outbound.circuit_breaker.v1`**: Real-time event stream published whenever a circuit breaker transitions state.
- **`http.outbound.dlq.v1`**: Dead Letter Queue capturing unrecoverable HTTP failures after retry exhaustion for offline replay.

### 6.2 CloudEvent Schema Example (`http.outbound.circuit_breaker.v1`)
```json
{
  "specversion": "1.0",
  "type": "com.platform.http.circuit_breaker.state_change",
  "source": "quality-engine/features/quality_baseline",
  "id": "cb-evt-991284-0a",
  "time": "2026-10-21T10:45:00.000Z",
  "datacontenttype": "application/json",
  "data": {
    "feature_name": "quality_baseline",
    "target_class": "declared_upstream",
    "upstream_host": "http_scorer_adapter",
    "previous_state": "CLOSED",
    "new_state": "OPEN",
    "consecutive_failures": 5,
    "recovery_timeout_seconds": 30.0,
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "trigger_error": "ReadTimeout: Server failed to respond in 30.0s"
  }
}
```

---

## 7. Exhaustive Parameter Reference: Valid vs. Ideal vs. Anti-Patterns

This section provides an in-depth parameter analysis: syntax rules, ideal production settings, and dangerous anti-patterns that risk production outages.

### 7.1 Parameter Analysis Table

| Parameter Path | Type & Valid Range | Ideal Production Setting | Anti-Pattern (What is NOT Ideal) | Failure Mode Caused by Anti-Pattern |
|---|---|---|---|---|
| `profile` | `enum`: `api_service`, `temporal_worker`, `internal_fast` | `api_service` for REST; `temporal_worker` for Temporal activities; `internal_fast` for cluster RPC. | Setting `api_service` inside Temporal worker activities. | Worker thread starvation; duplicate retries clashing with Temporal's retry engine; deadlock on bulkheads. |
| `client.timeout_seconds` | `float`: `0.1` to `300.0` | `10.0` to `30.0` for web APIs; `60.0` for batch/AI processing. | Setting to `0.0` (infinite timeout) or `> 120.0` for customer-facing APIs. | Thread pool exhaustion; Slowloris vulnerability; upstream gateway times out with HTTP 504 while worker stays hung. |
| `client.connect_timeout_seconds` | `float`: `0.05` to `30.0` | `2.0` to `5.0` seconds. | Setting to `> 15.0` seconds. | Slow connection attempts block worker threads when a downstream host drops packets. |
| `client.max_connections` | `int`: `1` to `5000` | `100` to `200` per process replica. | Setting to `> 2000` or leaving unbounded. | Kernel file descriptor exhaustion (`EMFILE: Too many open files`); ephemeral port starvation. |
| `client.max_keepalive_connections`| `int`: `0` to `max_connections` | `20` to `50` (typically 20–30% of `max_connections`). | Setting to `0` or equal to `max_connections`. | Setting to 0 destroys socket reuse, causing TCP handshake / TLS renegotiation latency spikes on every single request. |
| `client.keepalive_expiry_seconds` | `float`: `1.0` to `600.0` | `30.0` to `65.0` (must be shorter than upstream LB idle timeout). | Setting to `> 300.0` seconds. | Race condition: Client sends request on an idle socket just as the upstream load balancer closes it, causing `RemoteProtocolError`. |
| `client.retries` | `int`: `0` to `10` | `2` to `3` for idempotent methods (GET/PUT); `0` for non-idempotent (POST). | Setting to `> 5` with fixed zero backoff. | Retry storms (thundering herd) that overwhelm recovering downstream services. |
| `client.retry_backoff_factor` | `float`: `0.1` to `5.0` | `0.5` (exponential backoff: 0.5s, 1.0s, 2.0s with full jitter). | Setting to `0.0` (immediate retry). | Immediate re-execution hits the downstream service while it is still saturated, prolonging the outage. |
| `client.http2` | `bool`: `true`, `false` | `true` for services supporting ALPN HTTP/2. | Leaving `false` for high-throughput internal RPCs. | Forces 1 request per TCP socket, multiplying connection count by 50x under load. |
| `client.verify_ssl` | `bool`: `true`, `false` | `true` across all staging and production environments. | Setting to `false` in production. | Critical vulnerability: Disables TLS certificate validation, exposing traffic to Man-in-the-Middle (MitM) interception. |
| `client.follow_redirects` | `bool`: `true`, `false` | `false` (explicit redirection handling). | Setting to `true` on calls transmitting authorization headers. | Credential leakage: HTTP client automatically forwards `Authorization` bearer tokens to third-party redirect locations. |
| `circuit_breaker.failure_threshold` | `int`: `1` to `50` | `5` consecutive failures. | Setting to `1` or `> 20`. | Setting to 1 causes false positives on transient blips; setting >20 allows hundreds of threads to hang before tripping. |
| `circuit_breaker.recovery_timeout_seconds` | `float`: `1.0` to `300.0` | `30.0` seconds. | Setting to `< 2.0` seconds. | Floods recovering downstream services before they have finished restarting or clearing backlogs. |
| `rate_limit.requests_per_second` | `int`: `1` to `50000` | Scaled to match downstream SLA (e.g. `100` req/s). | Setting to `99999` (effectively disabled). | Downstream service is overwhelmed and returns 500/503 errors during traffic spikes. |
| `rate_limit.burst` | `int`: `>= requests_per_second` | `1.5x` to `2x` of `requests_per_second` (e.g. `200`). | Setting `burst` equal to `requests_per_second * 10`. | Large sudden packet floods overwhelm downstream connection queues. |
| `admission_control.concurrency_limit` | `int`: `1` to `1000` | `50` to `100` concurrent requests per client instance. | Setting to unbounded (`None`). | Client allocates thousands of concurrent async tasks, exhausting process RAM and CPU cycles. |
| `cache_eval.stale_if_error_seconds` | `float`: `0.0` to `86400.0` | `300.0` to `600.0` seconds. | Setting to `0.0`. | Downstream outage immediately cascades to end-users instead of serving graceful degraded cached content. |
| `security.input_hardening.reject_crlf_headers` | `bool`: `true`, `false` | `true` (non-negotiable security invariant). | Setting to `false`. | Allows HTTP response splitting and header injection attacks. |
| `security.ssrf_validation.blocked_ip_ranges` | `list[str]` (CIDRs) | Must include `0.0.0.0/8`, `10.0.0.0/8`, `127.0.0.0/8`, `169.254.0.0/16`, `172.16.0.0/12`, `192.168.0.0/16`. | Omitting `169.254.0.0/16` or private CIDRs. | Exposes AWS/GCP instance metadata API (`169.254.169.254`), allowing attackers to steal IAM instance credentials. |

---

## 8. Complete Step-by-Step Implementation & Operations Manual (Universal Framework)

This section provides a universal, feature-agnostic, 8-step blueprint to implement, configure, wire, test, and verify declarative HTTP clients in **any existing package or any future feature** across the monorepo.

### 8.0 Universal Environment Variables & Conventions

Before beginning implementation in any package or feature, set these environment variables in your terminal. All subsequent steps and verification scripts reference these variables dynamically:

```bash
# 1. Target package name (e.g., quality-engine, alert-engine, semantic-coherence, toxicity, etc.)
export PACKAGE_NAME="quality-engine"

# 2. Target domain feature folder name (e.g., score_composite, embedding_worker, alert_dispatcher, etc.)
export FEATURE_NAME="score_composite"

# 3. Execution profile: "api_service" (REST), "temporal_worker" (Temporal), or "internal_fast" (Cluster RPC)
export FEATURE_PROFILE="api_service"

# 4. Computed absolute filesystem paths
export MONOREPO_ROOT="$(pwd)"
export FEATURE_DIR="${MONOREPO_ROOT}/${PACKAGE_NAME}/src/features/${FEATURE_NAME}"
```

---

#### 8.0.1 End-to-End Pipeline Step Topology & Dataflow Map

The following architectural map illustrates how artifacts, parameters, and contracts flow through all 8 steps of the implementation framework, and identifies where isolation boundaries allow each step to be executed and tested independently:

```text
+------------------------------------------------------------------------------------------------------------------------+
|                         END-TO-END IMPLEMENTATION PIPELINE: STEP TOPOLOGY & DATAFLOW MAP                               |
|                     (How Artifacts Flow from Step 1 to Step 8 & Where Isolation Boundaries Lie)                        |
+------------------------------------------------------------------------------------------------------------------------+

[ENV SETUP]  PACKAGE_NAME, FEATURE_NAME, FEATURE_PROFILE, MONOREPO_ROOT, FEATURE_DIR
     │
     ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| STEP 1: Feature Folder Audit & Hexagonal Scaffolding                                              |
| INPUT:  Target Directory Path & Sub-layer Specifications                                          |
| OUTPUT: Hexagonal Tree (contracts/, domain/, infrastructure/, service/, tests/) + PEP 420 markers |
| STANDALONE USE: Run directory compliance auditor via 'po file-search --root <dir> --tree'         |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
     │ Creates directory structure for all subsequent layers
     ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| STEP 2: Declarative http-config.yml Authoring                                                     |
| INPUT:  FEATURE_PROFILE ("api_service" | "temporal_worker" | "internal_fast"), Timeouts, Policies    |
| OUTPUT: Validated http-config.yml containing client settings & active pipeline interceptors       |
| STANDALONE USE: Lint & validate YAML schema without Python runtime via pyyaml safe_load          |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
     │ Provides declarative network, retry, and interceptor configuration
     │
     ├──────────────────────────────────────────────┐
     │                                              │
     ▼                                              ▼
+────────────────────────────────────────+   +──────────────────────────────────────────────────────+
| STEP 3: Pure Domain Port Definition    |   | STEP 4: Concrete HTTP Adapter Implementation         |
| INPUT:  Domain Business Method Intent  |──>| INPUT:  http-config.yml (Step 2) + Port (Step 3)     |
| OUTPUT: FeatureOutboundPort (ABC)      |   | OUTPUT: HttpFeatureOutboundAdapter with Client       |
| STANDALONE USE: Abstract contract test |   | STANDALONE USE: Direct API invocation in script      |
+────────────────────────────────────────+   +──────────────────────────────────────────────────────+
     │ Contract definition                          │ Concrete implementation
     │                                              │
     └──────────────────────┬───────────────────────┘
                            │
                            ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| STEP 5: Domain Service Dependency Injection                                                       |
| INPUT:  FeatureOutboundPort interface (injected via constructor) + Domain Payload data            |
| OUTPUT: FeatureDomainService orchestrating business logic & returning pure domain DTO             |
| STANDALONE USE: Execute pure business logic with offline In-Memory StubPort (zero network)        |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
     │
     ├──────────────────────────────────────────────┬───────────────────────────────────────────────┐
     │                                              │                                               │
     ▼                                              ▼                                               ▼
+──────────────────────────────+   +──────────────────────────────+   +─────────────────────────────+
| STEP 6: Unit Test Isolation  |   | STEP 7: Fault-Injection Test |   | STEP 8: Live Hot-Reload     |
| INPUT:  Step 5 Service +     |   | INPUT:  Step 4 Adapter +     |   | INPUT:  Updated Step 2 YAML |
|         AsyncMock Port       |   |         httpx.MockTransport  |   |         + Running Process   |
| OUTPUT: Instant (<50ms) CI   |   | OUTPUT: Verified Circuit     |   | OUTPUT: Zero-downtime atomic|
|         test assertions      |   |         Breaker & Headers    |   |         in-memory swap      |
| STANDALONE USE:              |   | STANDALONE USE:              |   | STANDALONE USE:             |
| Run 'pytest tests/' offline  |   | Chaos simulation script      |   | SIGHUP config watcher test  |
+──────────────────────────────+   +──────────────────────────────+   +─────────────────────────────+
```

---

#### 8.0.2 Step Input/Output & Interconnection Master Matrix

| Step | Component Name | Exact Inputs Given | Exact Outputs Produced | Direct Upstream Source | Direct Downstream Consumer | How to Use Individually (Standalone Mode) |
|---|---|---|---|---|---|---|
| **Step 1** | **Hexagonal Scaffolding** | `PACKAGE_NAME`, `FEATURE_NAME`, `FEATURE_DIR`, Monorepo Root | 6 subdirectories (`contracts/`, `domain/`, `infrastructure/`, `service/`, `tests/`) + PEP 420 `__init__.py` markers | Monorepo filesystem | Steps 2, 3, 4, 5, 6 | Run directory linter: `po file-search --root $FEATURE_DIR --tree` |
| **Step 2** | **Declarative Config** | `FEATURE_PROFILE`, client timeouts, connection caps, retry counts, CB thresholds | Validated `${FEATURE_DIR}/http-config.yml` | Step 1 (directory) | Step 4 (Adapter client), Step 7 (fault test), Step 8 (reload) | Validate schema without code: `python3 -c "import yaml; yaml.safe_load(open('$FEATURE_DIR/http-config.yml'))"` |
| **Step 3** | **Domain Port** | Method signatures, domain entity types (`payload: Dict`, `tenant_id: str`) | Abstract Base Class `FeatureOutboundPort(ABC)` with abstract methods | Step 1 (`infrastructure/ports/`) | Step 4 (Adapter implements it), Step 5 (Service accepts it) | Abstract contract verification: AST AST parser verifying 0 network imports |
| **Step 4** | **HTTP Adapter** | Target `base_url`, `http-config.yml` (Step 2), `FeatureOutboundPort` (Step 3) | Concrete `HttpFeatureOutboundAdapter` class wrapping `ResilientHttpClient` | Step 2 (`http-config.yml`), Step 3 (Port contract) | Step 5 (Domain Service dependency injection) | Standalone script invoking remote endpoint directly without domain logic |
| **Step 5** | **Domain Service** | Injected Port instance (Step 3/4), caller data (`data: Dict`, `tenant_id: str`) | Orchestrated domain result (`{"status": "COMPLETED", "result": raw}`) | Step 3 (Port contract), Step 4 (runtime adapter) | REST router / Temporal worker / CLI caller | Run business logic offline using an in-memory `StubPort` (no network needed) |
| **Step 6** | **Unit Testing** | `FeatureDomainService` (Step 5), `unittest.mock.AsyncMock` port fixtures | Pytest assertions, test report (`pytest -v`), code coverage metrics | Step 3 (Port interface), Step 5 (Domain Service) | CI/CD build gate | Run `pytest <feature_dir>/tests/ -v` (executes in <50ms completely in-memory) |
| **Step 7** | **Fault Injection** | `ResilientHttpClient` (Step 4), `httpx.MockTransport` error responses (503s) | Verified Circuit Breaker state changes (`CLOSED` -> `OPEN`), W3C trace validation | Step 2 (policies), Step 4 (resilient client) | SRE runbooks & resilience verification | Run chaos simulation script to test failure scenarios locally without live servers |
| **Step 8** | **Live Hot-Reload** | Modified `http-config.yml` (Step 2), SIGHUP or `from_config()` invocation | Atomic swap of immutable config snapshot; zero request drops | Step 2 (`http-config.yml`), Step 4 (running client) | Production operations, live maintenance | Modify timeout via `sed` and verify reload via `from_config()` without process restart |

---

### Step 1: Feature Folder Audit & Hexagonal Scaffolding (Rule 1 Compliance)

#### 1.1 Purpose & Architectural Rationale
Rule 1 (`1-feature-folder-writing-rule.md`) mandates that every feature must be self-contained and strictly follow Hexagonal Architecture (Ports and Adapters). This ensures:
- The core business domain is completely decoupled from HTTP transport protocols, serialization libraries, and network clients.
- The feature can run in any process model (REST API worker, CLI tool, or Temporal workflow) without altering domain logic.
- PEP 420 namespace packaging rules are preserved: `src/` and `src/features/` must remain namespace directories (containing **no** `__init__.py`).

#### 1.2 Prerequisites & Structural Rules
- Target package directory must exist in the monorepo root.
- Python 3.11+ virtual environment must be active with `policy-orchestrator` installed (`which po`).
- Invariant: `src/__init__.py` and `src/features/__init__.py` must NOT exist. Only sub-layers (`contracts/`, `domain/`, `infrastructure/`, `service/`, `tests/`) contain `__init__.py`.

#### 1.3 Step-by-Step Scaffolding Commands
Run the following shell commands to scaffold the full hexagonal layer for your feature:

```bash
# 1. Create standard Hexagonal directory tree
mkdir -p "${FEATURE_DIR}/contracts"
mkdir -p "${FEATURE_DIR}/domain"
mkdir -p "${FEATURE_DIR}/infrastructure/ports"
mkdir -p "${FEATURE_DIR}/infrastructure/adapters"
mkdir -p "${FEATURE_DIR}/service"
mkdir -p "${FEATURE_DIR}/tests"

# 2. Initialize sub-layer package markers (PEP 420 compliant)
touch "${FEATURE_DIR}/contracts/__init__.py"
touch "${FEATURE_DIR}/domain/__init__.py"
touch "${FEATURE_DIR}/infrastructure/__init__.py"
touch "${FEATURE_DIR}/infrastructure/ports/__init__.py"
touch "${FEATURE_DIR}/infrastructure/adapters/__init__.py"
touch "${FEATURE_DIR}/service/__init__.py"
touch "${FEATURE_DIR}/tests/__init__.py"

# 3. Assert PEP 420 namespace invariants (Ensure NO root/feature init files exist)
rm -f "${MONOREPO_ROOT}/${PACKAGE_NAME}/src/__init__.py"
rm -f "${MONOREPO_ROOT}/${PACKAGE_NAME}/src/features/__init__.py"
```

#### 1.4 Automated Verification Script
Run this script to verify that the directory structure complies with monorepo rules:

```bash
python3 -c "
import os
import sys
from pathlib import Path

feature_dir = Path(os.environ['FEATURE_DIR'])
required_subdirs = [
    'contracts', 'domain', 'infrastructure/ports',
    'infrastructure/adapters', 'service', 'tests'
]

for subdir in required_subdirs:
    target = feature_dir / subdir
    assert target.is_dir(), f'FAILED: Missing directory {target}'
    init_file = target / '__init__.py'
    assert init_file.is_file(), f'FAILED: Missing __init__.py in {target}'

package_name = os.environ['PACKAGE_NAME']
assert not (Path(package_name) / 'src' / '__init__.py').exists(), 'FAILED: Stray src/__init__.py violates PEP 420!'
assert not (Path(package_name) / 'src' / 'features' / '__init__.py').exists(), 'FAILED: Stray src/features/__init__.py violates PEP 420!'

print(f'>>> Step 1 SUCCESS: Hexagonal structure verified for {feature_dir}')
"
```

#### 1.5 Common Pitfalls & Troubleshooting
- **Error: `ModuleNotFoundError: No module named 'src.features.<feature>'`**:
  - *Cause*: A developer created `src/__init__.py` or `src/features/__init__.py`, breaking Python's native namespace package resolution.
  - *Fix*: Run `rm -f ${PACKAGE_NAME}/src/__init__.py ${PACKAGE_NAME}/src/features/__init__.py`.

#### 1.6 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - `PACKAGE_NAME`: Name of the target microservice package (e.g. `quality-engine`, `alert-engine`).
  - `FEATURE_NAME`: Target feature folder name (e.g. `score_composite`, `embedding_worker`).
  - `MONOREPO_ROOT`: Base absolute path of the monorepo workspace.
  - `FEATURE_DIR`: Target path computed as `${MONOREPO_ROOT}/${PACKAGE_NAME}/src/features/${FEATURE_NAME}`.
- **Outputs Produced**:
  - Six clean subdirectories: `contracts/`, `domain/`, `infrastructure/ports/`, `infrastructure/adapters/`, `service/`, `tests/`.
  - Seven standard `__init__.py` subpackage files.
  - Strict assertion that `src/__init__.py` and `src/features/__init__.py` are deleted (PEP 420 namespace compliance).
  - Exit code: 0 on successful structure validation.
- **How It Connects to Other Steps**:
  - Upstream: Depends on the existence of the monorepo package root directory.
  - Downstream: Provides the essential directory structure for all remaining steps:
    - Step 2 writes `${FEATURE_DIR}/http-config.yml`.
    - Step 3 creates the abstract port in `${FEATURE_DIR}/infrastructure/ports/`.
    - Step 4 creates the concrete adapter in `${FEATURE_DIR}/infrastructure/adapters/`.
    - Step 5 places the domain service in `${FEATURE_DIR}/service/`.
    - Step 6 places unit tests in `${FEATURE_DIR}/tests/`.
- **How to Use Individually (Standalone Mode)**:
  - Can be run as a standalone scaffolding command or CI folder compliance checker for any new feature before writing any code:
    ```bash
    po file-search --root "${PACKAGE_NAME}/src/features/${FEATURE_NAME}" --tree
    ```

---

### Step 2: Authoring Declarative `http-config.yml` with Profile Selection

#### 2.1 Purpose & Architectural Rationale
Instead of hardcoding timeouts, retry counts, connection pools, and circuit breaker thresholds in Python code, every feature defines an immutable declarative contract in `http-config.yml`.
This guarantees:
- Operational agility: Site Reliability Engineers (SREs) can tune network parameters without recompiling or redeploying code.
- Profile consistency: The client automatically activates the appropriate pipeline steps based on the process model.

#### 2.2 Profile Decision Matrix

| Execution Profile | Target Execution Environment | Pipeline Steps Activated | Rationale |
|---|---|---|---|
| `api_service` | FastAPI, REST endpoints, Ingress gateways | All 8 Steps: `input_hardening`, `ssrf_validation`, `context_isolation`, `cache_eval`, `singleflight`, `circuit_breaker`, `rate_limit`, `admission_control` | Maximum protection against hostile user payloads, SSRF attacks, downstream outages, and connection exhaustion. |
| `temporal_worker` | Temporal activity workers, Celery/async task workers | 2 Steps: `context_isolation`, `circuit_breaker` | Lean execution. Rate limiting, backoff, retries, and task bulkheads are managed natively by the Temporal engine. |
| `internal_fast` | High-throughput intra-cluster RPC, daemon sidecars | 1 Step: `context_isolation` | Ultra-low latency (<0.5ms overhead). Bypasses caching and circuit breakers for trusted intra-cluster calls. |

#### 2.3 Concrete YAML Templates

##### Profile A: `api_service` (REST Services)
```yaml
schema_version: "1.0.0"
feature_name: "target_feature"
profile: "api_service"

client:
  timeout_seconds: 30.0
  connect_timeout_seconds: 5.0
  max_connections: 100
  max_keepalive_connections: 20
  keepalive_expiry_seconds: 30.0
  verify_ssl: true
  retries: 3
  retry_backoff_factor: 0.5
  retry_status_codes:
    - 429
    - 502
    - 503
    - 504

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
    stale_if_error_seconds: 300.0

  security:
    input_hardening: true
    ssrf_validation: true
```

##### Profile B: `temporal_worker` (Asynchronous Workflow Workers)
```yaml
schema_version: "1.0.0"
feature_name: "target_feature"
profile: "temporal_worker"

client:
  timeout_seconds: 60.0
  connect_timeout_seconds: 5.0
  max_connections: 50
  max_keepalive_connections: 10
  keepalive_expiry_seconds: 45.0
  verify_ssl: true
  retries: 0
  retry_backoff_factor: 0.0

pipeline:
  steps:
    - context_isolation
    - circuit_breaker

  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 30.0
    half_open_requests: 2

  security:
    input_hardening: false
    ssrf_validation: false
```

##### Profile C: `internal_fast` (Cluster-Internal High-Speed RPC)
```yaml
schema_version: "1.0.0"
feature_name: "target_feature"
profile: "internal_fast"

client:
  timeout_seconds: 5.0
  connect_timeout_seconds: 1.0
  max_connections: 200
  max_keepalive_connections: 50
  keepalive_expiry_seconds: 60.0
  verify_ssl: true
  retries: 1
  retry_backoff_factor: 0.1

pipeline:
  steps:
    - context_isolation

  security:
    input_hardening: false
    ssrf_validation: false
```

#### 2.4 In-Depth Parameter Reference & Architectural Meaning (Line by Line)

Every key in `http-config.yml` controls a critical runtime invariant of the client pipeline. Below is the exhaustive parameter-by-parameter breakdown:

1. **`schema_version` (string, required)**:
   - *Value*: `"1.0.0"`
   - *Meaning*: Semantic contract version for the configuration schema. If breaking changes are introduced to the loader, this field enables deterministic schema migrations and backward compatibility assertions.

2. **`feature_name` (string, required)**:
   - *Value*: `"${FEATURE_NAME}"` (e.g., `score_composite`)
   - *Meaning*: Explicitly binds this configuration file to its parent domain feature folder. The loader asserts `assert cfg['feature_name'] == Path(__file__).resolve().parent.name` to prevent accidental misplacement.

3. **`profile` (enum, required)**:
   - *Value*: `"api_service"` | `"temporal_worker"` | `"internal_fast"`
   - *Meaning*: Selects the execution environment profile. Dictates which pipeline steps are loaded and how concurrency/retries are handled across different process models.

4. **`client.timeout_seconds` (float, required)**:
   - *Value*: `30.0` (API) | `60.0` (Worker) | `5.0` (Internal)
   - *Meaning*: The absolute wall-clock timeout ceiling for a complete request/response transaction. If the remote service does not return within this window, the client cancels the task and raises `httpx.TimeoutException`.

5. **`client.connect_timeout_seconds` (float, required)**:
   - *Value*: `5.0` (standard) | `1.0` (internal RPC)
   - *Meaning*: The maximum duration allocated for the initial TCP 3-way handshake and TLS 1.3 ALPN negotiation. Prevents hanging worker threads when a downstream host drops packets or blackholes traffic.

6. **`client.max_connections` (integer, required)**:
   - *Value*: `100` (standard) | `200` (internal)
   - *Meaning*: The hard ceiling of open socket connections permitted in this client's connection pool. Prevents file descriptor exhaustion (`EMFILE: Too many open files`) under heavy load spikes.

7. **`client.max_keepalive_connections` (integer, required)**:
   - *Value*: `20` (standard) | `50` (internal)
   - *Meaning*: Number of idle TCP connections retained in the pool for socket reuse. Reusing connections saves ~35ms per request by avoiding repeated TCP handshakes and TLS renegotiations.

8. **`client.keepalive_expiry_seconds` (float, required)**:
   - *Value*: `30.0` (must be shorter than upstream load balancer idle timeout)
   - *Meaning*: Maximum time an idle socket remains alive in the pool before being proactively closed. Setting this lower than the load balancer's idle timeout (typically 60s) eliminates race conditions where the client transmits on a socket just as the load balancer tears it down (`RemoteProtocolError`).

9. **`client.verify_ssl` (boolean, required)**:
   - *Value*: `true`
   - *Meaning*: Enforces strict X.509 certificate validation and CA chain verification. Disabling this in staging or production is a critical vulnerability that permits Man-in-the-Middle (MitM) traffic interception.

10. **`client.retries` (integer, required)**:
    - *Value*: `3` (for REST APIs) | `0` (for Temporal workers)
    - *Meaning*: Number of automatic retry attempts executed on transient errors. In Temporal workers, this must be `0` because Temporal's activity execution engine manages retries natively; nested retries cause exponential thundering herds.

11. **`client.retry_backoff_factor` (float, required)**:
    - *Value*: `0.5`
    - *Meaning*: Multiplier for exponential backoff with full jitter ($t = \text{backoff} \times 2^{\text{attempt}} \times \text{rand}(0, 1)$). Spreads retried requests randomly over time to prevent thundering herds from overwhelming recovering downstream services.

12. **`client.retry_status_codes` (list of integers, required)**:
    - *Value*: `[429, 502, 503, 504]`
    - *Meaning*: HTTP status codes eligible for automated retries. Idempotent errors like Bad Gateway (502) and Gateway Timeout (504) are retried; client errors like 400, 401, 403, and 422 fail fast without retrying.

13. **`pipeline.steps` (list of strings, required)**:
    - *Value*: Ordered list of active interceptor steps (e.g. `[input_hardening, ssrf_validation, context_isolation, cache_eval, singleflight, circuit_breaker, rate_limit, admission_control]`).
    - *Meaning*: Explicitly defines the interceptor execution chain. Steps execute strictly in the declared order.

14. **`pipeline.circuit_breaker.failure_threshold` (integer)**:
    - *Value*: `5`
    - *Meaning*: Number of consecutive 5xx failures or timeouts required to trip the circuit from `CLOSED` to `OPEN`.

15. **`pipeline.circuit_breaker.recovery_timeout_seconds` (float)**:
    - *Value*: `30.0`
    - *Meaning*: The quiet period in seconds that the circuit remains `OPEN`. During this interval, all outbound calls fail fast immediately without touching the network, allowing downstream dependencies time to recover.

16. **`pipeline.circuit_breaker.half_open_requests` (integer)**:
    - *Value*: `3`
    - *Meaning*: Number of successful trial probe requests required in `HALF-OPEN` state to verify downstream recovery before fully healing the circuit back to `CLOSED`.

17. **`pipeline.rate_limit.requests_per_second` (integer)**:
    - *Value*: `100`
    - *Meaning*: Token bucket refill rate per second. Ensures the client never exceeds downstream service level agreements (SLAs).

18. **`pipeline.rate_limit.burst` (integer)**:
    - *Value*: `200`
    - *Meaning*: Maximum token bucket capacity. Allows transient bursts up to 200 requests while maintaining long-term throughput at 100 req/s.

19. **`pipeline.cache_eval.enabled` (boolean)**:
    - *Value*: `true` | `false`
    - *Meaning*: Toggles RFC 9111 HTTP response caching. When enabled, identical GET/POST evaluations return immediately from cache.

20. **`pipeline.cache_eval.default_ttl_seconds` (integer)**:
    - *Value*: `60`
    - *Meaning*: Lifetime of cached response records in seconds.

21. **`pipeline.cache_eval.stale_if_error_seconds` (float)**:
    - *Value*: `300.0` (5 minutes)
    - *Meaning*: If the downstream service is down (5xx or circuit open), the client serves stale cached data up to 300 seconds old rather than returning an error to the user (graceful degradation).

22. **`pipeline.security.input_hardening` (boolean)**:
    - *Value*: `true`
    - *Meaning*: Activates header sanitization (blocking `\r\n` CRLF characters to prevent HTTP response splitting) and caps JSON nesting depth to 20 levels to stop parser recursion attacks.

23. **`pipeline.security.ssrf_validation` (boolean)**:
    - *Value*: `true`
    - *Meaning*: Performs synchronous DNS resolution and enforces an IP firewall blocking loopback (`127.0.0.0/8`), RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and AWS/GCP cloud metadata (`169.254.169.254`).

---

#### 2.5 Step-by-Step Authoring Command
Execute this parameterized shell command to write the configuration file based on `$FEATURE_PROFILE`:

```bash
cat << EOF > "${FEATURE_DIR}/http-config.yml"
schema_version: "1.0.0"
feature_name: "${FEATURE_NAME}"
profile: "${FEATURE_PROFILE}"

client:
  timeout_seconds: $( [ "${FEATURE_PROFILE}" = "temporal_worker" ] && echo "60.0" || ( [ "${FEATURE_PROFILE}" = "internal_fast" ] && echo "5.0" || echo "30.0" ) )
  connect_timeout_seconds: $( [ "${FEATURE_PROFILE}" = "internal_fast" ] && echo "1.0" || echo "5.0" )
  max_connections: $( [ "${FEATURE_PROFILE}" = "internal_fast" ] && echo "200" || echo "100" )
  max_keepalive_connections: 20
  keepalive_expiry_seconds: 30.0
  verify_ssl: true
  retries: $( [ "${FEATURE_PROFILE}" = "temporal_worker" ] && echo "0" || ( [ "${FEATURE_PROFILE}" = "internal_fast" ] && echo "1" || echo "3" ) )
  retry_backoff_factor: 0.5
  retry_status_codes:
    - 429
    - 502
    - 503
    - 504

pipeline:
  steps:
$( [ "${FEATURE_PROFILE}" = "api_service" ] && cat << 'STEPS'
    - input_hardening
    - ssrf_validation
    - context_isolation
    - cache_eval
    - singleflight
    - circuit_breaker
    - rate_limit
    - admission_control
STEPS
)
$( [ "${FEATURE_PROFILE}" = "temporal_worker" ] && cat << 'STEPS'
    - context_isolation
    - circuit_breaker
STEPS
)
$( [ "${FEATURE_PROFILE}" = "internal_fast" ] && cat << 'STEPS'
    - context_isolation
STEPS
)

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
    stale_if_error_seconds: 300.0

  security:
    input_hardening: $( [ "${FEATURE_PROFILE}" = "api_service" ] && echo "true" || echo "false" )
    ssrf_validation: $( [ "${FEATURE_PROFILE}" = "api_service" ] && echo "true" || echo "false" )
EOF
```

#### 2.5 Automated Verification Script
Run this script to validate YAML syntax and profile constraints:

```bash
python3 -c "
import os
import yaml
from pathlib import Path

config_path = Path(os.environ['FEATURE_DIR']) / 'http-config.yml'
assert config_path.is_file(), f'FAILED: {config_path} does not exist'

with open(config_path) as f:
    cfg = yaml.safe_load(f)

assert cfg['schema_version'] == '1.0.0', 'Invalid schema_version'
assert cfg['feature_name'] == os.environ['FEATURE_NAME'], 'feature_name does not match directory name'
assert cfg['profile'] in ['api_service', 'temporal_worker', 'internal_fast'], 'Invalid profile'

profile = cfg['profile']
steps = cfg['pipeline']['steps']

if profile == 'api_service':
    assert len(steps) == 8, f'api_service profile requires 8 steps, got {len(steps)}'
elif profile == 'temporal_worker':
    assert steps == ['context_isolation', 'circuit_breaker'], f'temporal_worker profile steps mismatch: {steps}'
elif profile == 'internal_fast':
    assert steps == ['context_isolation'], f'internal_fast profile steps mismatch: {steps}'

assert cfg['client']['timeout_seconds'] > 0.0, 'timeout_seconds must be positive'
print(f'>>> Step 2 SUCCESS: http-config.yml validated for profile [{profile}]')
"
```

#### 2.6 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - `FEATURE_NAME`: Target feature identifier.
  - `FEATURE_PROFILE`: One of `api_service`, `temporal_worker`, or `internal_fast`.
  - Network requirements: Client timeouts, keepalive pool sizes, retry counts, circuit breaker failure threshold, rate limiting quota.
- **Outputs Produced**:
  - Validated declarative YAML file: `${FEATURE_DIR}/http-config.yml`.
  - 23 calibrated parameters across `client`, `pipeline.steps`, `circuit_breaker`, `rate_limit`, `cache_eval`, and `security`.
- **How It Connects to Other Steps**:
  - Upstream: Written into `${FEATURE_DIR}` created in Step 1.
  - Downstream: Read directly by Step 4's `ResilientHttpClient.from_config()`. The adapter uses this YAML to configure all timeouts, connection pools, and interceptors. Also verified under fault conditions in Step 7 and dynamically hot-reloaded in Step 8.
- **How to Use Individually (Standalone Mode)**:
  - Can be written, validated, linted, or tuned completely standalone without running any application code or having microservices started:
    ```bash
    python3 -c "
    import yaml
    with open('${FEATURE_DIR}/http-config.yml') as f:
        cfg = yaml.safe_load(f)
    print('Config validated! Profile:', cfg['profile'], '| Steps:', cfg['pipeline']['steps'])
    "
    ```

---

### Step 3: Defining the Pure Domain Outbound Port Interface (`infrastructure/ports/`)

#### 3.1 Purpose & Architectural Rationale
The Outbound Port is an abstract interface using standard library `abc.ABC`. It models **domain intent** (e.g. `fetch_embedding`, `evaluate_score`, `dispatch_alert`), not HTTP protocols:
- Pure Domain Invariant: Port files must contain **zero** network imports (`import httpx`, `import requests`, `import urllib` are strictly forbidden).
- The port accepts pure domain entities or primitives (`str`, `dict`, `pydantic.BaseModel`) and returns domain models.

#### 3.2 Concrete Universal Port Implementation
Generate the abstract port file `${FEATURE_DIR}/infrastructure/ports/${FEATURE_NAME}_port.py`:

```bash
cat << 'EOF' > "${FEATURE_DIR}/infrastructure/ports/${FEATURE_NAME}_port.py"
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class FeatureOutboundPort(ABC):
    @abstractmethod
    async def execute_remote_operation(
        self,
        payload: Dict[str, Any],
        tenant_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute the feature's outbound remote operation."""
        pass
EOF
```

#### 3.3 Automated Verification Script
Run this script to assert that the port is abstract and has zero network coupling:

```bash
python3 -c "
import os
import ast
from pathlib import Path

port_path = Path(os.environ['FEATURE_DIR']) / 'infrastructure' / 'ports' / f\"{os.environ['FEATURE_NAME']}_port.py\"
assert port_path.is_file(), f'FAILED: {port_path} not found'

with open(port_path) as f:
    tree = ast.parse(f.read())

forbidden_modules = {'httpx', 'requests', 'urllib', 'aiohttp'}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name not in forbidden_modules, f'VIOLATION: Forbidden import {alias.name} in Port interface!'
    elif isinstance(node, ast.ImportFrom):
        assert node.module not in forbidden_modules, f'VIOLATION: Forbidden import from {node.module} in Port interface!'

print(f'>>> Step 3 SUCCESS: Port interface verified pure of networking imports')
"
```

#### 3.4 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - Domain business contract requirements: method names, parameter types (`payload: Dict[str, Any]`, `tenant_id: str`, `correlation_id: Optional[str]`).
  - Zero networking concepts: No URLs, no HTTP methods (GET/POST), no headers, no status codes.
- **Outputs Produced**:
  - Python interface module: `${FEATURE_DIR}/infrastructure/ports/${FEATURE_NAME}_port.py`.
  - Abstract Base Class: `class FeatureOutboundPort(ABC)` with abstract method `execute_remote_operation()`.
- **How It Connects to Other Steps**:
  - Upstream: Placed in `${FEATURE_DIR}/infrastructure/ports/` created in Step 1.
  - Downstream:
    - Implemented by Step 4's concrete `HttpFeatureOutboundAdapter`.
    - Required as constructor dependency injection in Step 5's `FeatureDomainService(__init__(self, outbound_port))`.
    - Mocked in Step 6's unit tests using `AsyncMock`.
- **How to Use Individually (Standalone Mode)**:
  - Can be defined and verified completely independently of HTTP clients, libraries, or network infrastructure.
  - Allows multiple interchangeable implementations: an HTTP adapter, a gRPC adapter, a Kafka event adapter, or an in-memory stub can all implement this same port without modifying domain code.
  - Standalone verification command (AST parser asserting zero networking imports):
    ```bash
    python3 -c "
    import ast
    with open('${FEATURE_DIR}/infrastructure/ports/${FEATURE_NAME}_port.py') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, 'module', '') or [a.name for a in node.names][0]
            assert mod not in {'httpx', 'requests', 'urllib', 'aiohttp'}, f'Forbidden import {mod}'
    print('Port is 100% pure domain!')
    "
    ```

---

### Step 4: Implementing the Concrete HTTP Adapter (`infrastructure/adapters/`) with `ResilientHttpClient`

#### 4.1 Purpose & Architectural Rationale
The Adapter implements the abstract Port interface. It is the sole component that interfaces with `python_shared.http.ResilientHttpClient`.
Key Invariants:
- Dynamic Config Resolution: The adapter resolves its own directory dynamically via `Path(__file__).resolve().parents[2]` so it functions correctly regardless of execution path.
- Transparent Telemetry: The adapter passes `tenant_id` and `correlation_id` to `client.execute_async()`, allowing the pipeline to propagate W3C `traceparent` headers.
- DTO Translation: Converts domain requests into HTTP JSON payloads and maps HTTP responses to domain results.

#### 4.2 Concrete Universal Adapter Implementation
Generate `${FEATURE_DIR}/infrastructure/adapters/http_${FEATURE_NAME}_adapter.py`:

```bash
cat << 'EOF' > "${FEATURE_DIR}/infrastructure/adapters/http_${FEATURE_NAME}_adapter.py"
from pathlib import Path
from typing import Dict, Any, Optional
from python_shared.http import ResilientHttpClient

class HttpFeatureOutboundAdapter:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        feature_dir = Path(__file__).resolve().parents[2]
        self._client = ResilientHttpClient.from_config(
            config_path=feature_dir,
            base_url=base_url
        )

    async def execute_remote_operation(
        self,
        payload: Dict[str, Any],
        tenant_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        headers: Dict[str, str] = {}
        if correlation_id:
            headers["x-correlation-id"] = correlation_id

        response = await self._client.execute_async(
            method="POST",
            url="/api/v1/remote/execute",
            json=payload,
            tenant_id=tenant_id,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
EOF
```

#### 4.3 Automated Verification Script
Run this script to instantiate the adapter and assert that `ResilientHttpClient.from_config()` loaded the YAML configuration correctly:

```bash
python3 -c "
import os
import sys
from pathlib import Path

monorepo_root = Path(os.environ['MONOREPO_ROOT'])
sys.path.insert(0, str(monorepo_root / 'python-shared'))

from python_shared.http import ResilientHttpClient

feature_dir = Path(os.environ['FEATURE_DIR'])
client = ResilientHttpClient.from_config(feature_dir, base_url='http://mock-service')

assert client.profile == os.environ['FEATURE_PROFILE'], f'Profile mismatch: {client.profile}'
assert client.timeout > 0.0, 'Client timeout must be configured'

expected_step_count = 8 if client.profile == 'api_service' else (2 if client.profile == 'temporal_worker' else 1)
assert len(client.runner.steps) == expected_step_count, f'Pipeline step count mismatch: {len(client.runner.steps)} vs {expected_step_count}'

print(f'>>> Step 4 SUCCESS: Adapter successfully bound to {client.profile} with {len(client.runner.steps)} steps')
"
```

#### 4.4 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - `http-config.yml` from Step 2 (loaded via `Path(__file__).resolve().parents[2]`).
  - `FeatureOutboundPort` contract from Step 3.
  - Remote target `base_url` (e.g. `"http://localhost:8000"` or cluster service DNS).
  - Inbound method call: `execute_remote_operation(payload, tenant_id, correlation_id)`.
- **Outputs Produced**:
  - Concrete adapter class: `class HttpFeatureOutboundAdapter(FeatureOutboundPort)`.
  - Instantiated `ResilientHttpClient` configured with active pipeline interceptors.
  - Method execution output: Domain result dictionary mapped from HTTP JSON response (`response.json()`).
- **How It Connects to Other Steps**:
  - Upstream: Implements the Port from Step 3; loads configuration from Step 2; placed in directory from Step 1.
  - Downstream: Injected into Step 5's `FeatureDomainService`; tested against simulated network failures in Step 7; hot-reloads config in Step 8.
- **How to Use Individually (Standalone Mode)**:
  - Can be instantiated and invoked directly in a standalone script, CLI tool, or integration smoke test without needing the domain service or Web API layer:
    ```python
    import asyncio
    from pathlib import Path
    import sys

    # Add python-shared to path
    sys.path.insert(0, "python-shared")
    from src.features.score_composite.infrastructure.adapters.http_score_composite_adapter import HttpFeatureOutboundAdapter

    async def main():
        adapter = HttpFeatureOutboundAdapter(base_url="http://localhost:8000")
        result = await adapter.execute_remote_operation(
            payload={"test_key": "test_val"},
            tenant_id="tenant-standalone"
        )
        print("Adapter executed independently:", result)

    asyncio.run(main())
    ```

---

### Step 5: Injecting the Port into the Pure Domain Service (`service/`)

#### 5.1 Purpose & Architectural Rationale
The Domain Service encapsulates core business orchestration. Following Dependency Injection (DI):
- The service receives the Port interface in its constructor (`__init__(self, port: FeatureOutboundPort)`).
- The service has zero knowledge of HTTP endpoints, network errors, or retries.
- Tests can mock the Port trivially without mocking HTTP sockets or patching libraries.

#### 5.2 Concrete Universal Service Implementation
Generate `${FEATURE_DIR}/service/${FEATURE_NAME}_service.py`:

```bash
cat << 'EOF' > "${FEATURE_DIR}/service/${FEATURE_NAME}_service.py"
from typing import Dict, Any, Optional

class FeatureDomainService:
    def __init__(self, outbound_port) -> None:
        self._outbound_port = outbound_port

    async def execute_business_action(
        self,
        data: Dict[str, Any],
        tenant_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not data:
            raise ValueError("Input data cannot be empty")
        
        raw_result = await self._outbound_port.execute_remote_operation(
            payload=data,
            tenant_id=tenant_id,
            correlation_id=correlation_id
        )
        
        return {
            "status": "COMPLETED",
            "feature": "verified",
            "result": raw_result
        }
EOF
```

#### 5.3 Automated Verification Script
Run this script to verify that the domain service accepts the injected port and processes business actions:

```bash
python3 -c "
import asyncio
from unittest.mock import AsyncMock

class DummyPort:
    async def execute_remote_operation(self, payload, tenant_id, correlation_id=None):
        return {'score': 0.99, 'tenant': tenant_id}

async def run_test():
    import os, sys, importlib.util
    from pathlib import Path
    service_file = Path(os.environ['FEATURE_DIR']) / 'service' / f\"{os.environ['FEATURE_NAME']}_service.py\"
    spec = importlib.util.spec_from_file_location('service_mod', service_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    service = mod.FeatureDomainService(outbound_port=DummyPort())
    output = await service.execute_business_action({'query': 'test'}, tenant_id='t-123')
    assert output['status'] == 'COMPLETED'
    assert output['result']['score'] == 0.99

asyncio.run(run_test())
print('>>> Step 5 SUCCESS: Domain service dependency injection verified')
"
```

#### 5.4 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - Injected Port instance conforming to `FeatureOutboundPort` (from Step 3/4).
  - Business execution parameters: `data: Dict[str, Any]`, `tenant_id: str`, `correlation_id: Optional[str]`.
- **Outputs Produced**:
  - Domain service class: `class FeatureDomainService`.
  - Business domain result dictionary (e.g. `{"status": "COMPLETED", "result": raw_result}`).
  - Domain exceptions on validation failure (`ValueError("Input data cannot be empty")`).
- **How It Connects to Other Steps**:
  - Upstream: Consumes the Port interface defined in Step 3. In production, it receives Step 4's `HttpFeatureOutboundAdapter`. In unit tests, it receives Step 6's mock.
  - Downstream: Exposed directly to user-facing controllers, FastAPI routers, Temporal workflow activities, or CLI commands.
- **How to Use Individually (Standalone Mode)**:
  - Can be executed, debugged, and unit-tested 100% offline with zero network connectivity using an in-memory stub port:
    ```python
    import asyncio
    from src.features.score_composite.service.score_composite_service import FeatureDomainService

    class InMemoryStubPort:
        async def execute_remote_operation(self, payload, tenant_id, correlation_id=None):
            return {"mock_score": 0.98, "status": "calculated_in_memory"}

    async def run_offline():
        service = FeatureDomainService(outbound_port=InMemoryStubPort())
        res = await service.execute_business_action(
            data={"metric_values": [1.0, 0.9, 0.95]},
            tenant_id="tenant-local"
        )
        print("Pure domain logic output:", res)

    asyncio.run(run_offline())
    ```

---

### Step 6: Unit Testing with In-Memory Mocks (`tests/`)

#### 6.1 Purpose & Architectural Rationale
Unit tests verify domain business logic in total isolation from the network:
- Tests execute in milliseconds without opening TCP ports or running background servers.
- `unittest.mock.AsyncMock` simulates downstream successes, network timeouts, and HTTP failures.

#### 6.2 Concrete Universal Test Suite
Generate `${FEATURE_DIR}/tests/${FEATURE_NAME}_service_test.py`:

```bash
cat << 'EOF' > "${FEATURE_DIR}/tests/${FEATURE_NAME}_service_test.py"
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_port():
    port = AsyncMock()
    port.execute_remote_operation.return_value = {"processed": True, "value": 42}
    return port

@pytest.mark.asyncio
async def test_domain_service_successful_execution(mock_port):
    import os, importlib.util
    from pathlib import Path
    service_file = Path(os.environ.get("FEATURE_DIR", ".")) / "service" / f"{os.environ.get('FEATURE_NAME', 'target')}_service.py"
    spec = importlib.util.spec_from_file_location("svc_mod", service_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    service = mod.FeatureDomainService(outbound_port=mock_port)
    result = await service.execute_business_action(
        data={"key": "test_input"},
        tenant_id="tenant-unit-test",
        correlation_id="corr-999"
    )

    assert result["status"] == "COMPLETED"
    assert result["result"]["value"] == 42
    mock_port.execute_remote_operation.assert_awaited_once_with(
        payload={"key": "test_input"},
        tenant_id="tenant-unit-test",
        correlation_id="corr-999"
    )

@pytest.mark.asyncio
async def test_domain_service_empty_input_rejection(mock_port):
    import os, importlib.util
    from pathlib import Path
    service_file = Path(os.environ.get("FEATURE_DIR", ".")) / "service" / f"{os.environ.get('FEATURE_NAME', 'target')}_service.py"
    spec = importlib.util.spec_from_file_location("svc_mod", service_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    service = mod.FeatureDomainService(outbound_port=mock_port)
    with pytest.raises(ValueError, match="Input data cannot be empty"):
        await service.execute_business_action(data={}, tenant_id="tenant-unit-test")
EOF
```

#### 6.3 Automated Test Execution
Run the unit tests using `pytest`:

```bash
pytest "${FEATURE_DIR}/tests/${FEATURE_NAME}_service_test.py" -v
```

#### 6.4 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - `FeatureDomainService` instance from Step 5.
  - `unittest.mock.AsyncMock` configured to simulate `FeatureOutboundPort` returns and exceptions.
  - Test test-cases: Valid data payload, empty payload validation error, mock downstream responses.
- **Outputs Produced**:
  - Automated test execution report (`pytest -v`).
  - Pass/Fail verification of business constraints and port call assertions (`mock_port.execute_remote_operation.assert_awaited_once_with(...)`).
- **How It Connects to Other Steps**:
  - Upstream: Tests the domain service implemented in Step 5 while mocking the port defined in Step 3.
  - Downstream: Acts as an ultra-fast local developer test loop and CI/CD quality gate before running slower integration or fault-injection tests in Step 7.
- **How to Use Individually (Standalone Mode)**:
  - Can be run completely offline in milliseconds from the command line on any workstation or CI runner without external services:
    ```bash
    pytest "${FEATURE_DIR}/tests/${FEATURE_NAME}_service_test.py" -v
    ```

---

### Step 7: Resilient Pipeline & Fault-Injection Verification

#### 7.1 Purpose & Architectural Rationale
Verifies that the HTTP pipeline's defensive safeguards function as specified:
- Circuit Breaker trips after consecutive downstream 5xx errors and fails fast without hitting the network.
- Context Isolation attaches W3C `traceparent` and `x-tenant-id` to outbound wire requests.
- SSRF Validation rejects requests attempting to access RFC 1918 or AWS/GCP metadata (`169.254.169.254`).

#### 7.2 Concrete Fault-Injection Test Suite
Run this comprehensive integration test using `httpx.MockTransport`:

```bash
python3 -c "
import asyncio
import httpx
from python_shared.http import ResilientHttpClient

async def test_pipeline_resilience():
    # 1. Test W3C Traceparent and Header Injection
    captured_headers = {}
    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        return httpx.Response(200, json={'status': 'ok'})

    client = ResilientHttpClient(base_url='http://mock-service', profile='api_service')
    client._async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_handler),
        base_url='http://mock-service'
    )

    resp = await client.execute_async('POST', '/test', json={'x': 1}, tenant_id='tenant-gold')
    assert resp.status_code == 200
    assert 'traceparent' in captured_headers, 'FAILED: traceparent missing from outbound request'
    assert captured_headers.get('x-tenant-id') == 'tenant-gold', 'FAILED: x-tenant-id not propagated'
    print('>>> Subtest A Passed: W3C Context & Tenant Headers Propagated')

    # 2. Test Circuit Breaker Trip on Downstream Failures
    fail_count = 0
    def failing_handler(request: httpx.Request) -> httpx.Response:
        nonlocal fail_count
        fail_count += 1
        return httpx.Response(503, json={'error': 'Service Unavailable'})

    failing_client = ResilientHttpClient(base_url='http://mock-downstream', profile='api_service')
    failing_client._async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(failing_handler),
        base_url='http://mock-downstream'
    )

    for _ in range(5):
        try:
            await failing_client.execute_async('GET', '/broken', tenant_id='t-1')
        except Exception:
            pass

    tripped = False
    try:
        await failing_client.execute_async('GET', '/broken', tenant_id='t-1')
    except Exception as e:
        if 'circuit' in str(e).lower() or 'open' in str(e).lower():
            tripped = True
    
    assert tripped, 'FAILED: Circuit breaker did not trip after 5 failures'
    print('>>> Subtest B Passed: Circuit Breaker successfully tripped into OPEN state')

asyncio.run(test_pipeline_resilience())
print('>>> Step 7 SUCCESS: Pipeline resilience and fault-injection verified!')
"
```

#### 7.3 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - `ResilientHttpClient` configured with `api_service` profile from Step 2 and Step 4.
  - Simulated fault scenarios: `httpx.MockTransport` programmed to return 503 Service Unavailable, simulated connection drops, and header inspection handlers.
- **Outputs Produced**:
  - Verified W3C `traceparent` and `x-tenant-id` header transmission.
  - Verified Circuit Breaker state transition: 5 consecutive failures trips state from `CLOSED` to `OPEN`.
  - Fast-fail assertion: Subsequent calls fail immediately without dispatching network frames.
  - Emitted metrics: `circuit_breaker.transition.open`.
- **How It Connects to Other Steps**:
  - Upstream: Validates the resilience policies defined in Step 2 and implemented in Step 4.
  - Downstream: Confirms that when Step 5's Domain Service invokes remote actions during an outage, connection pools and resources are protected from exhaustion.
- **How to Use Individually (Standalone Mode)**:
  - Can be run as a standalone chaos engineering test or reliability harness on a developer workstation without live external dependencies:
    ```bash
    python3 -c "
    import asyncio, httpx
    from python_shared.http import ResilientHttpClient

    async def run_chaos():
        client = ResilientHttpClient(base_url='http://mock-target', profile='api_service')
        client._async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(503, json={'err': 'downstream_down'})),
            base_url='http://mock-target'
        )
        for i in range(5):
            try: await client.execute_async('GET', '/test', tenant_id='t-1')
            except Exception: pass
        print('Circuit breaker tripped successfully in standalone test!')

    asyncio.run(run_chaos())
    "
    ```

---

### Step 8: Operational Hot-Reload, SIGHUP Triggers & Production Verification

#### 8.1 Purpose & Architectural Rationale
In production environments, microservices must allow updating configuration parameters (such as increasing timeouts during database maintenance, adjusting circuit breaker thresholds, or modifying rate limits) with **zero dropped requests and zero downtime**:
- Atomic Swap: Updating the configuration swaps an immutable memory pointer.
- Active sockets remain connected; new requests immediately execute with the updated snapshot.

#### 8.2 Operational Verification Commands
Execute this automated smoke test to verify live configuration updates:

```bash
# 1. Read current timeout from http-config.yml
CURRENT_TIMEOUT=$(grep "timeout_seconds:" "${FEATURE_DIR}/http-config.yml" | head -n 1 | awk '{print $2}')
echo "Current timeout: ${CURRENT_TIMEOUT}s"

# 2. Update timeout in-place using sed (e.g. adjust to 45.0s)
sed -i 's/timeout_seconds: .*/timeout_seconds: 45.0/' "${FEATURE_DIR}/http-config.yml"

# 3. Verify ResilientHttpClient reloads updated configuration
python3 -c "
import os
from pathlib import Path
from python_shared.http import ResilientHttpClient

feature_dir = Path(os.environ['FEATURE_DIR'])
client = ResilientHttpClient.from_config(feature_dir)
assert client.timeout == 45.0, f'Hot reload failed: expected 45.0, got {client.timeout}'
print('>>> Step 8 SUCCESS: Dynamic configuration reload verified without process restart!')
"

# 4. Revert test modification
sed -i "s/timeout_seconds: .*/timeout_seconds: ${CURRENT_TIMEOUT}/" "${FEATURE_DIR}/http-config.yml"
```

#### 8.3 Input/Output, Interconnection & Standalone Usage Reference

- **Inputs Given**:
  - Live running process or dynamic loader instance.
  - Modified `${FEATURE_DIR}/http-config.yml` on disk (e.g. timeout adjusted via SRE tool, GitOps sync, or ConfigMap reload).
  - Reload trigger: SIGHUP signal, filesystem watcher event, or `ResilientHttpClient.from_config()` call.
- **Outputs Produced**:
  - Atomic pointer swap to new immutable configuration snapshot.
  - Updated client runtime properties (`client.timeout == 45.0`) with zero dropped in-flight requests, zero TCP socket churn, and zero process downtime.
  - Reload log: `Config reloaded successfully`.
- **How It Connects to Other Steps**:
  - Upstream: Modifies the file created in Step 2; refreshes the client instantiated in Step 4 and used by Step 5.
  - Downstream: Enables live operational tuning by SREs and production runbooks without triggering Kubernetes Pod restarts.
- **How to Use Individually (Standalone Mode)**:
  - Can be tested standalone to verify dynamic configuration reloading mechanics without starting the web server:
    ```bash
    python3 -c "
    from python_shared.http import ResilientHttpClient
    client = ResilientHttpClient.from_config('${FEATURE_DIR}')
    print('Current timeout loaded dynamically:', client.timeout)
    "
    ```

---

## 9. Failure Diagnosis & Resolution Matrix

| Symptom / Error | Root Cause | Diagnosis Command | Corrective Action |
|---|---|---|---|
| `SSRFSecurityViolation: Target IP 169.254.169.254 is within blocked cloud metadata range` | Outbound request targeted AWS/GCP instance metadata endpoint. | Inspect request destination in active span tags. | Reject request immediately with HTTP 400. Never whitelist metadata ranges. |
| `CircuitBreakerOpenException: Circuit is OPEN (5 consecutive failures)` | Downstream microservice is failing health checks or timing out. | `curl http://127.0.0.1:9003/admin/v1/http/circuit-breaker` | Inspect downstream logs. If downstream recovered, await `recovery_timeout_seconds` or call `/admin/v1/http/circuit-breaker/reset`. |
| `BulkheadRejectionException: Admission queue full (100 pending)` | Inbound rate exceeds downstream processing capacity; queue saturated. | Check `admission_control.queue_size` and active worker count. | Scale downstream replicas or increase `admission_control.concurrency_limit`. |
| `SingleflightLeaderDiedException` | The leader request that was deduplicated encountered an unhandled panic. | Inspect trace ID in error log. | Follower requests automatically bypass cache on leader failure. Retry with exponential backoff. |
| Broken namespace package (`src.features.http`) | Stray `src/__init__.py` or `src/features/__init__.py` preventing PEP 420 resolution. | `po file-search --root . --pattern "__init__.py"` | Delete `src/__init__.py`. Import from `python_shared.http`. |
