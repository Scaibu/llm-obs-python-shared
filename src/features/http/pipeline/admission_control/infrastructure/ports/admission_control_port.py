"""
Blueprint:
- Outbound port for concurrency admission control.
"""
from typing import Protocol

class ConcurrencyAdmissionControlPort(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> None: ...
    def get_active_count(self) -> int: ...
