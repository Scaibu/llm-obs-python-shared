"""
Blueprint:
- Decision rules for admission_control pipeline step.
"""
from src.features.http.pipeline.admission_control.contracts.admission_control_constants import (
    AdmissionControlConstants,
)

class AdmissionControlRules:
    @staticmethod
    def evaluate_admission(acquired: bool, active_count: int) -> None:
        if not acquired:
            raise RuntimeError(
                AdmissionControlConstants.ERROR_CAPACITY_EXCEEDED.format(active_count=active_count)
            )

