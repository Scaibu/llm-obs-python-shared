"""
Blueprint:
- In-memory adapter for concurrency admission control port.
"""
from src.features.http.pipeline.resilience.concurrency_admission_control import ConcurrencyAdmissionControl
from src.features.http.pipeline.admission_control.infrastructure.ports.admission_control_port import (
    ConcurrencyAdmissionControlPort,
)

class ConcurrencyAdmissionControlAdapter(ConcurrencyAdmissionControlPort):
    def __init__(self, delegate: ConcurrencyAdmissionControl | None = None) -> None:
        self._delegate = delegate or ConcurrencyAdmissionControl()

    def acquire(self) -> bool:
        return self._delegate.acquire()

    def release(self) -> None:
        self._delegate.release()

    def get_active_count(self) -> int:
        return self._delegate.get_active_count()
