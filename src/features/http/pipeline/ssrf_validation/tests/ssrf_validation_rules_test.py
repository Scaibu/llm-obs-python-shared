"""
Blueprint:
- Unit tests for ssrf_validation rules.
"""
import pytest
from src.features.http.pipeline.ssrf_validation.domain.rules.ssrf_validation_rules import (
    SsrfValidationRules,
)

def test_ssrf_valid_url():
    hostname = SsrfValidationRules.validate_url("https://api.example.com/v1/resource", target_class="declared_upstream")
    assert hostname == "api.example.com"

def test_ssrf_invalid_url():
    with pytest.raises(ValueError) as exc:
        SsrfValidationRules.validate_url("not_a_valid_url", target_class="declared_upstream")
    assert "Invalid URL" in str(exc.value)

def test_ssrf_disallowed_host():
    with pytest.raises(ValueError) as exc:
        SsrfValidationRules.validate_url("https://evil.com/leak", target_class="user_supplied_url", allowed_hosts=["api.example.com"])
    assert "not in allowed hosts" in str(exc.value)
