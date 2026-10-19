"""
Blueprint:
- Service managing authenticated tenant quota consumption.
"""
from src.features.server.pipeline_tenant_quota.contracts.pipeline_tenant_quota_types import (
    TenantQuotaInputDTO,
    TenantQuotaOutputDTO,
)
from src.features.server.pipeline_tenant_quota.infrastructure.ports.pipeline_tenant_quota_port import TenantQuotaPort

class PipelineTenantQuotaService:
    def __init__(self, quota_port: TenantQuotaPort):
        self._port = quota_port

    @property
    def quota_port(self) -> TenantQuotaPort:
        return self._port

    def execute(self, input_dto: TenantQuotaInputDTO) -> TenantQuotaOutputDTO:
        allowed = self._port.consume_tenant_quota(
            tenant_id=input_dto.tenant_id,
            tokens=input_dto.tokens,
            refill_rate=input_dto.refill_rate,
        )
        if not allowed:
            return TenantQuotaOutputDTO(allowed=False, status_code=429, retry_after_seconds=3)
        return TenantQuotaOutputDTO(allowed=True, status_code=200, retry_after_seconds=0)
