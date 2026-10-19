"""
Blueprint:
- Pure domain orchestrator service for JSON contract and document validation.
- Adheres to Single Responsibility Principle: handles JSON schema validation orchestration only.
- Coordinates JsonValidationWorkflow and resolves JSON file paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.features.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationTargetType,
)
from src.features.validation.domain.workflows.json_validation_workflow import JsonValidationWorkflow
from src.features.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class JsonValidationService:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository
        self._workflow = JsonValidationWorkflow(repository=repository)

    async def validate_json_content(
        self,
        json_content: str,
        name: str = "payload.json",
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        req = ContractValidationRequestDTO(
            contract_name=name,
            content=json_content,
            target_type=ValidationTargetType.JSON,
            required_patterns=required_patterns,
            schema_definition={"required_fields": list(required_fields)} if required_fields else {},
        )
        return await self._workflow.execute_json_validation(req, trace_id=trace_id)

    async def resolve_and_validate_file(
        self,
        candidate_paths: Sequence[str | Path],
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        resolved_path: Path | None = next(
            (candidate for p in candidate_paths if (candidate := Path(p).resolve()).is_file()),
            None,
        )

        if resolved_path is None:
            failed_req = ContractValidationRequestDTO(
                contract_name="unknown_file",
                content="",
                target_type=ValidationTargetType.JSON,
                required_patterns=required_patterns,
                schema_definition={"required_fields": list(required_fields)} if required_fields else {},
            )
            return await self._workflow.execute_json_validation(failed_req, trace_id=trace_id)

        try:
            content = resolved_path.read_text(encoding="utf-8")
        except Exception:
            content = ""

        return await self.validate_json_content(
            json_content=content,
            name=resolved_path.name,
            required_fields=required_fields,
            required_patterns=required_patterns,
            trace_id=trace_id,
        )
