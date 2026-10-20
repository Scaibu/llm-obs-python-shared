"""
Blueprint:
- Unit tests for cache_eval rules.
"""
from src.features.http.pipeline.cache_eval.domain.rules.cache_eval_rules import (
    CacheEvalRules,
)

def test_cache_mutating_methods():
    assert CacheEvalRules.is_mutating("POST") is True
    assert CacheEvalRules.is_mutating("DELETE") is True
    assert CacheEvalRules.is_mutating("GET") is False

def test_should_lookup_cache():
    assert CacheEvalRules.should_lookup_cache("GET", False, "hash123") is True
    assert CacheEvalRules.should_lookup_cache("GET", True, "hash123") is False
    assert CacheEvalRules.should_lookup_cache("POST", False, "hash123") is False
    assert CacheEvalRules.should_lookup_cache("GET", False, None) is False
