"""
Blueprint:
- Schema validation and ACL for admission_control pipeline step.
"""
from src.features.http.pipeline.admission_control.contracts.admission_control_types import (
    AdmissionControlInputDTO,
    AdmissionControlOutputDTO,
)

class AdmissionControlSchema:
    @staticmethod
    def validate_input() -> AdmissionControlInputDTO:
        return AdmissionControlInputDTO()

    @staticmethod
    def to_output(admitted: bool, active_count: int) -> AdmissionControlOutputDTO:
        return AdmissionControlOutputDTO(admitted=admitted, active_count=active_count)
