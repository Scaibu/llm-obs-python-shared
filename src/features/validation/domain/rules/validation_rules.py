"""
Blueprint:
- Facade combining specialized domain rules for backward compatibility.
- Concrete rules are separated by format/concern following SRP:
    * KeyNormalizationRules & SchemaValidationRules -> common_rules.py
    * YamlValidationRules -> yaml_rules.py
    * JsonValidationRules -> json_rules.py
    * TomlValidationRules -> toml_rules.py
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.features.validation.contracts.validation_types import (
    CanonicalKeyDTO,
    ValidationErrorDetail,
)
from src.features.validation.domain.rules.common_rules import (
    KeyNormalizationRules,
    SchemaValidationRules,
)
from src.features.validation.domain.rules.yaml_rules import YamlValidationRules
from src.features.validation.domain.rules.json_rules import JsonValidationRules
from src.features.validation.domain.rules.toml_rules import TomlValidationRules


class ValidationRules:
    @staticmethod
    def canonicalize_key(raw_key: str, norm_version: int = 1) -> CanonicalKeyDTO:
        return KeyNormalizationRules.canonicalize_key(raw_key, norm_version)

    @staticmethod
    def validate_yaml_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:
        return YamlValidationRules.validate_yaml_syntax(content)

    @staticmethod
    def validate_json_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:
        return JsonValidationRules.validate_json_syntax(content)

    @staticmethod
    def validate_toml_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:
        return TomlValidationRules.validate_toml_syntax(content)

    @staticmethod
    def extract_regex_patterns(
        content: str, patterns: Sequence[str]
    ) -> tuple[Mapping[str, str], Sequence[ValidationErrorDetail]]:
        return SchemaValidationRules.extract_regex_patterns(content, patterns)

    @staticmethod
    def validate_schema_fields(
        parsed_doc: Any, required_fields: Sequence[str]
    ) -> Sequence[ValidationErrorDetail]:
        return SchemaValidationRules.validate_schema_fields(parsed_doc, required_fields)

    @staticmethod
    def validate_pyproject_structure(
        parsed_doc: Any,
        require_pinned_versions: bool = False,
    ) -> Sequence[ValidationErrorDetail]:
        return TomlValidationRules.validate_pyproject_structure(parsed_doc, require_pinned_versions)
