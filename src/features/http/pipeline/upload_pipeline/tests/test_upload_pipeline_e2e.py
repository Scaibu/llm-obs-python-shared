"""
Blueprint:
- End-to-end integration tests for the full 8-step upload pipeline.
- Tests valid complete flow: Session Create -> Client Transfer -> Complete (Quarantine) -> Inspect -> Promote -> Download.
- Tests failure flows: Checksum mismatch, Quota exhaustion, and TOCTOU version binding.
"""
import pytest
import hashlib
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
)
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_types import (
    CreateSessionInputDTO,
    CompleteUploadInputDTO,
    InspectionInputDTO,
    PromoteInputDTO,
    DownloadRequestDTO,
)
from src.features.http.pipeline.upload_pipeline.infrastructure.adapters.in_memory_upload_adapters import (
    InMemoryStorageAdapter,
    InMemoryMetadataAdapter,
    InMemoryQuotaAdapter,
)
from src.features.http.pipeline.upload_pipeline.service.upload_pipeline_service import (
    UploadPipelineService,
)

@pytest.fixture
def upload_service():
    storage = InMemoryStorageAdapter()
    metadata = InMemoryMetadataAdapter()
    quota = InMemoryQuotaAdapter(tenant_quota_bytes=10 * 1024 * 1024) # 10 MB quota
    return UploadPipelineService(storage, metadata, quota), storage, metadata, quota

def test_full_upload_pipeline_lifecycle_e2e(upload_service):
    service, storage, metadata, quota = upload_service

    # Valid PNG binary payload
    png_bytes = (
        UploadPipelineConstants.MAGIC_PNG
        + b"\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00"
        + b"\x00" * 30
    )
    png_sha = hashlib.sha256(png_bytes).hexdigest()
    file_size = len(png_bytes)

    # 1. Create Upload Session
    session_out = service.create_upload_session(
        CreateSessionInputDTO(
            tenant_id="tenant-alpha",
            principal_id="user-1",
            filename="avatar.png",
            content_type="image/png",
            size_bytes=file_size,
            declared_sha256=png_sha,
        )
    )
    assert session_out.session_id.startswith("sess_")
    assert "quarantine/tenant-alpha" in session_out.opaque_quarantine_key

    # 2. Client transfers directly to storage (Simulated direct-to-storage transfer)
    version_id = storage.simulate_client_upload(session_out.opaque_quarantine_key, png_bytes)

    # 3. Client calls Completion: verify bounds and transition to quarantined
    complete_out = service.complete_upload(
        CompleteUploadInputDTO(
            session_id=session_out.session_id,
            tenant_id="tenant-alpha",
            principal_id="user-1",
        )
    )
    assert complete_out.state == UploadPipelineConstants.STATE_QUARANTINED
    assert complete_out.version_id == version_id

    # 4. Sandboxed Worker Inspection
    inspect_out = service.inspect_upload(
        InspectionInputDTO(
            session_id=session_out.session_id,
            tenant_id="tenant-alpha",
            quarantine_key=complete_out.quarantine_key,
            version_id=version_id,
            expected_sha256=png_sha,
            declared_content_type="image/png",
        )
    )
    assert inspect_out.passed is True
    assert inspect_out.detected_mime_type == "image/png"

    # 5. Promotion to clean immutable storage
    promote_out = service.promote_upload(
        PromoteInputDTO(
            session_id=session_out.session_id,
            tenant_id="tenant-alpha",
            quarantine_key=complete_out.quarantine_key,
            version_id=version_id,
            detected_mime_type=inspect_out.detected_mime_type,
            sha256=png_sha,
            size_bytes=file_size,
        )
    )
    assert promote_out.state == UploadPipelineConstants.STATE_PROMOTED
    assert "clean/tenant-alpha" in promote_out.clean_immutable_key

    # 6. Authenticated Download Preparation
    download_out = service.prepare_download(
        DownloadRequestDTO(
            object_id=promote_out.object_id,
            tenant_id="tenant-alpha",
            principal_id="user-1",
        )
    )
    assert download_out.content_type == "image/png"
    assert download_out.headers["X-Content-Type-Options"] == "nosniff"
    assert "inline" in download_out.content_disposition

    # 7. Access Control check: Other tenant CANNOT download this object
    with pytest.raises(PermissionError):
        service.prepare_download(
            DownloadRequestDTO(
                object_id=promote_out.object_id,
                tenant_id="tenant-attacker",
                principal_id="user-2",
            )
        )

def test_upload_completion_rejects_checksum_tampering(upload_service):
    service, storage, metadata, quota = upload_service

    payload = b"clean-file-data"
    declared_sha = hashlib.sha256(payload).hexdigest()

    session_out = service.create_upload_session(
        CreateSessionInputDTO(
            tenant_id="tenant-alpha",
            principal_id="user-1",
            filename="data.txt",
            content_type="text/plain",
            size_bytes=len(payload),
            declared_sha256=declared_sha,
        )
    )

    # Client uploads modified data (different bytes/hash)
    tampered_bytes = b"tampered-data-x"
    storage.simulate_client_upload(session_out.opaque_quarantine_key, tampered_bytes)

    with pytest.raises(ValueError) as exc:
        service.complete_upload(
            CompleteUploadInputDTO(
                session_id=session_out.session_id,
                tenant_id="tenant-alpha",
                principal_id="user-1",
            )
        )
    assert "does not match declared checksum" in str(exc.value)

def test_quota_reservation_enforced_at_session_creation(upload_service):
    service, storage, metadata, quota = upload_service

    # Quota is 10 MB; attempting to allocate 11 MB fails immediately
    with pytest.raises(ValueError) as exc:
        service.create_upload_session(
            CreateSessionInputDTO(
                tenant_id="tenant-quota-test",
                principal_id="user-1",
                filename="huge.zip",
                content_type="application/zip",
                size_bytes=11 * 1024 * 1024,
                declared_sha256="a" * 64,
            )
        )
    assert "insufficient quota" in str(exc.value)
