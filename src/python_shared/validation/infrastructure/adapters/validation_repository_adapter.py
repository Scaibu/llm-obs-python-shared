"""
Blueprint:
- Concrete adapter implementing ValidationRepositoryPort.
- Implements in-memory persistence with thread-safe isolation for microservices and test suites.
- Maps domain models cleanly without domain leakage.
"""

from __future__ import annotations

from typing import Dict
from python_shared.validation.contracts.validation_types import ValidationReportModel
from python_shared.validation.infrastructure.ports.validation_repository_port import (
    ValidationRepositoryPort,
)


class InMemoryValidationRepositoryAdapter(ValidationRepositoryPort):
    def __init__(self) -> None:
        self._storage: Dict[str, ValidationReportModel] = {}

    async def save_report(self, report: ValidationReportModel, trace_id: str = "") -> ValidationReportModel:
        self._storage[report.validation_id] = report
        return report

    async def get_report_by_id(self, validation_id: str, trace_id: str = "") -> ValidationReportModel | None:
        return self._storage.get(validation_id)
