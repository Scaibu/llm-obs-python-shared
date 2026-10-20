"""
Blueprint:
- Constants contract for admission_control pipeline step.
"""
from typing import Final

class AdmissionControlConstants:
    STEP_NAME: Final[str] = "AdmissionControl"
    STEP_DESCRIPTION: Final[str] = "Concurrency Admission Control & Fleet Capacity Guard"
    ERROR_CAPACITY_EXCEEDED: Final[str] = (
        "Too Many Requests - Fleet In-Flight Concurrency Capacity ({active_count}) Exceeded"
    )
