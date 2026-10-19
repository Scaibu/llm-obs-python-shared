"""
Blueprint:
- Pure immutable data transfer objects and domain models for validation feature.
- Follows strict Single Responsibility Principle: no business logic, no I/O, no persistence.
- Enforces closed type definitions and explicit error contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationTargetType(str, Enum):
    CONTRACT = "CONTRACT"
    WORKFLOW = "WORKFLOW"
    KEY = "KEY"
    SCHEMA = "SCHEMA"
    JSON = "JSON"
    TOML = "TOML"


class ValidationStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    VALID = "VALID"
    INVALID = "INVALID"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ValidationErrorDetail:
    code: str
    message: str
    path: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalKeyDTO:
    raw_key: str
    canonical_key: str
    norm_version: int = 1


@dataclass(frozen=True)
class ContractValidationRequestDTO:
    contract_name: str
    content: str
    target_type: ValidationTargetType = ValidationTargetType.CONTRACT
    required_patterns: Sequence[str] = field(default_factory=list)
    schema_definition: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReportModel:
    validation_id: str
    target_name: str
    target_type: ValidationTargetType
    status: ValidationStatus
    errors: Sequence[ValidationErrorDetail] = field(default_factory=list)
    extracted_metadata: Mapping[str, Any] = field(default_factory=dict)
    is_valid: bool = False
