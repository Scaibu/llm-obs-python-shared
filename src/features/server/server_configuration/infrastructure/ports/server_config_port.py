"""
Blueprint:
- Port for reading server configuration dictionary from declarative files.
"""
from typing import Dict, Any, Protocol

class ServerConfigPort(Protocol):
    def load_config_data(self) -> Dict[str, Any]: ...
