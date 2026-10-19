"""
Blueprint:
- Adapter loading trusted proxies directly from external component config.yml.
"""
import os
import yaml  # type: ignore[import-untyped]
from typing import List, Optional
from src.features.server.pipeline_peer_resolution.infrastructure.ports.pipeline_peer_resolution_port import PeerConfigPort

class StandardPeerConfigAdapter(PeerConfigPort):
    def __init__(self, proxies: Optional[List[str]] = None, config_path: Optional[str] = None) -> None:
        if proxies is not None:
            self._proxies = proxies
        else:
            path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or {}
                self._proxies = data.get("trusted_proxies", ["127.0.0.1/32"])
            else:
                self._proxies = ["127.0.0.1/32"]

    def get_trusted_proxies(self) -> List[str]:
        return self._proxies
