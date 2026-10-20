"""
Blueprint:
- Composable HTTP pipeline runner coordinating modular pipeline step features.
- Implements strict Part B execution order:
  1. SSRF Validation (user URLs only)
  2. Context Binding (strips untrusted headers, binds authenticated tenant & principal)
  3. Cache Evaluation (lookup hit short-circuits execution before consuming tokens/slots)
  4. Singleflight (deduplication of in-flight misses across concurrent requests)
  5. Circuit Breaker (open state fast-fails before rate-limiting or bulkheads)
  6. Rate Limit (per-tenant / per-upstream token bucket)
  7. Bulkhead / Admission Control (isolated concurrency slot acquisition)
"""
import os
import yaml
from typing import Any, Dict, List, Optional
from src.features.http.pipeline.types import PipelineContext, RequestConfig
from src.features.http.pipeline.ssrf_validation import StepSsrfValidation
from src.features.http.pipeline.context_isolation import StepContextIsolation
from src.features.http.pipeline.cache_eval import StepCacheEval
from src.features.http.pipeline.singleflight import StepSingleflight
from src.features.http.pipeline.circuit_breaker import StepCircuitBreaker
from src.features.http.pipeline.rate_limit import StepRateLimit
from src.features.http.pipeline.admission_control import StepAdmissionControl

class StepInputHardening:
    name: str = "InputHardening"
    description: str = "Enforces RFC 7493 I-JSON rules, max nesting depth, and rejects CRLF header injection"

    async def execute(self, ctx: Any) -> None:
        from src.features.http.pipeline.security.input_hardening import InputHardeningRules
        ctx.step_index += 1
        # 1. Enforce CRLF rejection in outbound headers
        if ctx.config.headers:
            InputHardeningRules.reject_crlf_in_headers(ctx.config.headers)
        # 2. If body is a JSON string, validate strict I-JSON rules
        if isinstance(ctx.config.body, str) and (ctx.config.body.strip().startswith("{") or ctx.config.body.strip().startswith("[")):
            InputHardeningRules.parse_strict_ijson(ctx.config.body)

class HttpPipelineRunner:
    def __init__(
        self,
        steps: Optional[List[Any]] = None,
        config_path: Optional[str] = None,
    ):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.yml")
        self.config: Dict[str, Any] = self._load_config()
        self.steps = steps or self._build_default_steps()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        return {}

    def _build_default_steps(self) -> List[Any]:
        # Strict Execution order:
        # InputHardening -> SSRF -> Context -> Cache -> Singleflight -> CircuitBreaker -> RateLimit -> Bulkhead
        return [
            StepInputHardening(),
            StepSsrfValidation(),
            StepContextIsolation(),
            StepCacheEval(),
            StepSingleflight(),
            StepCircuitBreaker(),
            StepRateLimit(),
            StepAdmissionControl(),
        ]

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        admitted = False
        from src.python_shared.telemetry.tracer import trace_pipeline_stage
        try:
            for step in self.steps:
                step_name = getattr(step, "name", step.__class__.__name__)
                with trace_pipeline_stage(
                    f"http.pipeline.{step_name}",
                    attributes={
                        "http.method": ctx.config.method,
                        "http.url": ctx.config.url,
                        "tenant.id": ctx.tenant_id or "anonymous",
                        "pipeline.step": step_name,
                    },
                    tracer_name="http.outbound.pipeline",
                ):
                    await step.execute(ctx)
                if isinstance(step, StepAdmissionControl):
                    admitted = True
                if ctx.cached_response is not None:
                    # Cache hit: immediate short-circuit without consuming rate limits or slots
                    break
            return ctx
        finally:
            if admitted:
                ctx.admission_control.release()

pipeline_runner = HttpPipelineRunner()

__all__ = [
    "HttpPipelineRunner",
    "pipeline_runner",
]
