"""
Blueprint:
- Service creating, validating, and freezing ServerPolicySnapshot.
- Exits or raises ConfigurationError aggregating all issues.
"""
from src.features.server.server_configuration.contracts.server_config_types import ServerPolicySnapshot
from src.features.server.server_configuration.domain.rules.server_config_rules import ServerConfigRules
from src.features.server.server_configuration.infrastructure.ports.server_config_port import ServerConfigPort

class ServerConfigurationService:
    def __init__(self, port: ServerConfigPort) -> None:
        self._port = port

    def build_snapshot(self) -> ServerPolicySnapshot:
        raw_data = self._port.load_config_data()
        snapshot = ServerPolicySnapshot(**raw_data)
        errors = ServerConfigRules.validate_snapshot(snapshot)
        if errors:
            raise ValueError(f"Configuration validation failed with {len(errors)} errors: " + "; ".join(errors))
        return snapshot

    @classmethod
    def from_file(cls, config_path: str) -> "ServerConfigurationService":
        import yaml
        from pathlib import Path
        from src.features.server.server_configuration.infrastructure.adapters.server_config_adapter import (
            StandardServerConfigAdapter,
        )
        p = Path(config_path)
        if p.is_dir():
            p = p / "server-config.yml"
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(StandardServerConfigAdapter(data))

