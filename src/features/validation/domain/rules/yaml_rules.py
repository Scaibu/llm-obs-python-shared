"""
Blueprint:
- Pure business logic rules for YAML validation.
- Single Responsibility: Enforces YAML syntax parsing and structure checks without I/O or persistence coupling.
"""

from __future__ import annotations

import yaml
from typing import Any

from src.features.validation.contracts.validation_types import (
    ValidationErrorDetail,
    ValidationSeverity,
)


class YamlValidationRules:
    @staticmethod
    def validate_yaml_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:
        if not content or not content.strip():
            err = ValidationErrorDetail(
                code="EMPTY_CONTENT",
                message="Contract content is empty or blank.",
                path="content",
                severity=ValidationSeverity.ERROR,
            )
            return False, None, err

        try:
            parsed = yaml.safe_load(content)
            return True, parsed, None
        except yaml.YAMLError as exc:
            err = ValidationErrorDetail(
                code="YAML_SYNTAX_ERROR",
                message=f"YAML syntax invalid: {exc}",
                path="content",
                severity=ValidationSeverity.ERROR,
                context={"exception": str(exc)},
            )
            return False, None, err
