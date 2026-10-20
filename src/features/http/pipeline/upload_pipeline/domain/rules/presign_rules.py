"""
Blueprint:
- Pure business rules for presigned post policies, opaque key generation, and upload constraints.
- Addresses Section 3 Risks: U1 TOCTOU, U2 Size bounds, U3 Content-Type pinning, U5 Key injection.
"""
import uuid
from typing import Dict, Tuple
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
)

class PresignRules:
    @staticmethod
    def generate_opaque_quarantine_key(tenant_id: str, session_id: str) -> str:
        # U5 Key Injection Control: Server generated path only; no client path components allowed
        safe_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_"))
        return f"quarantine/{safe_tenant}/{session_id}"

    @staticmethod
    def generate_immutable_clean_key(tenant_id: str, object_id: str, sha256_hash: str) -> str:
        safe_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_"))
        return f"clean/{safe_tenant}/{object_id}/{sha256_hash}"

    @staticmethod
    def build_post_policy_conditions(
        opaque_key: str,
        content_type: str,
        size_bytes: int,
        sha256_checksum: str,
    ) -> Dict[str, str]:
        # U2 & U3: Enforce exact key, exact content-type, content-length-range, and sha256 header
        return {
            "key": opaque_key,
            "Content-Type": content_type,
            "x-amz-checksum-sha256": sha256_checksum,
            "content-length-range": f"{size_bytes},{size_bytes}",
        }

    @staticmethod
    def verify_completion_bounds(
        expected_size: int,
        actual_size: int,
        expected_sha256: str,
        actual_sha256: str,
    ) -> None:
        if actual_size != expected_size:
            raise ValueError(
                UploadPipelineConstants.ERROR_SIZE_MISMATCH.format(
                    actual=actual_size,
                    expected=expected_size,
                )
            )
        if actual_sha256.lower() != expected_sha256.lower():
            raise ValueError(
                UploadPipelineConstants.ERROR_CHECKSUM_MISMATCH.format(
                    actual=actual_sha256,
                    expected=expected_sha256,
                )
            )
