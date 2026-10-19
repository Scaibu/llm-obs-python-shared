"""
Blueprint:
- Pure authentication header parsing rules.
"""
from typing import Dict, Optional

class AuthenticationRules:
    @staticmethod
    def extract_bearer_token(headers: Dict[str, str]) -> Optional[str]:
        norm = {k.lower(): v for k, v in headers.items()}
        auth_header = norm.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return None
