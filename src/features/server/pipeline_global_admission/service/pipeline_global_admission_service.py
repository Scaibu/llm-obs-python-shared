"""
Blueprint:
- Service managing global concurrency admission control.
"""
from src.features.server.pipeline_global_admission.contracts.pipeline_global_admission_types import (
    AdmissionInputDTO,
    AdmissionOutputDTO,
)
from src.features.server.pipeline_global_admission.domain.rules.pipeline_global_admission_rules import GlobalAdmissionRules
from src.features.server.pipeline_global_admission.infrastructure.ports.pipeline_global_admission_port import AdmissionTrackerPort

class PipelineGlobalAdmissionService:
    def __init__(self, tracker: AdmissionTrackerPort):
        self._tracker = tracker

    def execute(self, input_dto: AdmissionInputDTO) -> AdmissionOutputDTO:
        current = self._tracker.get_in_flight()
        if not GlobalAdmissionRules.should_admit(current, input_dto.max_concurrency):
            return AdmissionOutputDTO(allowed=False, current_inflight=current, retry_after_seconds=5)
        self._tracker.increment()
        return AdmissionOutputDTO(allowed=True, current_inflight=current + 1, retry_after_seconds=0)

    @property
    def tracker(self) -> AdmissionTrackerPort:
        return self._tracker

    def release(self) -> None:
        self._tracker.decrement()
