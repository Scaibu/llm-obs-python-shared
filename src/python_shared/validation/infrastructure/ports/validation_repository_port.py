"""
Blueprint:
- Outbound port interface for validation persistence.
- Decouples domain from underlying database, storage or caching implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from python_shared.validation.contracts.validation_types import ValidationReportModel


class ValidationRepositoryPort(ABC):
    @abstractmethod
    async def save_report(self, report: ValidationReportModel, trace_id: str = "") -> ValidationReportModel:
        pass

    @abstractmethod
    async def get_report_by_id(self, validation_id: str, trace_id: str = "") -> ValidationReportModel | None:
        pass
