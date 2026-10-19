"""
Blueprint:
- Multi-step TOML and pyproject.toml validation automation DAG workflow.
- Coordinates TOML syntax parsing, regex extraction, pyproject metadata & dependency rules.
- Awaits outbound repository port for persisting validation audits.
"""

from __future__ import annotations

import uuid

from python_shared.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationStatus,
    ValidationErrorDetail,
    ValidationTargetType,
)
from python_shared.validation.domain.rules.toml_rules import TomlValidationRules
from python_shared.validation.domain.rules.common_rules import SchemaValidationRules
from python_shared.validation.domain.machines.validation_machine import ValidationStateMachine
from python_shared.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class TomlValidationWorkflow:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    async def execute_toml_validation(
        self, request: ContractValidationRequestDTO, trace_id: str = ""
    ) -> ValidationReportModel:
        validation_id = str(uuid.uuid4())
        current_status = ValidationStatus.PENDING

        current_status = ValidationStateMachine.transition(current_status, ValidationStatus.IN_PROGRESS)

        errors: list[ValidationErrorDetail] = []
        extracted_metadata: dict[str, str] = {}

        is_valid_doc, parsed_doc, syntax_err = TomlValidationRules.validate_toml_syntax(request.content)
        if syntax_err:
            errors.append(syntax_err)

        if request.required_patterns:
            extracted, pattern_errors = SchemaValidationRules.extract_regex_patterns(
                request.content, request.required_patterns
            )
            extracted_metadata.update(extracted)
            errors.extend(pattern_errors)

        if is_valid_doc and parsed_doc:
            # If pyproject validation is requested or filename matches
            is_pyproject = (
                "pyproject" in request.contract_name.lower()
                or request.schema_definition.get("is_pyproject", False)
            )
            if is_pyproject:
                require_pinned = request.schema_definition.get("require_pinned_versions", False)
                pyproject_errors = TomlValidationRules.validate_pyproject_structure(
                    parsed_doc, require_pinned_versions=require_pinned
                )
                errors.extend(pyproject_errors)

            required_fields = request.schema_definition.get("required_fields", [])
            if required_fields:
                schema_errors = SchemaValidationRules.validate_schema_fields(parsed_doc, required_fields)
                errors.extend(schema_errors)

        has_blocking_errors = any(e.severity.value == "ERROR" for e in errors)
        target_status = ValidationStatus.VALID if not has_blocking_errors else ValidationStatus.INVALID
        final_status = ValidationStateMachine.transition(current_status, target_status)

        report = ValidationReportModel(
            validation_id=validation_id,
            target_name=request.contract_name,
            target_type=request.target_type or ValidationTargetType.TOML,
            status=final_status,
            errors=tuple(errors),
            extracted_metadata=extracted_metadata,
            is_valid=(final_status == ValidationStatus.VALID),
        )

        await self._repository.save_report(report, trace_id=trace_id)
        return report
