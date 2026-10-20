"""
Blueprint:
- Pure domain data transfer objects (DTOs) for upload and download lifecycle.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class CreateSessionInputDTO:
    tenant_id: str
    principal_id: str
    filename: str
    content_type: str
    size_bytes: int
    declared_sha256: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CreateSessionOutputDTO:
    session_id: str
    opaque_quarantine_key: str
    upload_url: str
    post_fields: Dict[str, str]
    expires_at_epoch: float

@dataclass(frozen=True)
class CompleteUploadInputDTO:
    session_id: str
    tenant_id: str
    principal_id: str

@dataclass(frozen=True)
class CompleteUploadOutputDTO:
    session_id: str
    state: str
    version_id: str
    quarantine_key: str
    size_bytes: int
    sha256: str

@dataclass(frozen=True)
class InspectionInputDTO:
    session_id: str
    tenant_id: str
    quarantine_key: str
    version_id: str
    expected_sha256: str
    declared_content_type: str

@dataclass(frozen=True)
class InspectionResultDTO:
    passed: bool
    detected_mime_type: str
    rejection_reason: Optional[str] = None
    sanitized_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PromoteInputDTO:
    session_id: str
    tenant_id: str
    quarantine_key: str
    version_id: str
    detected_mime_type: str
    sha256: str
    size_bytes: int

@dataclass(frozen=True)
class PromoteOutputDTO:
    object_id: str
    clean_immutable_key: str
    version_id: str
    state: str

@dataclass(frozen=True)
class DownloadRequestDTO:
    object_id: str
    tenant_id: str
    principal_id: str
    requested_range: Optional[str] = None

@dataclass(frozen=True)
class DownloadDescriptorDTO:
    object_id: str
    download_url: str
    content_type: str
    content_disposition: str
    content_digest: str
    content_security_policy: str
    etag: str
    size_bytes: int
    headers: Dict[str, str]
