"""
Blueprint:
- Port for peer resolution configuration.
"""
from typing import Protocol, List

class PeerConfigPort(Protocol):
    def get_trusted_proxies(self) -> List[str]: ...
