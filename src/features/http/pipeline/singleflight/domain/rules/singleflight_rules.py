"""
Blueprint:
- Decision rules for request hashing and deduplication check.
- Generates tenant- and principal-isolated keys incorporating Vary headers.
"""
import hashlib
import json
from typing import Any, Dict, Optional
from src.features.http.pipeline.singleflight.contracts.singleflight_constants import (
    SingleflightConstants,
)

class SingleflightRules:
    @staticmethod
    def generate_hashed_key(
        tenant_id: str,
        principal_id: str,
        method: str,
        url: str,
        body: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        body_str = json.dumps(body) if body else ""
        
        # Hash credential/vary-related headers to prevent cross-principal leakage
        vary_headers = {}
        if headers:
            for k, v in sorted(headers.items()):
                if k.lower() in ("authorization", "accept", "accept-language"):
                    vary_headers[k.lower()] = v
        vary_str = json.dumps(vary_headers, sort_keys=True)

        raw = f"{tenant_id}:{principal_id}:{method.upper()}:{url}:{body_str}:{vary_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def should_deduplicate(method: str, cancel_previous: bool) -> bool:
        return (not cancel_previous) and method.upper() in (
            SingleflightConstants.METHOD_GET,
            "HEAD",
        )
