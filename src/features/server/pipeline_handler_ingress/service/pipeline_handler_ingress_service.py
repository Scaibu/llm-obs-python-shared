"""
Blueprint:
- Domain service executing Stage 12 ingress dispatch.
"""
from src.features.server.pipeline_handler_ingress.contracts.pipeline_handler_ingress_types import (
    HandlerIngressInputDTO,
    HandlerIngressOutputDTO,
)
from src.features.server.pipeline_handler_ingress.domain.rules.pipeline_handler_ingress_rules import HandlerIngressRules
from src.features.server.pipeline_handler_ingress.infrastructure.ports.pipeline_handler_ingress_port import DomainDispatcherPort

class PipelineHandlerIngressService:
    def __init__(self, dispatcher: DomainDispatcherPort):
        self._dispatcher = dispatcher

    async def execute(self, input_dto: HandlerIngressInputDTO) -> HandlerIngressOutputDTO:
        send_continue = HandlerIngressRules.expects_continue(input_dto.headers)
        result = await self._dispatcher.dispatch(input_dto.target_handler, input_dto.body)
        return HandlerIngressOutputDTO(
            dispatched=True,
            status_code=200,
            sent_continue=send_continue,
            response_body=result,
        )
