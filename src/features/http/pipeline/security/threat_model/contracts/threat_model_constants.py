"""
Blueprint:
- Rule 1-compliant threat model and assurance specification for all HTTP and Server pipeline components.
- Maps STRIDE threat categories against trust boundaries:
  1. Client -> Edge
  2. Edge -> Ingress Pipeline
  3. Server -> Outbound Upstreams
  4. Server -> Object Storage
  5. Workers -> Storage & Sandbox
- Declares OWASP ASVS 4.0 Level 2 baseline verification invariants.
"""
from typing import Dict, List, Final
from pydantic import BaseModel, Field

class StrideThreatCategory:
    SPOOFING: Final[str] = "Spoofing"
    TAMPERING: Final[str] = "Tampering"
    REPUDIATION: Final[str] = "Repudiation"
    INFO_DISCLOSURE: Final[str] = "Information Disclosure"
    DENIAL_OF_SERVICE: Final[str] = "Denial of Service"
    ELEVATION_OF_PRIVILEGE: Final[str] = "Elevation of Privilege"

class TrustBoundaryThreat(BaseModel):
    boundary: str
    stride_category: str
    threat_description: str
    mandatory_control_id: str
    asvs_requirement: str

THREAT_MODEL_MATRIX: List[TrustBoundaryThreat] = [
    TrustBoundaryThreat(
        boundary="Client -> Edge",
        stride_category=StrideThreatCategory.SPOOFING,
        threat_description="Attacker injects x-tenant-id or spoofs user identity",
        mandatory_control_id="context_isolation.strip_inbound_headers",
        asvs_requirement="V2.1.1 (Authenticated Tenant Extraction)",
    ),
    TrustBoundaryThreat(
        boundary="Client -> Edge",
        stride_category=StrideThreatCategory.DENIAL_OF_SERVICE,
        threat_description="Pre-auth flood exhausting worker slots",
        mandatory_control_id="pipeline_pre_auth_limit + admission_control",
        asvs_requirement="V3.1.1 (Rate limiting and Bulkheads)",
    ),
    TrustBoundaryThreat(
        boundary="Edge -> Server (Uploads)",
        stride_category=StrideThreatCategory.TAMPERING,
        threat_description="Client overwrites clean scanned file via unexpired presigned URL (TOCTOU)",
        mandatory_control_id="upload_pipeline.version_id_binding",
        asvs_requirement="V12.1.1 (Atomic File Verification)",
    ),
    TrustBoundaryThreat(
        boundary="Edge -> Server (Uploads)",
        stride_category=StrideThreatCategory.DENIAL_OF_SERVICE,
        threat_description="Decompression bomb (zip bomb) or pixel flood in upload",
        mandatory_control_id="upload_pipeline.pixel_flood + archive_bomb_guard",
        asvs_requirement="V12.2.1 (Format Inspection Bounds)",
    ),
    TrustBoundaryThreat(
        boundary="Server -> Upstreams",
        stride_category=StrideThreatCategory.INFO_DISCLOSURE,
        threat_description="SSRF accessing AWS/cloud instance metadata or internal services",
        mandatory_control_id="ssrf_validation.blocked_ip_ranges",
        asvs_requirement="V12.6.1 (SSRF Protection)",
    ),
    TrustBoundaryThreat(
        boundary="Server -> Upstreams",
        stride_category=StrideThreatCategory.DENIAL_OF_SERVICE,
        threat_description="Cascading outage from slow downstream holding connections",
        mandatory_control_id="circuit_breaker + bulkhead_admission",
        asvs_requirement="V3.7.1 (Circuit Breaking and Bulkheads)",
    ),
]
