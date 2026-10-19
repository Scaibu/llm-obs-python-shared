"""
Blueprint:
- Pure business logic rules and decision tables for key normalization and common pattern extraction.
- Single Responsibility: Enforces Key Normalization invariants (idempotence, totality, canonicalization) and regex/field rules.
- Free of I/O, persistence, or framework dependencies.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.features.validation.contracts.validation_types import (
    CanonicalKeyDTO,
    ValidationErrorDetail,
    ValidationSeverity,
)


class KeyNormalizationRules:
    @staticmethod
    def canonicalize_key(raw_key: str, norm_version: int = 1) -> CanonicalKeyDTO:
        if not isinstance(raw_key, str):
            raise TypeError(f"Raw key must be a string, got {type(raw_key).__name__}")

        stripped = raw_key.strip()
        if not stripped:
            raise ValueError("Key cannot be empty or whitespace only.")

        clean_str = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", stripped)
        canonical = clean_str.casefold()
        canonical = re.sub(r"\s+", "_", canonical)
        canonical = re.sub(r"[^\w\.\-\:]", "", canonical)

        if not canonical:
            raise ValueError(f"Key '{raw_key}' reduced to empty string after canonicalization.")

        return CanonicalKeyDTO(raw_key=raw_key, canonical_key=canonical, norm_version=norm_version)


class SchemaValidationRules:
    @staticmethod
    def extract_regex_patterns(
        content: str, patterns: Sequence[str]
    ) -> tuple[Mapping[str, str], Sequence[ValidationErrorDetail]]:
        extracted: dict[str, str] = {}
        errors: list[ValidationErrorDetail] = []

        for pat in patterns:
            try:
                compiled = re.compile(pat, re.MULTILINE)
                m = compiled.search(content)
                if m:
                    extracted[pat] = m.group(1).strip() if m.groups() else m.group(0).strip()
                else:
                    errors.append(
                        ValidationErrorDetail(
                            code="PATTERN_NOT_FOUND",
                            message=f"Required pattern not matched: {pat}",
                            path="content",
                            severity=ValidationSeverity.ERROR,
                            context={"pattern": pat},
                        )
                    )
            except re.error as re_err:
                errors.append(
                    ValidationErrorDetail(
                        code="INVALID_REGEX_PATTERN",
                        message=f"Invalid regular expression pattern '{pat}': {re_err}",
                        path="required_patterns",
                        severity=ValidationSeverity.ERROR,
                        context={"pattern": pat},
                    )
                )

        return extracted, tuple(errors)

    @staticmethod
    def validate_schema_fields(
        parsed_doc: Any, required_fields: Sequence[str]
    ) -> Sequence[ValidationErrorDetail]:
        if not isinstance(parsed_doc, dict):
            return (
                ValidationErrorDetail(
                    code="INVALID_DOCUMENT_ROOT",
                    message="Parsed contract root must be a mapping dictionary.",
                    path="root",
                    severity=ValidationSeverity.ERROR,
                ),
            )

        errors: list[ValidationErrorDetail] = []
        for fld in required_fields:
            if fld not in parsed_doc:
                errors.append(
                    ValidationErrorDetail(
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Missing required field in contract: '{fld}'",
                        path=fld,
                        severity=ValidationSeverity.ERROR,
                    )
                )
            elif parsed_doc[fld] is None:
                errors.append(
                    ValidationErrorDetail(
                        code="NULL_FIELD_NOT_ALLOWED",
                        message=f"Field '{fld}' cannot be null.",
                        path=fld,
                        severity=ValidationSeverity.ERROR,
                    )
                )

        return tuple(errors)
