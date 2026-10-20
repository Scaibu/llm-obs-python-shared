"""
Blueprint:
- Unit tests for singleflight rules.
"""
from src.features.http.pipeline.singleflight.domain.rules.singleflight_rules import (
    SingleflightRules,
)

def test_generate_hashed_key_deterministic():
    k1 = SingleflightRules.generate_hashed_key("t1", "p1", "GET", "https://api.test", None)
    k2 = SingleflightRules.generate_hashed_key("t1", "p1", "GET", "https://api.test", None)
    assert k1 == k2
    assert len(k1) == 64

def test_should_deduplicate():
    assert SingleflightRules.should_deduplicate("GET", False) is True
    assert SingleflightRules.should_deduplicate("GET", True) is False
    assert SingleflightRules.should_deduplicate("POST", False) is False
