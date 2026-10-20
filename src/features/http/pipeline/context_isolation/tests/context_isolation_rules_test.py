"""
Blueprint:
- Unit tests for context_isolation rules.
"""
import pytest
from src.features.http.pipeline.context_isolation.domain.rules.context_isolation_rules import (
    ContextIsolationRules,
)

def test_validate_tenant_identity_authenticated():
    assert ContextIsolationRules.validate_tenant_identity("tenant-custom") == "tenant-custom"

def test_validate_tenant_identity_service():
    assert ContextIsolationRules.validate_tenant_identity(None, service_principals_allowed=True) == "service"

def test_validate_tenant_identity_missing_rejected():
    with pytest.raises(PermissionError) as exc:
        ContextIsolationRules.validate_tenant_identity(None, service_principals_allowed=False)
    assert "Missing authenticated tenant identity" in str(exc.value)

def test_sanitize_headers_strips_inbound_tenant():
    headers = {"X-Tenant-ID": "spoofed", "Accept": "application/json"}
    sanitized = ContextIsolationRules.sanitize_headers(headers)
    assert "X-Tenant-ID" not in sanitized
    assert "x-tenant-id" not in sanitized
    assert sanitized["Accept"] == "application/json"

def test_payload_size_valid():
    size = ContextIsolationRules.calculate_payload_size_bytes({"hello": "world"})
    ContextIsolationRules.validate_payload_size(size, 1000)

def test_payload_size_exceeded():
    with pytest.raises(ValueError) as exc:
        ContextIsolationRules.validate_payload_size(500, 100)
    assert "exceeds maximum limit" in str(exc.value)
