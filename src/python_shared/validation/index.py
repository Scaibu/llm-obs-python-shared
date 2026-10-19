"""
Blueprint:
- Public facade for validation feature.
- Exports service, port, adapters, DTOs, and router.
- Shields internal implementation details.
"""

from __future__ import annotations

from python_shared.validation.contracts.validation_types import (
    CanonicalKeyDTO,
    ContractValidationRequestDTO,
    ValidationErrorDetail,
    ValidationReportModel,
    ValidationSeverity,
    ValidationStatus,
    ValidationTargetType,
)
from python_shared.validation.domain.rules.common_rules import (
    KeyNormalizationRules,
    SchemaValidationRules,
)
from python_shared.validation.domain.rules.yaml_rules import YamlValidationRules
from python_shared.validation.domain.rules.json_rules import JsonValidationRules
from python_shared.validation.domain.rules.toml_rules import TomlValidationRules
from python_shared.validation.domain.rules.validation_rules import ValidationRules
from python_shared.validation.domain.machines.validation_machine import ValidationStateMachine
from python_shared.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)
from python_shared.validation.infrastructure.adapters.validation_repository_adapter import (
    InMemoryValidationRepositoryAdapter,
)
from python_shared.validation.service.yaml_validation_service import YamlValidationService
from python_shared.validation.service.json_validation_service import JsonValidationService
from python_shared.validation.service.toml_validation_service import TomlValidationService
from python_shared.validation.service.validation_service import ValidationService

try:
    from api.rest.v1.routers.validation_router import validation_router
except ImportError:
    try:
        from src.api.rest.v1.routers.validation_router import validation_router  # type: ignore[no-redef]
    except ImportError:
        validation_router = None  # type: ignore[assignment]

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
