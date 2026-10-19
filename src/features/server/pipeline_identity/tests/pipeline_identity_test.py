"""
Blueprint:
- Unit test suite for pipeline_identity rules, service, and adapters.
"""
from src.features.server.pipeline_identity.contracts.pipeline_identity_types import IdentityInputDTO
from src.features.server.pipeline_identity.infrastructure.adapters.pipeline_identity_adapter import (
    StandardIdentityAdapter,
)
from src.features.server.pipeline_identity.service.pipeline_identity_service import (
    PipelineIdentityService,
)
from src.features.server.pipeline_identity.domain.rules.pipeline_identity_rules import IdentityRules

def test_traceparent_validation() -> None:
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert IdentityRules.is_valid_traceparent(valid) is True
    assert IdentityRules.is_valid_traceparent("invalid-trace") is False

def test_service_generates_identity() -> None:
    adapter = StandardIdentityAdapter()
    service = PipelineIdentityService(port=adapter)
    res = service.execute(IdentityInputDTO(headers={}, is_trusted_hop=False))
    assert res.request_id is not None
    assert res.traceparent.startswith("00-")
    assert res.is_propagated_trace is False
