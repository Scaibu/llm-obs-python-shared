"""
Blueprint:
- In-memory admission tracker reading max concurrency limit from external component config.yml.
"""
import os
import yaml  # type: ignore[import-untyped]
import threading
from typing import Optional
from src.features.server.pipeline_global_admission.infrastructure.ports.pipeline_global_admission_port import AdmissionTrackerPort

class InMemoryAdmissionTrackerAdapter(AdmissionTrackerPort):
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._counter = 0
        self._lock = threading.Lock()
        path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            self.max_concurrency = data.get("max_concurrency", 1000)
        else:
            self.max_concurrency = 1000

    def get_in_flight(self) -> int:
        with self._lock:
            return self._counter

    def increment(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter

    def decrement(self) -> int:
        with self._lock:
            self._counter = max(0, self._counter - 1)
            return self._counter
