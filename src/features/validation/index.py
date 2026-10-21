"""
Blueprint:
- Public facade for validation feature.
- Exports service, port, adapters, DTOs, and router.
- Shields internal implementation details.
"""

from __future__ import annotations

from src.features.validation.contracts.validation_types import (
    CanonicalKeyDTO,
    ContractValidationRequestDTO,
    ValidationErrorDetail,
    ValidationReportModel,
    ValidationSeverity,
    ValidationStatus,
    ValidationTargetType,
)
from src.features.validation.domain.rules.common_rules import (
    KeyNormalizationRules,
    SchemaValidationRules,
)
from src.features.validation.domain.rules.yaml_rules import YamlValidationRules
from src.features.validation.domain.rules.json_rules import JsonValidationRules
from src.features.validation.domain.rules.toml_rules import TomlValidationRules
from src.features.validation.domain.rules.validation_rules import ValidationRules
from src.features.validation.domain.machines.validation_machine import ValidationStateMachine
from src.features.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)
from src.features.validation.infrastructure.adapters.validation_repository_adapter import (
    InMemoryValidationRepositoryAdapter,
)
from src.features.validation.service.yaml_validation_service import YamlValidationService
from src.features.validation.service.json_validation_service import JsonValidationService
from src.features.validation.service.toml_validation_service import TomlValidationService
from src.features.validation.service.validation_service import ValidationService
try:
    from src.api.rest.v1.routers.validation_router import validation_router
except Exception:
    validation_router = None

__all__ = [
    "CanonicalKeyDTO",
    "ContractValidationRequestDTO",
    "ValidationErrorDetail",
    "ValidationReportModel",
    "ValidationSeverity",
    "ValidationStatus",
    "ValidationTargetType",
    "KeyNormalizationRules",
    "SchemaValidationRules",
    "YamlValidationRules",
    "JsonValidationRules",
    "TomlValidationRules",
    "ValidationRules",
    "ValidationStateMachine",
    "ValidationRepositoryPort",
    "InMemoryValidationRepositoryAdapter",
    "YamlValidationService",
    "JsonValidationService",
    "TomlValidationService",
    "ValidationService",
    "validation_router",
]
