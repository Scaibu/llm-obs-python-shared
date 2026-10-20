"""
Blueprint:
- Pure domain orchestrator service for admission_control pipeline step.
"""
from src.features.http.pipeline.admission_control.contracts.admission_control_types import (
    AdmissionControlInputDTO,
    AdmissionControlOutputDTO,
)
from src.features.http.pipeline.admission_control.domain.rules.admission_control_rules import (
    AdmissionControlRules,
)
from src.features.http.pipeline.admission_control.infrastructure.ports.admission_control_port import (
    ConcurrencyAdmissionControlPort,
)

class AdmissionControlService:
    def __init__(self, port: ConcurrencyAdmissionControlPort) -> None:
        self._port = port

    def execute(self, _input_dto: AdmissionControlInputDTO | None = None) -> AdmissionControlOutputDTO:
        acquired = self._port.acquire()
        active_count = self._port.get_active_count()
        AdmissionControlRules.evaluate_admission(acquired, active_count)
        return AdmissionControlOutputDTO(admitted=True, active_count=active_count)
