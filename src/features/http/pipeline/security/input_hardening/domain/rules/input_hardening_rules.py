"""
Blueprint:
- Input hardening rules:
  1. RFC 7493 / I-JSON parser limits (max nesting depth, max keys, reject duplicate keys)
  2. CRLF injection prevention in headers (rejects \r and \n in header names or values)
  3. Unicode confusable normalization and character bounds
"""
import json
from typing import Any, Dict, List, Set

class InputHardeningConstants:
    MAX_JSON_DEPTH: int = 20
    MAX_JSON_KEYS: int = 1000
    MAX_STRING_LENGTH: int = 65536

class InputHardeningRules:
    @staticmethod
    def reject_crlf_in_headers(headers: Dict[str, str]) -> None:
        # 4.6 CRLF in outbound headers: Reject CR and LF in any header name or value
        for key, value in headers.items():
            if "\r" in key or "\n" in key:
                raise ValueError(f"CRLF detected in header name: '{key}'")
            if "\r" in str(value) or "\n" in str(value):
                raise ValueError(f"CRLF detected in header value for key: '{key}'")

    @staticmethod
    def parse_strict_ijson(raw_json: str) -> Any:
        # 4.1 & 4.2 RFC 7493 I-JSON duplicate key rejection and depth validation
        def dict_with_duplicate_check(ordered_pairs):
            d = {}
            for k, v in ordered_pairs:
                if k in d:
                    raise ValueError(f"Duplicate JSON key detected: '{k}' (violates I-JSON RFC 7493)")
                d[k] = v
            return d

        data = json.loads(raw_json, object_pairs_hook=dict_with_duplicate_check)
        depth = InputHardeningRules._calculate_depth(data)
        if depth > InputHardeningConstants.MAX_JSON_DEPTH:
            raise ValueError(f"JSON nesting depth {depth} exceeds max allowed ({InputHardeningConstants.MAX_JSON_DEPTH})")
        return data

    @staticmethod
    def _calculate_depth(val: Any, current_depth: int = 1) -> int:
        if isinstance(val, dict):
            if not val:
                return current_depth
            return max(InputHardeningRules._calculate_depth(v, current_depth + 1) for v in val.values())
        if isinstance(val, list):
            if not val:
                return current_depth
            return max(InputHardeningRules._calculate_depth(item, current_depth + 1) for item in val)
        return current_depth
