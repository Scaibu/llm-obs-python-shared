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
        if ctx.config.headers:
            InputHardeningRules.reject_crlf_in_headers(ctx.config.headers)
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

