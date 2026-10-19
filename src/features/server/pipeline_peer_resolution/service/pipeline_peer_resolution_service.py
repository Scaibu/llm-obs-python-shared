"""
Blueprint:
- Domain service resolving peer IP using right-to-left traversal.
"""
from src.features.server.pipeline_peer_resolution.contracts.pipeline_peer_resolution_types import (
    PeerResolutionInputDTO,
    PeerResolutionOutputDTO,
)
from src.features.server.pipeline_peer_resolution.domain.rules.pipeline_peer_resolution_rules import PeerResolutionRules
from src.features.server.pipeline_peer_resolution.infrastructure.ports.pipeline_peer_resolution_port import PeerConfigPort

class PipelinePeerResolutionService:
    def __init__(self, config_port: PeerConfigPort):
        self._port = config_port

    def execute(self, input_dto: PeerResolutionInputDTO) -> PeerResolutionOutputDTO:
        trusted = input_dto.trusted_proxies or self._port.get_trusted_proxies()
        client_ip = PeerResolutionRules.resolve_client_ip(
            remote_addr=input_dto.remote_addr,
            x_forwarded_for=input_dto.x_forwarded_for or "",
            trusted_proxies=trusted,
        )
        return PeerResolutionOutputDTO(
            client_ip=client_ip,
            is_proxied=bool(input_dto.x_forwarded_for),
        )
