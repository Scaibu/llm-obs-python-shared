"""
Blueprint:
- Exhaustive unit tests for validation business rules.
- Tests key normalization properties (idempotence f(f(x)) == f(x), totality, canonical equivalence).
- Tests boundary conditions, invalid inputs, YAML syntax validation, and regex extraction.
"""

import pytest
from src.features.validation.domain.rules.validation_rules import ValidationRules


def test_canonicalize_key_idempotence():
    raw_inputs = [
        "  User.Email_Address  ",
        "UPPER_CASE_KEY",
        "special!@#$characters%^&*",
        "multiple   spaces   between",
        "tab\tnewline\nvalues",
    ]
    for raw in raw_inputs:
        first = ValidationRules.canonicalize_key(raw)
        second = ValidationRules.canonicalize_key(first.canonical_key)
        assert first.canonical_key == second.canonical_key, f"Idempotence failed for {raw}"


def test_canonicalize_key_invalid_inputs():
    with pytest.raises(ValueError):
        ValidationRules.canonicalize_key("")

    with pytest.raises(ValueError):
        ValidationRules.canonicalize_key("    ")

    with pytest.raises(TypeError):
        ValidationRules.canonicalize_key(None)  # type: ignore

    with pytest.raises(TypeError):
        ValidationRules.canonicalize_key(12345)  # type: ignore


def test_canonicalize_key_soundness():
    k1 = ValidationRules.canonicalize_key("hello_world")
    k2 = ValidationRules.canonicalize_key("  HELLO_WORLD  ")
    assert k1.canonical_key == k2.canonical_key


def test_validate_yaml_syntax_valid():
    yaml_content = """
    name: test_contract
    version: 1.0.0
    rules:
      - id: rule_1
        threshold: 0.95
    """
    valid, parsed, err = ValidationRules.validate_yaml_syntax(yaml_content)
    assert valid is True
    assert parsed is not None
    assert parsed["name"] == "test_contract"
    assert err is None


def test_validate_yaml_syntax_invalid():
    bad_yaml = "name: test: invalid: [unclosed"
    valid, parsed, err = ValidationRules.validate_yaml_syntax(bad_yaml)
    assert valid is False
    assert parsed is None
    assert err is not None
    assert err.code == "YAML_SYNTAX_ERROR"


def test_validate_yaml_empty_content():
    valid, parsed, err = ValidationRules.validate_yaml_syntax("   ")
    assert valid is False
    assert err is not None
    assert err.code == "EMPTY_CONTENT"


def test_extract_regex_patterns():
    doc = """
    service_name: llm-worker
    max_retries: 5
    """
    patterns = [r"service_name:\s*([^\s]+)", r"max_retries:\s*(\d+)", r"missing_key:\s*([^\s]+)"]
    extracted, errors = ValidationRules.extract_regex_patterns(doc, patterns)

    assert extracted[patterns[0]] == "llm-worker"
    assert extracted[patterns[1]] == "5"
    assert len(errors) == 1
    assert errors[0].code == "PATTERN_NOT_FOUND"


def test_validate_schema_fields():
    doc = {"name": "contract", "version": "1.0", "null_field": None}
    errors = ValidationRules.validate_schema_fields(doc, ["name", "version", "required_but_missing", "null_field"])
    error_codes = [e.code for e in errors]

    assert "MISSING_REQUIRED_FIELD" in error_codes
    assert "NULL_FIELD_NOT_ALLOWED" in error_codes


def test_validate_json_syntax_valid():
    json_content = '{"service": "llm-obs", "timeout_ms": 5000, "features": ["logging", "tracing"]}'
    valid, parsed, err = ValidationRules.validate_json_syntax(json_content)
    assert valid is True
    assert parsed is not None
    assert parsed["service"] == "llm-obs"
    assert parsed["timeout_ms"] == 5000
    assert err is None


def test_validate_json_syntax_invalid():
    bad_json = '{"service": "llm-obs", unquoted_key: 123}'
    valid, parsed, err = ValidationRules.validate_json_syntax(bad_json)
    assert valid is False
    assert parsed is None
    assert err is not None
    assert err.code == "JSON_SYNTAX_ERROR"


def test_validate_json_empty_content():
    valid, parsed, err = ValidationRules.validate_json_syntax("   ")
    assert valid is False
    assert parsed is None
    assert err is not None
    assert err.code == "EMPTY_CONTENT"


def test_validate_toml_syntax_valid():
    toml_str = """
    [build-system]
    requires = ["setuptools>=61.0"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "llm-obs"
    version = "1.0.0"
    dependencies = ["httpx>=0.27.0", "pydantic==2.8.2"]
    """
    valid, parsed, err = ValidationRules.validate_toml_syntax(toml_str)
    assert valid is True
    assert parsed is not None
    assert parsed["project"]["name"] == "llm-obs"
    assert err is None


def test_validate_toml_syntax_invalid():
    bad_toml = "[project\nname = 123"
    valid, parsed, err = ValidationRules.validate_toml_syntax(bad_toml)
    assert valid is False
    assert err is not None
    assert err.code == "TOML_SYNTAX_ERROR"


def test_validate_pyproject_structure_valid():
    doc = {
        "build-system": {
            "requires": ["setuptools>=61.0"],
            "build-backend": "setuptools.build_meta",
        },
        "project": {
            "name": "llm-obs",
            "version": "1.0.0",
            "dependencies": ["pydantic>=2.0.0", "httpx==0.27.0"],
        },
    }
    errors = ValidationRules.validate_pyproject_structure(doc, require_pinned_versions=True)
    assert len(errors) == 0


def test_validate_pyproject_structure_missing_build_and_unpinned():
    doc = {
        "project": {
            "name": "llm-obs",
            "dependencies": ["pydantic", "httpx>=0.27.0"],
        }
    }
    errors = ValidationRules.validate_pyproject_structure(doc, require_pinned_versions=True)
    codes = [e.code for e in errors]
    assert "MISSING_BUILD_SYSTEM" in codes
    assert "MISSING_VERSION" in codes
    assert "UNPINNED_DEPENDENCY" in codes

