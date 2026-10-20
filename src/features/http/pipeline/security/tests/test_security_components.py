"""
Blueprint:
- Exhaustive unit tests for security assurance, threat modeling, identity lifecycle, input hardening, and fencing tokens.
"""
import pytest
from src.features.http.pipeline.security.threat_model import ThreatModelRules, ThreatModelService
from src.features.http.pipeline.security.identity_lifecycle import IdentityLifecycleRules, IdentityLifecycleConstants
from src.features.http.pipeline.security.input_hardening import InputHardeningRules
from src.features.http.pipeline.security.fencing_coordination import FencingTokenStore

def test_threat_model_audit():
    service = ThreatModelService()
    # Audit with all our implemented controls
    active_controls = [
        "context_isolation.strip_inbound_headers",
        "pipeline_pre_auth_limit",
        "admission_control",
        "upload_pipeline.version_id_binding",
        "upload_pipeline.pixel_flood",
        "archive_bomb_guard",
        "ssrf_validation.blocked_ip_ranges",
        "circuit_breaker",
        "bulkhead_admission",
    ]
    report = service.audit_pipeline(active_controls)
    assert report["all_mitigated"] is True
    assert report["mitigated_count"] == report["total_threats"]

def test_identity_lifecycle_api_key_hashing_and_constant_time():
    raw_key, hashed_key = IdentityLifecycleRules.generate_api_key()
    assert raw_key.startswith(IdentityLifecycleConstants.KEY_PREFIX)
    assert len(hashed_key) == 64

    # Verify constant-time validation succeeds for matching key
    assert IdentityLifecycleRules.verify_api_key_hash(raw_key, hashed_key) is True
    # Fails for tampered key
    assert IdentityLifecycleRules.verify_api_key_hash(raw_key + "tampered", hashed_key) is False

def test_input_hardening_crlf_rejection():
    safe_headers = {"Content-Type": "application/json", "Authorization": "Bearer 123"}
    InputHardeningRules.reject_crlf_in_headers(safe_headers)

    # Injected CR/LF in value
    with pytest.raises(ValueError) as exc1:
        InputHardeningRules.reject_crlf_in_headers({"X-Custom": "safe\r\nInjected-Header: evil"})
    assert "CRLF detected" in str(exc1.value)

    # Injected CR/LF in key
    with pytest.raises(ValueError) as exc2:
        InputHardeningRules.reject_crlf_in_headers({"X-Custom\n": "val"})
    assert "CRLF detected" in str(exc2.value)

def test_input_hardening_ijson_duplicate_keys_and_depth():
    # Duplicate key must be rejected (I-JSON RFC 7493)
    duplicate_key_json = '{"user": "alice", "user": "bob"}'
    with pytest.raises(ValueError) as exc1:
        InputHardeningRules.parse_strict_ijson(duplicate_key_json)
    assert "Duplicate JSON key detected" in str(exc1.value)

    # Valid JSON parses
    clean_json = '{"user": "alice", "role": "admin"}'
    data = InputHardeningRules.parse_strict_ijson(clean_json)
    assert data["user"] == "alice"

    # Excessive nesting depth rejected
    deep_json = '{"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": {"l": {"m": {"n": {"o": {"p": {"q": {"r": {"s": {"t": {"u": 1}}}}}}}}}}}}}}}}}}}}}'
    with pytest.raises(ValueError) as exc2:
        InputHardeningRules.parse_strict_ijson(deep_json)
    assert "JSON nesting depth" in str(exc2.value)

def test_fencing_token_store_rejects_stale_writes():
    store = FencingTokenStore()
    token1 = store.issue_token("resource-1")
    token2 = store.issue_token("resource-1")
    assert token2 > token1

    # Writer with token 2 commits first
    assert store.accept_write("resource-1", token2) is True

    # Writer with stale token 1 attempts write -> must be rejected
    assert store.accept_write("resource-1", token1) is False
