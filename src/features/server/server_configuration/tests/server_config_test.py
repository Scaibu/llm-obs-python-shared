"""
Blueprint:
- Unit tests for server configuration validation rules.
"""
import pytest
from src.features.server.server_configuration import (
    ServerPolicySnapshot,
    ServerConfigRules,
    ServerConfigurationService,
    StandardServerConfigAdapter,
)

def test_valid_snapshot() -> None:
    snapshot = ServerPolicySnapshot()
    errors = ServerConfigRules.validate_snapshot(snapshot)
    assert len(errors) == 0

def test_timeout_hierarchy_violation() -> None:
    raw = {
        "server": {
            "header_read_timeout": "70s",
            "idle_connection_timeout": "65s",
        }
    }
    service = ServerConfigurationService(StandardServerConfigAdapter(raw))
    with pytest.raises(ValueError) as exc:
        service.build_snapshot()
    assert "header_read_timeout (70s) must be < idle_connection_timeout (65s)" in str(exc.value)

def test_admin_bind_public_violation() -> None:
    raw = {
        "server": {
            "admin_bind": "0.0.0.0:9090",
        }
    }
    service = ServerConfigurationService(StandardServerConfigAdapter(raw))
    with pytest.raises(ValueError) as exc:
        service.build_snapshot()
    assert "admin_bind must not listen on public interface" in str(exc.value)
