"""
Blueprint:
- Pure domain orchestrator service for YAML contract validation.
- Adheres to Single Responsibility Principle: handles YAML contract validation orchestration only.
- Coordinates YamlValidationWorkflow and resolves candidate file paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.features.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationTargetType,
)
from src.features.validation.domain.workflows.yaml_validation_workflow import YamlValidationWorkflow
from src.features.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class YamlValidationService:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository
        self._workflow = YamlValidationWorkflow(repository=repository)

    async def validate_yaml_content(
        self,
        yaml_content: str,
        contract_name: str = "contract.yaml",
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        req = ContractValidationRequestDTO(
            contract_name=contract_name,
            content=yaml_content,
            target_type=ValidationTargetType.CONTRACT,
            required_patterns=required_patterns,
            schema_definition={"required_fields": list(required_fields)} if required_fields else {},
        )
        return await self._workflow.execute_yaml_validation(req, trace_id=trace_id)

    async def resolve_and_validate_file(
        self,
        candidate_paths: Sequence[str | Path],
        required_patterns: Sequence[str] = (),
        required_fields: Sequence[str] = (),
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
                target_type=ValidationTargetType.CONTRACT,
                required_patterns=required_patterns,
                schema_definition={"required_fields": list(required_fields)} if required_fields else {},
            )
            return await self._workflow.execute_yaml_validation(failed_req, trace_id=trace_id)

        try:
            content = resolved_path.read_text(encoding="utf-8")
        except Exception:
            content = ""

        return await self.validate_yaml_content(
            yaml_content=content,
            contract_name=resolved_path.name,
            required_fields=required_fields,
            required_patterns=required_patterns,
            trace_id=trace_id,
        )
