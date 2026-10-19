"""
Blueprint:
- Port for in-flight counter tracking.
"""
from typing import Protocol

class AdmissionTrackerPort(Protocol):
    def get_in_flight(self) -> int: ...
    def increment(self) -> int: ...
    def decrement(self) -> int: ...
