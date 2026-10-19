"""
Blueprint:
- Adapter loading declarative configuration data.
"""
from typing import Dict, Any, Optional
from src.features.server.server_configuration.infrastructure.ports.server_config_port import ServerConfigPort

class StandardServerConfigAdapter(ServerConfigPort):
    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self._data = data if data is not None else {}

    def load_config_data(self) -> Dict[str, Any]:
        return self._data
