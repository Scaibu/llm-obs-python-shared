"""
Blueprint:
- Public facade for admission_control pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.admission_control.contracts.admission_control_constants import (
    AdmissionControlConstants,
)
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
from src.features.http.pipeline.admission_control.infrastructure.adapters.admission_control_adapter import (
    ConcurrencyAdmissionControlAdapter,
)
from src.features.http.pipeline.admission_control.service.admission_control_service import (
    AdmissionControlService,
)

class StepAdmissionControl:
    name: str = AdmissionControlConstants.STEP_NAME
    description: str = AdmissionControlConstants.STEP_DESCRIPTION


    def __init__(self, service: AdmissionControlService | None = None) -> None:
        self._service = service

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        service = self._service or AdmissionControlService(
            ConcurrencyAdmissionControlAdapter(ctx.admission_control)
        )
        service.execute()

__all__ = [
    "AdmissionControlInputDTO",
    "AdmissionControlOutputDTO",
    "AdmissionControlRules",
    "ConcurrencyAdmissionControlPort",
    "ConcurrencyAdmissionControlAdapter",
    "AdmissionControlService",
    "StepAdmissionControl",
]
