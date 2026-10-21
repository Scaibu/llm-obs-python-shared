import os
import yaml
from typing import Any, Dict, List, Optional
from src.features.http.pipeline.types import PipelineContext, RequestConfig
from src.features.http.pipeline.security.input_hardening import StepInputHardening
from src.features.http.pipeline.ssrf_validation import StepSsrfValidation
from src.features.http.pipeline.context_isolation import StepContextIsolation
from src.features.http.pipeline.cache_eval import StepCacheEval
from src.features.http.pipeline.singleflight import StepSingleflight
from src.features.http.pipeline.circuit_breaker import StepCircuitBreaker
from src.features.http.pipeline.rate_limit import StepRateLimit
from src.features.http.pipeline.admission_control import StepAdmissionControl

STEP_REGISTRY: Dict[str, Any] = {
    "input_hardening": StepInputHardening,
    "ssrf_validation": StepSsrfValidation,
    "context_isolation": StepContextIsolation,
    "cache_eval": StepCacheEval,
    "singleflight": StepSingleflight,
    "circuit_breaker": StepCircuitBreaker,
    "rate_limit": StepRateLimit,
    "admission_control": StepAdmissionControl,
}

class HttpPipelineRunner:
    def __init__(
        self,
        steps: Optional[List[Any]] = None,
        config_path: Optional[str] = None,
        profile: str = "default",
    ) -> None:
        self.config_path: str = config_path or os.path.join(os.path.dirname(__file__), "config.yml")
        self.config: Dict[str, Any] = self._load_config()
        self.profile: str = profile
        if steps is not None:
            self.steps: List[Any] = self._resolve_steps(steps)
        else:
            self.steps = self._build_steps_for_profile(self.profile)

    def _resolve_steps(self, steps_input: List[Any]) -> List[Any]:
        resolved: List[Any] = []
        for item in steps_input:
            if isinstance(item, str):
                step_cls = STEP_REGISTRY.get(item)
                if step_cls is not None:
                    resolved.append(step_cls())
            elif isinstance(item, dict) and "name" in item:
                step_cls = STEP_REGISTRY.get(item["name"])
                if step_cls is not None:
                    resolved.append(step_cls())
            else:
                resolved.append(item)
        return resolved

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        return {}

    def _build_steps_for_profile(self, profile: str) -> List[Any]:
        profiles = self.config.get("profiles", {})
        resolved_name = profile
        if resolved_name == "default":
            resolved_name = profiles.get("default", "api_service")
        
        profile_def = profiles.get(resolved_name)
        if isinstance(profile_def, dict) and "steps" in profile_def:
            step_names = profile_def["steps"]
            return self._resolve_steps(step_names)

        return self._build_default_steps()

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
        from python_shared.telemetry.tracer import trace_pipeline_stage
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

_cached_runners: Dict[str, HttpPipelineRunner] = {}

def get_pipeline_runner(
    profile: str = "default",
    config_path: Optional[str] = None,
) -> HttpPipelineRunner:
    cache_key = f"{profile}:{config_path or ''}"
    if cache_key not in _cached_runners:
        _cached_runners[cache_key] = HttpPipelineRunner(profile=profile, config_path=config_path)
    return _cached_runners[cache_key]

pipeline_runner = get_pipeline_runner("default")

__all__ = [
    "HttpPipelineRunner",
    "get_pipeline_runner",
    "pipeline_runner",
    "STEP_REGISTRY",
]


