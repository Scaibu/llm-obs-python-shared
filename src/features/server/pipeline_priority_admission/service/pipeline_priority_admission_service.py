"""
Blueprint:
- Domain service executing priority-based admission control.
"""
from src.features.server.pipeline_priority_admission.contracts.pipeline_priority_admission_types import (
    PriorityAdmissionInputDTO,
    PriorityAdmissionOutputDTO,
)
from src.features.server.pipeline_priority_admission.domain.rules.pipeline_priority_admission_rules import (
    PriorityAdmissionRules,
)

class PipelinePriorityAdmissionService:
    def execute(self, input_dto: PriorityAdmissionInputDTO) -> PriorityAdmissionOutputDTO:
        admitted = PriorityAdmissionRules.should_admit(
            input_dto.priority_class,
            input_dto.system_load_ratio,
        )
        if not admitted:
            return PriorityAdmissionOutputDTO(admitted=False, status_code=503, retry_after_seconds=5)
        return PriorityAdmissionOutputDTO(admitted=True, status_code=200, retry_after_seconds=0)
