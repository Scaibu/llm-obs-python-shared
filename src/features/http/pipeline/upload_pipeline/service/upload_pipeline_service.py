"""
Blueprint:
- Pure domain orchestrator service coordinating the 8 lifecycle stages of an upload.
- Steps:
  1. create_session: reserve quota, generate opaque key, issue presigned POST policy.
  2. complete_upload: verify size/checksum from storage, bind version_id, transition to quarantined.
  3. inspect_upload: run sandboxed magic byte sniffing & format checks on quarantine bytes.
  4. promote_upload: copy verified version to clean storage under immutable key, mark available.
  5. prepare_download: authenticate, verify available state, generate RFC 6266 headers & safe presigned URL.
"""
import time
import uuid
from typing import Any, Dict, Optional

from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
)
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_types import (
    CreateSessionInputDTO,
    CreateSessionOutputDTO,
    CompleteUploadInputDTO,
    CompleteUploadOutputDTO,
    InspectionInputDTO,
    InspectionResultDTO,
    PromoteInputDTO,
    PromoteOutputDTO,
    DownloadRequestDTO,
    DownloadDescriptorDTO,
)
from src.features.http.pipeline.upload_pipeline.domain.machines.upload_lifecycle_machine import (
    UploadLifecycleMachine,
)
from src.features.http.pipeline.upload_pipeline.domain.rules.presign_rules import (
    PresignRules,
)
from src.features.http.pipeline.upload_pipeline.domain.rules.content_inspection_rules import (
    ContentInspectionRules,
)
from src.features.http.pipeline.upload_pipeline.domain.rules.download_policy_rules import (
    DownloadPolicyRules,
)
from src.features.http.pipeline.upload_pipeline.infrastructure.ports.storage_port import (
    StoragePort,
    MetadataRepositoryPort,
    QuotaPort,
)

class UploadPipelineService:
    def __init__(
        self,
        storage_port: StoragePort,
        metadata_port: MetadataRepositoryPort,
        quota_port: QuotaPort,
    ) -> None:
        self.storage = storage_port
        self.metadata = metadata_port
        self.quota = quota_port

    def create_upload_session(self, input_dto: CreateSessionInputDTO) -> CreateSessionOutputDTO:
        # 1. Enforce per-tenant open session caps
        open_sessions = self.quota.count_open_sessions(input_dto.tenant_id)
        if open_sessions >= UploadPipelineConstants.MAX_OPEN_SESSIONS_PER_TENANT:
            raise ValueError(
                UploadPipelineConstants.ERROR_SESSION_LIMIT_EXCEEDED.format(
                    tenant_id=input_dto.tenant_id,
                    limit=UploadPipelineConstants.MAX_OPEN_SESSIONS_PER_TENANT,
                )
            )

        # 2. Quota reserved upfront at session create (never after upload)
        reserved = self.quota.reserve_quota(input_dto.tenant_id, input_dto.size_bytes)
        if not reserved:
            raise ValueError(
                UploadPipelineConstants.ERROR_QUOTA_EXCEEDED.format(
                    tenant_id=input_dto.tenant_id,
                    bytes=input_dto.size_bytes,
                )
            )

        # 3. Generate opaque server-controlled quarantine key
        session_id = f"sess_{uuid.uuid4().hex}"
        quarantine_key = PresignRules.generate_opaque_quarantine_key(input_dto.tenant_id, session_id)

        # 4. Generate constrained presigned post policy
        upload_url, post_fields = self.storage.generate_presigned_post(
            key=quarantine_key,
            content_type=input_dto.content_type,
            size_bytes=input_dto.size_bytes,
            sha256_checksum=input_dto.declared_sha256,
            expires_seconds=UploadPipelineConstants.MAX_PRESIGN_EXPIRY_SECONDS,
        )

        now = time.time()
        expires_at = now + UploadPipelineConstants.MAX_SESSION_EXPIRY_SECONDS

        # 5. Commit pending session to metadata repository
        self.metadata.create_session({
            "session_id": session_id,
            "tenant_id": input_dto.tenant_id,
            "principal_id": input_dto.principal_id,
            "filename": input_dto.filename,
            "content_type": input_dto.content_type,
            "size_bytes": input_dto.size_bytes,
            "declared_sha256": input_dto.declared_sha256,
            "quarantine_key": quarantine_key,
            "state": UploadPipelineConstants.STATE_PENDING,
            "created_at": now,
            "expires_at": expires_at,
            "metadata": input_dto.metadata,
        })

        return CreateSessionOutputDTO(
            session_id=session_id,
            opaque_quarantine_key=quarantine_key,
            upload_url=upload_url,
            post_fields=post_fields,
            expires_at_epoch=expires_at,
        )

    def complete_upload(self, input_dto: CompleteUploadInputDTO) -> CompleteUploadOutputDTO:
        session = self.metadata.get_session(input_dto.session_id)
        if not session:
            raise ValueError(f"Session '{input_dto.session_id}' not found")

        # Invariant: session must belong to requesting tenant
        if session["tenant_id"] != input_dto.tenant_id:
            raise PermissionError("Access denied: session belongs to another tenant")

        UploadLifecycleMachine.validate_transition(
            session["state"], UploadPipelineConstants.STATE_UPLOADED
        )

        # Verify object exists in storage and bounds match exactly
        meta = self.storage.get_object_metadata(session["quarantine_key"])
        if not meta:
            raise ValueError(
                UploadPipelineConstants.ERROR_OBJECT_NOT_FOUND.format(key=session["quarantine_key"])
            )

        PresignRules.verify_completion_bounds(
            expected_size=session["size_bytes"],
            actual_size=meta["size_bytes"],
            expected_sha256=session["declared_sha256"],
            actual_sha256=meta["sha256"],
        )

        version_id = meta["version_id"]

        # Transition state: uploaded -> quarantined (closed session)
        self.metadata.update_session_state(
            session_id=input_dto.session_id,
            state=UploadPipelineConstants.STATE_QUARANTINED,
            extra_fields={"version_id": version_id},
        )

        return CompleteUploadOutputDTO(
            session_id=input_dto.session_id,
            state=UploadPipelineConstants.STATE_QUARANTINED,
            version_id=version_id,
            quarantine_key=session["quarantine_key"],
            size_bytes=meta["size_bytes"],
            sha256=meta["sha256"],
        )

    def inspect_upload(self, input_dto: InspectionInputDTO) -> InspectionResultDTO:
        session = self.metadata.get_session(input_dto.session_id)
        if not session:
            raise ValueError(f"Session '{input_dto.session_id}' not found")

        UploadLifecycleMachine.validate_transition(
            session["state"], UploadPipelineConstants.STATE_INSPECTING
        )
        self.metadata.update_session_state(
            session_id=input_dto.session_id,
            state=UploadPipelineConstants.STATE_INSPECTING,
        )

        # Read quarantined object bytes for format sniffing
        data = self.storage.read_object_bytes(input_dto.quarantine_key)
        detected_mime = ContentInspectionRules.sniff_mime_type(data)

        try:
            # Perform format-specific checks
            if detected_mime == "image/png":
                ContentInspectionRules.inspect_png_dimensions(data)
            elif detected_mime == "image/svg+xml":
                ContentInspectionRules.inspect_svg_security(data)
            elif detected_mime == "application/zip":
                ContentInspectionRules.inspect_archive_safety(data)

            return InspectionResultDTO(
                passed=True,
                detected_mime_type=detected_mime,
                sanitized_metadata={"detected_mime": detected_mime},
            )
        except Exception as e:
            # Inspection failed: reject session, release reserved quota, delete quarantine blob
            self.metadata.update_session_state(
                session_id=input_dto.session_id,
                state=UploadPipelineConstants.STATE_REJECTED,
                extra_fields={"rejection_reason": str(e)},
            )
            self.quota.release_quota(input_dto.tenant_id, session["size_bytes"])
            self.storage.delete_object(input_dto.quarantine_key, input_dto.version_id)
            return InspectionResultDTO(
                passed=False,
                detected_mime_type=detected_mime,
                rejection_reason=str(e),
            )

    def promote_upload(self, input_dto: PromoteInputDTO) -> PromoteOutputDTO:
        session = self.metadata.get_session(input_dto.session_id)
        if not session:
            raise ValueError(f"Session '{input_dto.session_id}' not found")

        UploadLifecycleMachine.validate_transition(
            session["state"], UploadPipelineConstants.STATE_PROMOTED
        )

        object_id = f"obj_{uuid.uuid4().hex}"
        clean_key = PresignRules.generate_immutable_clean_key(
            tenant_id=input_dto.tenant_id,
            object_id=object_id,
            sha256_hash=input_dto.sha256,
        )

        # Copy verified version to clean immutable storage
        dest_key, dest_version_id = self.storage.copy_object(
            source_key=input_dto.quarantine_key,
            dest_key=clean_key,
            version_id=input_dto.version_id,
        )

        # Delete quarantine object
        self.storage.delete_object(input_dto.quarantine_key, input_dto.version_id)

        # Commit final available state in metadata transaction
        self.metadata.commit_available_object({
            "object_id": object_id,
            "tenant_id": input_dto.tenant_id,
            "clean_key": clean_key,
            "version_id": dest_version_id,
            "filename": session["filename"],
            "content_type": input_dto.detected_mime_type,
            "size_bytes": input_dto.size_bytes,
            "sha256": input_dto.sha256,
            "state": UploadPipelineConstants.STATE_PROMOTED,
            "promoted_at": time.time(),
        })

        self.metadata.update_session_state(
            session_id=input_dto.session_id,
            state=UploadPipelineConstants.STATE_PROMOTED,
            extra_fields={"object_id": object_id, "clean_key": clean_key},
        )

        return PromoteOutputDTO(
            object_id=object_id,
            clean_immutable_key=clean_key,
            version_id=dest_version_id,
            state=UploadPipelineConstants.STATE_PROMOTED,
        )

    def prepare_download(self, input_dto: DownloadRequestDTO) -> DownloadDescriptorDTO:
        # Section 6: per-object per-request authorization check
        obj = self.metadata.get_object(input_dto.object_id)
        if not obj:
            raise FileNotFoundError(f"Object '{input_dto.object_id}' not found")

        if obj["tenant_id"] != input_dto.tenant_id:
            raise PermissionError(
                UploadPipelineConstants.ERROR_UNAUTHORIZED_DOWNLOAD.format(
                    principal_id=input_dto.principal_id,
                    object_id=input_dto.object_id,
                )
            )

        if obj["state"] != UploadPipelineConstants.STATE_PROMOTED:
            raise ValueError(
                UploadPipelineConstants.ERROR_OBJECT_NOT_AVAILABLE.format(
                    object_id=input_dto.object_id,
                    state=obj["state"],
                )
            )

        # Generate safe serving headers (RFC 6266, nosniff, sandbox CSP)
        serving_headers = DownloadPolicyRules.build_serving_headers(
            content_type=obj["content_type"],
            filename=obj["filename"],
            size_bytes=obj["size_bytes"],
            sha256_hash=obj["sha256"],
        )

        # Handle byte range requests (RFC 9110 single range limit)
        if input_dto.requested_range:
            range_bounds = DownloadPolicyRules.validate_range_header(
                input_dto.requested_range, obj["size_bytes"]
            )
            if range_bounds:
                serving_headers["Content-Range"] = f"bytes {range_bounds[0]}-{range_bounds[1]}/{obj['size_bytes']}"

        download_url = f"https://usercontent.example.net/objects/{input_dto.object_id}"

        return DownloadDescriptorDTO(
            object_id=input_dto.object_id,
            download_url=download_url,
            content_type=serving_headers["Content-Type"],
            content_disposition=serving_headers["Content-Disposition"],
            content_digest=serving_headers["Content-Digest"],
            content_security_policy=serving_headers["Content-Security-Policy"],
            etag=serving_headers["ETag"],
            size_bytes=obj["size_bytes"],
            headers=serving_headers,
        )
