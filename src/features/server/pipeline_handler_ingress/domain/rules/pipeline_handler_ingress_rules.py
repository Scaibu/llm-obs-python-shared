"""
Blueprint:
- Ingress expectation and streaming rules.
"""
from typing import Dict

class HandlerIngressRules:
    @staticmethod
    def expects_continue(headers: Dict[str, str]) -> bool:
        norm = {k.lower(): v for k, v in headers.items()}
        expect = norm.get("expect", "")
        return expect.lower().strip() == "100-continue"
