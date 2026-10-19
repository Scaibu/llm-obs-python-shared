"""
Blueprint:
- Multi-step validation automation DAG workflow.
- Coordinates syntax parsing, regex extraction, schema rules, and state machine transitions.
- Awaits outbound repository port for persisting validation audits.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from python_shared.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationStatus,
    ValidationErrorDetail,
)
from python_shared.validation.domain.rules.validation_rules import ValidationRules
from python_shared.validation.domain.machines.validation_machine import ValidationStateMachine
from python_shared.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class ValidationWorkflow:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    async def execute_contract_validation(
        self, request: ContractValidationRequestDTO, trace_id: str = ""
    ) -> ValidationReportModel:
        validation_id = str(uuid.uuid4())
        current_status = ValidationStatus.PENDING

        current_status = ValidationStateMachine.transition(current_status, ValidationStatus.IN_PROGRESS)

        errors: list[ValidationErrorDetail] = []
        extracted_metadata: dict[str, str] = {}

        if request.target_type == ValidationTargetType.JSON:
            is_valid_doc, parsed_doc, syntax_err = ValidationRules.validate_json_syntax(request.content)
        else:
            is_valid_doc, parsed_doc, syntax_err = ValidationRules.validate_yaml_syntax(request.content)

        if syntax_err:
            errors.append(syntax_err)

        if request.required_patterns:
            extracted, pattern_errors = ValidationRules.extract_regex_patterns(
                request.content, request.required_patterns
            )
            extracted_metadata.update(extracted)
            errors.extend(pattern_errors)

        if is_valid_doc and parsed_doc and request.schema_definition:
            required_fields = request.schema_definition.get("required_fields", [])
            if required_fields:
                schema_errors = ValidationRules.validate_schema_fields(parsed_doc, required_fields)
                errors.extend(schema_errors)

        target_status = ValidationStatus.VALID if not errors else ValidationStatus.INVALID
        final_status = ValidationStateMachine.transition(current_status, target_status)

        report = ValidationReportModel(
            validation_id=validation_id,
            target_name=request.contract_name,
            target_type=request.target_type,
            status=final_status,
            errors=tuple(errors),
            extracted_metadata=extracted_metadata,
            is_valid=(final_status == ValidationStatus.VALID),
        )

        await self._repository.save_report(report, trace_id=trace_id)
        return report
