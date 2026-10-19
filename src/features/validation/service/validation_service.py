"""
Blueprint:
- Validation Service facade coordinating specialized validation services.
- Delegates to YamlValidationService for YAML files/contracts.
- Delegates to JsonValidationService for JSON files/schemas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.features.validation.contracts.validation_types import (
    CanonicalKeyDTO,
    ContractValidationRequestDTO,
    ValidationReportModel,
    ValidationTargetType,
)
from src.features.validation.domain.rules.validation_rules import ValidationRules
from src.features.validation.service.yaml_validation_service import YamlValidationService
from src.features.validation.service.json_validation_service import JsonValidationService
from src.features.validation.service.toml_validation_service import TomlValidationService
from src.features.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class ValidationService:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository
        self.yaml_service = YamlValidationService(repository=repository)
        self.json_service = JsonValidationService(repository=repository)
        self.toml_service = TomlValidationService(repository=repository)

    async def validate_contract(
        self, request: ContractValidationRequestDTO, trace_id: str = ""
    ) -> ValidationReportModel:
        if request.target_type == ValidationTargetType.JSON:
            return await self.json_service.validate_json_content(
                json_content=request.content,
                name=request.contract_name,
                required_fields=request.schema_definition.get("required_fields", ()),
                required_patterns=request.required_patterns,
                trace_id=trace_id,
            )
        if request.target_type == ValidationTargetType.TOML:
            return await self.toml_service.validate_toml_content(
                toml_content=request.content,
                name=request.contract_name,
                required_fields=request.schema_definition.get("required_fields", ()),
                required_patterns=request.required_patterns,
                require_pinned_versions=bool(request.schema_definition.get("require_pinned_versions", False)),
                is_pyproject=bool(request.schema_definition.get("is_pyproject", True)),
                trace_id=trace_id,
            )
        return await self.yaml_service.validate_yaml_content(
            yaml_content=request.content,
            contract_name=request.contract_name,
            required_fields=request.schema_definition.get("required_fields", ()),
            required_patterns=request.required_patterns,
            trace_id=trace_id,
        )

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
        return await self.toml_service.validate_toml_content(
            toml_content=toml_content,
            name=name,
            required_fields=required_fields,
            required_patterns=required_patterns,
            require_pinned_versions=require_pinned_versions,
            is_pyproject=is_pyproject,
            trace_id=trace_id,
        )

    async def validate_toml_file(
        self,
        file_path: str | Path,
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        require_pinned_versions: bool = False,
        is_pyproject: bool = True,
        trace_id: str = "",
    ) -> ValidationReportModel:
        return await self.toml_service.resolve_and_validate_file(
            candidate_paths=[file_path],
            required_fields=required_fields,
            required_patterns=required_patterns,
            require_pinned_versions=require_pinned_versions,
            is_pyproject=is_pyproject,
            trace_id=trace_id,
        )

    async def validate_json_content(
        self,
        json_content: str,
        name: str = "payload.json",
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        return await self.json_service.validate_json_content(
            json_content=json_content,
            name=name,
            required_fields=required_fields,
            required_patterns=required_patterns,
            trace_id=trace_id,
        )

    async def validate_json_file(
        self,
        file_path: str | Path,
        required_fields: Sequence[str] = (),
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        return await self.json_service.resolve_and_validate_file(
            candidate_paths=[file_path],
            required_fields=required_fields,
            required_patterns=required_patterns,
            trace_id=trace_id,
        )

    async def resolve_and_validate_file(
        self,
        candidate_paths: Sequence[str | Path],
        required_patterns: Sequence[str] = (),
        trace_id: str = "",
    ) -> ValidationReportModel:
        return await self.yaml_service.resolve_and_validate_file(
            candidate_paths=candidate_paths,
            required_patterns=required_patterns,
            trace_id=trace_id,
        )

    def canonicalize_key(self, raw_key: str, norm_version: int = 1) -> CanonicalKeyDTO:
        return ValidationRules.canonicalize_key(raw_key=raw_key, norm_version=norm_version)
