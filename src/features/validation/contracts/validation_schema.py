"""
Blueprint:
- Schema Anti-Corruption Layer (ACL) for validation ingress/egress.
- Provides bidirectional conversion: fromApi and toApi.
- Wraps output into standardized RFC envelope structure.
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from pydantic import BaseModel, Field

from src.features.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationStatus,
    ValidationTargetType,
    ValidationErrorDetail,
    ValidationSeverity,
)


class ContractValidationApiRequest(BaseModel):
    contract_name: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    target_type: str = Field(default="CONTRACT")
    required_patterns: list[str] = Field(default_factory=list)
    schema_definition: dict[str, Any] = Field(default_factory=dict)


class ValidationErrorDetailResponse(BaseModel):
    code: str
    message: str
    path: str
    severity: str
    context: dict[str, Any] = Field(default_factory=dict)


class ValidationReportApiResponse(BaseModel):
    validation_id: str
    target_name: str
    target_type: str
    status: str
    is_valid: bool
    errors: list[ValidationErrorDetailResponse]
    extracted_metadata: dict[str, Any]


class ValidationEnvelopeResponse(BaseModel):
    success: bool
    data: ValidationReportApiResponse | None = None
    error: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ValidationSchemaMapper:
    @staticmethod
    def from_api(payload: Mapping[str, Any]) -> ContractValidationRequestDTO:
        req = ContractValidationApiRequest(**payload)
        try:
            target_type = ValidationTargetType(req.target_type.upper())
        except ValueError:
            target_type = ValidationTargetType.CONTRACT

        return ContractValidationRequestDTO(
            contract_name=req.contract_name.strip(),
            content=req.content,
            target_type=target_type,
            required_patterns=req.required_patterns,
            schema_definition=req.schema_definition,
        )

    @staticmethod
    def to_api(model: ValidationReportModel, trace_id: str = "") -> dict[str, Any]:
        errors_resp = [
            ValidationErrorDetailResponse(
                code=e.code,
                message=e.message,
                path=e.path,
                severity=e.severity.value,
                context=dict(e.context),
            )
            for e in model.errors
        ]

        report_resp = ValidationReportApiResponse(
            validation_id=model.validation_id,
            target_name=model.target_name,
            target_type=model.target_type.value,
            status=model.status.value,
            is_valid=model.is_valid,
            errors=errors_resp,
            extracted_metadata=dict(model.extracted_metadata),
        )

        envelope = ValidationEnvelopeResponse(
            success=model.is_valid,
            data=report_resp,
            error=None if model.is_valid else {"message": "Validation failed", "count": len(model.errors)},
            meta={"traceId": trace_id},
        )
        return envelope.model_dump()
