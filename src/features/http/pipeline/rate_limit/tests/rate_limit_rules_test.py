"""
Blueprint:
- Unit tests for rate_limit rules.
"""
import pytest
from src.features.http.pipeline.rate_limit.domain.rules.rate_limit_rules import (
    RateLimitRules,
)

def test_rate_limit_allowed():
    RateLimitRules.evaluate_rate_limit(True, "tenant-1")

def test_rate_limit_exceeded():
    with pytest.raises(RuntimeError) as exc:
        RateLimitRules.evaluate_rate_limit(False, "tenant-1")
    assert "Rate limit exceeded" in str(exc.value)
