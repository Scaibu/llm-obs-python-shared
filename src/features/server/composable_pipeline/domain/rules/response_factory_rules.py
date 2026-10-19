"""
Blueprint:
- ResponseFactoryRules: Centralized rule engine creating standardized IngressResponse envelopes.
- Eliminates repeated boilerplate across pipeline stages, ensuring DRY, consistent headers, status codes, and RFC 9457 Problem Details envelopes.
"""
import json
from typing import Any, Dict, Optional
from src.features.server.composable_pipeline.contracts.pipeline_constants import PipelineHeaders
from src.features.server.composable_pipeline.contracts.pipeline_types import (
    IngressResponse,
    PipelineRequestContext,
)
from src.features.server.composable_pipeline.domain.rules.rfc9457_rules import ProblemDetailsRules


class ResponseFactoryRules:
    @staticmethod
    def _compute_bytes(payload: Any) -> int:
        if payload is None:
            return 0
        if isinstance(payload, bytes):
            return len(payload)
        if isinstance(payload, str):
            return len(payload.encode("utf-8"))
        try:
            return len(
                json.dumps(
                    payload,
                    default=lambda o: o.decode("utf-8", errors="replace") if isinstance(o, bytes) else str(o),
                ).encode("utf-8")
            )
        except Exception:
            return len(str(payload).encode("utf-8"))

    @staticmethod
    def create_rejection(
        ctx: PipelineRequestContext,
        status_code: int,
        reason: str,
        detail: str,
        problem_base_url: str,
        retry_after_seconds: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> IngressResponse:
        ctx.status_code = status_code
        ctx.is_failed = True
        ctx.rejection_reason = reason

        headers: Dict[str, str] = {PipelineHeaders.REQUEST_ID: ctx.request_id}
        if retry_after_seconds is not None:
            headers[PipelineHeaders.RETRY_AFTER] = str(retry_after_seconds)
        if extra_headers:
            headers.update(extra_headers)

        problem = ProblemDetailsRules.create_problem(
            status=status_code,
            detail=detail,
            instance=ctx.request_id,
            reason=reason,
            base_url=problem_base_url,
            retry_after_seconds=retry_after_seconds,
        )
        ctx.bytes_out = len(problem.model_dump_json().encode("utf-8"))

        return IngressResponse(
            status_code=status_code,
            headers=headers,
            problem_details=problem,
            context=ctx,
        )

    @staticmethod
    def create_success(
        ctx: PipelineRequestContext,
        status_code: int,
        response_body: Any,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> IngressResponse:
        ctx.status_code = status_code
        ctx.bytes_out = ResponseFactoryRules._compute_bytes(response_body)
        headers: Dict[str, str] = {
            PipelineHeaders.REQUEST_ID: ctx.request_id,
            PipelineHeaders.TRACEPARENT: ctx.trace_id,
        }
        if extra_headers:
            headers.update(extra_headers)

        return IngressResponse(
            status_code=status_code,
            headers=headers,
            body=response_body,
            context=ctx,
        )
