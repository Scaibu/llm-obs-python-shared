"""
Blueprint:
- Domain service orchestrating request identity and traceparent sanitization.
"""
from src.features.server.pipeline_identity.contracts.pipeline_identity_types import (
    IdentityInputDTO,
    IdentityOutputDTO,
)
from src.features.server.pipeline_identity.domain.rules.pipeline_identity_rules import IdentityRules
from src.features.server.pipeline_identity.infrastructure.ports.pipeline_identity_port import IdentityPort

class PipelineIdentityService:
    def __init__(self, port: IdentityPort):
        self._port = port

    def execute(self, input_dto: IdentityInputDTO) -> IdentityOutputDTO:
        inbound_trace = input_dto.headers.get("traceparent", "")
        if IdentityRules.should_propagate(inbound_trace, input_dto.is_trusted_hop):
            traceparent = inbound_trace
            is_propagated = True
        else:
            traceparent = self._port.generate_traceparent()
            is_propagated = False

        inbound_req_id = input_dto.headers.get("x-request-id")
        request_id = inbound_req_id if inbound_req_id else self._port.generate_request_id()

        return IdentityOutputDTO(
            request_id=request_id,
            traceparent=traceparent,
            is_propagated_trace=is_propagated,
        )
