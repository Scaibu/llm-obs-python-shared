"""
Blueprint:
- Schema validation and ACL for ssrf_validation pipeline step.
"""
from typing import List, Optional
from src.features.http.pipeline.ssrf_validation.contracts.ssrf_validation_types import (
    SsrfValidationInputDTO,
    SsrfValidationOutputDTO,
)

class SsrfValidationSchema:
    @staticmethod
    def validate_input(url: str, allowed_hosts: Optional[List[str]]) -> SsrfValidationInputDTO:
        return SsrfValidationInputDTO(url=url, allowed_hosts=allowed_hosts)

    @staticmethod
    def to_output(valid: bool, hostname: Optional[str]) -> SsrfValidationOutputDTO:
        return SsrfValidationOutputDTO(valid=valid, hostname=hostname)
