"""
Blueprint:
- Priority class load shedding rules.
"""
from src.features.server.pipeline_priority_admission.contracts.pipeline_priority_admission_types import (
    RequestPriorityClass,
)

class PriorityAdmissionRules:
    @staticmethod
    def should_admit(priority_class: RequestPriorityClass, load_ratio: float) -> bool:
        if load_ratio > 0.95:
            return priority_class == RequestPriorityClass.INTERACTIVE
        if load_ratio > 0.80:
            return priority_class in [RequestPriorityClass.INTERACTIVE, RequestPriorityClass.BACKGROUND]
        return True
