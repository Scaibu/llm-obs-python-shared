"""
Blueprint:
- Pure domain orchestrator service for TOML contract and pyproject.toml validation.
- Validates syntax, dependencies, tool configurations, and version pinning constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from python_shared.validation.contracts.validation_types import (
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationTargetType,
)
from python_shared.validation.domain.workflows.toml_validation_workflow import (
    TomlValidationWorkflow,
)
from python_shared.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class TomlValidationService:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._workflow = TomlValidationWorkflow(repository=repository)

    async def validate_toml_content(
        self,
        toml_content: str,
        name: str = "pyproject.toml",
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        require_pinned_versions: bool = False,
        is_pyproject: bool = True,
        trace_id: str = "",
    ) -> ValidationReportModel:
        schema_def: dict[str, object] = {
            "is_pyproject": is_pyproject,
            "require_pinned_versions": require_pinned_versions,
        }
        if required_fields:
            schema_def["required_fields"] = list(required_fields)

        req = ContractValidationRequestDTO(
            contract_name=name,
            content=toml_content,
            target_type=ValidationTargetType.TOML,
            required_patterns=required_patterns,
            schema_definition=schema_def,
        )
        return await self._workflow.execute_toml_validation(req, trace_id=trace_id)

    async def resolve_and_validate_file(
        self,
        candidate_paths: Sequence[str | Path],
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        require_pinned_versions: bool = False,
        is_pyproject: bool = True,
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
                target_type=ValidationTargetType.TOML,
                required_patterns=required_patterns,
                schema_definition={
                    "required_fields": list(required_fields) if required_fields else {},
                    "is_pyproject": is_pyproject,
                    "require_pinned_versions": require_pinned_versions,
                },
            )
            return await self._workflow.execute_toml_validation(failed_req, trace_id=trace_id)

        try:
            content = resolved_path.read_text(encoding="utf-8")
        except Exception:
            content = ""

        return await self.validate_toml_content(
            toml_content=content,
            name=resolved_path.name,
            required_fields=required_fields,
            required_patterns=required_patterns,
            require_pinned_versions=require_pinned_versions,
            is_pyproject=is_pyproject,
            trace_id=trace_id,
        )
