"""
Blueprint:
- Public facade for input_hardening feature.
"""
from typing import Any
from src.features.http.pipeline.security.input_hardening.domain.rules.input_hardening_rules import (
    InputHardeningConstants,
    InputHardeningRules,
)

class StepInputHardening:
    name: str = "InputHardening"
    description: str = "Enforces RFC 7493 I-JSON rules, max nesting depth, and rejects CRLF header injection"

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        if ctx.config.headers:
            InputHardeningRules.reject_crlf_in_headers(ctx.config.headers)
        if isinstance(ctx.config.body, str) and (ctx.config.body.strip().startswith("{") or ctx.config.body.strip().startswith("[")):
            InputHardeningRules.parse_strict_ijson(ctx.config.body)

__all__ = [
    "InputHardeningConstants",
    "InputHardeningRules",
    "StepInputHardening",
]

