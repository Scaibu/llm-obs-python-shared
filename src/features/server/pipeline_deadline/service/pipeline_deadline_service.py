"""
Blueprint:
- Domain service computing deadline budget and performing fail-fast validation.
"""
from src.features.server.pipeline_deadline.contracts.pipeline_deadline_types import (
    DeadlineInputDTO,
    DeadlineOutputDTO,
)
from src.features.server.pipeline_deadline.domain.rules.pipeline_deadline_rules import DeadlineRules

class PipelineDeadlineService:
    def execute(self, input_dto: DeadlineInputDTO) -> DeadlineOutputDTO:
        budget = DeadlineRules.calculate_budget(
            client_timeout_ms=input_dto.client_timeout_ms,
            route_min_ms=input_dto.route_min_ms,
            route_max_ms=input_dto.route_max_ms,
            safety_margin_ms=input_dto.safety_margin_ms,
        )
        if not DeadlineRules.is_viable(budget, input_dto.route_min_ms):
            return DeadlineOutputDTO(valid=False, status_code=504, allocated_budget_ms=budget)
        return DeadlineOutputDTO(valid=True, status_code=200, allocated_budget_ms=budget)
