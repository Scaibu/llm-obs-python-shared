"""
Blueprint:
- Ingress delivery handler for validation.
- Parses request, manages local try/catch boundary, wraps in RFC envelope.
"""

from __future__ import annotations

from typing import Any, Mapping
from fastapi import Request
from fastapi.responses import JSONResponse

from src.features.validation.contracts.validation_schema import (
    ValidationSchemaMapper,
    ValidationEnvelopeResponse,
)
from src.features.validation.service.validation_service import ValidationService


class ValidationHandler:
    def __init__(self, service: ValidationService) -> None:
        self._service = service

    async def handle_validate_contract(self, request: Request, payload: Mapping[str, Any]) -> JSONResponse:
        trace_id = getattr(request.state, "correlation_id", "trace-default")
        try:
            dto = ValidationSchemaMapper.from_api(payload)
            report = await self._service.validate_contract(dto, trace_id=trace_id)
            envelope = ValidationSchemaMapper.to_api(report, trace_id=trace_id)
            status_code = 200 if report.is_valid else 422
            return JSONResponse(status_code=status_code, content=envelope)
        except Exception as exc:
            err_envelope = ValidationEnvelopeResponse(
                success=False,
                data=None,
                error={"code": "VALIDATION_ERROR", "message": str(exc)},
                meta={"traceId": trace_id},
            ).model_dump()
            return JSONResponse(status_code=400, content=err_envelope)
