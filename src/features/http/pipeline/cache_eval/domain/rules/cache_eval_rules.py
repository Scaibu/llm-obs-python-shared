"""
Blueprint:
- Decision rules for cache evaluation and RFC 9111 storability.
- Strictly guards against caching authenticated requests unless explicitly public.
"""
from typing import Dict, Optional
from src.features.http.pipeline.cache_eval.contracts.cache_eval_constants import (
    CacheEvalConstants,
)

class CacheEvalRules:
    @staticmethod
    def is_mutating(method: str) -> bool:
        return method.upper() in CacheEvalConstants.MUTATING_METHODS

    @staticmethod
    def should_lookup_cache(
        method: str,
        no_cache: bool,
        hashed_request_key: Optional[str],
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        if method.upper() not in (CacheEvalConstants.METHOD_GET, "HEAD"):
            return False
        if no_cache or not hashed_request_key:
            return False
        
        # Check client Cache-Control header case-insensitively
        if headers:
            cc = ""
            for k, v in headers.items():
                if k.lower() == "cache-control":
                    cc = v.lower()
                    break
            if "no-cache" in cc or "no-store" in cc:
                return False

        return True

    @staticmethod
    def is_storable(request_headers: Dict[str, str], response_headers: Dict[str, str]) -> bool:
        req_auth = any(k.lower() == "authorization" for k in request_headers.keys())
        
        resp_cc = ""
        for k, v in response_headers.items():
            if k.lower() == "cache-control":
                resp_cc = v.lower()
                break

        if "no-store" in resp_cc:
            return False

        # RFC 9111 §3.5: Shared cache MUST NOT store response to request with Authorization
        # unless response explicitly contains public, s-maxage, or must-revalidate
        if req_auth:
            if not any(token in resp_cc for token in ("public", "s-maxage", "must-revalidate")):
                return False

        return True
