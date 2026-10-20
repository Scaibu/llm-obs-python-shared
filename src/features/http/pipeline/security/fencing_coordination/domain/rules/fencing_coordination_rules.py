"""
Blueprint:
- Fencing token and distributed coordination rules (Kleppmann fencing tokens).
- Prevents split-brain writes when lock leases expire.
"""
from typing import Dict, Optional

class FencingCoordinationRules:
    @staticmethod
    def validate_fencing_token(incoming_token: int, last_seen_token: int) -> bool:
        # Storage rejects any write with a token <= last_seen_token
        return incoming_token > last_seen_token

class FencingTokenStore:
    def __init__(self) -> None:
        self._issued_tokens: Dict[str, int] = {}
        self._committed_tokens: Dict[str, int] = {}

    def issue_token(self, resource_id: str) -> int:
        current = self._issued_tokens.get(resource_id, 0)
        new_token = current + 1
        self._issued_tokens[resource_id] = new_token
        return new_token

    def accept_write(self, resource_id: str, token: int) -> bool:
        last_committed = self._committed_tokens.get(resource_id, 0)
        if FencingCoordinationRules.validate_fencing_token(token, last_committed):
            self._committed_tokens[resource_id] = token
            return True
        return False
