"""
Blueprint:
- Pure business logic rules for JSON validation.
- Single Responsibility: Enforces JSON syntax parsing and decoding checks without I/O or persistence coupling.
"""

from __future__ import annotations

import json
from typing import Any

from python_shared.validation.contracts.validation_types import (
    ValidationErrorDetail,
    ValidationSeverity,
)


class JsonValidationRules:
    @staticmethod
    def validate_json_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:
        if not content or not content.strip():
            err = ValidationErrorDetail(
                code="EMPTY_CONTENT",
                message="JSON content is empty or blank.",
                path="content",
                severity=ValidationSeverity.ERROR,
            )
            return False, None, err

        try:
            parsed = json.loads(content)
            return True, parsed, None
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            err = ValidationErrorDetail(
                code="JSON_SYNTAX_ERROR",
                message=f"JSON syntax invalid: {exc}",
                path="content",
                severity=ValidationSeverity.ERROR,
                context={"exception": str(exc)},
            )
            return False, None, err
