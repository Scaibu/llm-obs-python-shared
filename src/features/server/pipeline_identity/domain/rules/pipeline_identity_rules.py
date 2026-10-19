"""
Blueprint:
- Pure business logic rules for W3C traceparent format validation and hop trust.
"""
import re

class IdentityRules:
    W3C_TRACEPARENT_PATTERN = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")

    @classmethod
    def is_valid_traceparent(cls, traceparent: str) -> bool:
        if not traceparent or not isinstance(traceparent, str):
            return False
        return bool(cls.W3C_TRACEPARENT_PATTERN.match(traceparent))

    @classmethod
    def should_propagate(cls, traceparent: str, is_trusted_hop: bool) -> bool:
        return is_trusted_hop and cls.is_valid_traceparent(traceparent)
