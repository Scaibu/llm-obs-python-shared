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
