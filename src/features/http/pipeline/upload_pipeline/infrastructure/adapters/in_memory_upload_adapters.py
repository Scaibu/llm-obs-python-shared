"""
Blueprint:
- In-memory adapters implementing StoragePort, MetadataRepositoryPort, and QuotaPort.
- Supports local development, unit tests, and CI without requiring real S3 or SQL dependencies.
"""
import hashlib
import time
import uuid
from typing import Any, Dict, Optional, Tuple
from src.features.http.pipeline.upload_pipeline.infrastructure.ports.storage_port import (
    StoragePort,
    MetadataRepositoryPort,
    QuotaPort,
)

class InMemoryStorageAdapter(StoragePort):
    def __init__(self) -> None:
        # storage format: key -> list of versions [{"version_id": str, "data": bytes, "metadata": dict}]
        self.store: Dict[str, list] = {}

    def simulate_client_upload(self, key: str, data: bytes) -> str:
        version_id = f"v-{uuid.uuid4().hex[:8]}"
        sha = hashlib.sha256(data).hexdigest()
        entry = {
            "version_id": version_id,
            "data": data,
            "size_bytes": len(data),
            "sha256": sha,
            "created_at": time.time(),
        }
        if key not in self.store:
            self.store[key] = []
        self.store[key].append(entry)
        return version_id

    def generate_presigned_post(
        self,
        key: str,
        content_type: str,
        size_bytes: int,
        sha256_checksum: str,
        expires_seconds: int = 600,
    ) -> Tuple[str, Dict[str, str]]:
        upload_url = "https://storage.internal.net/uploads"
        fields = {
            "key": key,
            "Content-Type": content_type,
            "x-amz-checksum-sha256": sha256_checksum,
            "content-length-range": f"{size_bytes},{size_bytes}",
            "policy": "mock-b64-policy",
            "x-amz-signature": "mock-signature",
        }
        return upload_url, fields

    def get_object_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        versions = self.store.get(key)
        if not versions:
            return None
        latest = versions[-1]
        return {
            "key": key,
            "version_id": latest["version_id"],
            "size_bytes": latest["size_bytes"],
            "sha256": latest["sha256"],
        }

    def read_object_bytes(self, key: str, max_bytes: Optional[int] = None) -> bytes:
        versions = self.store.get(key)
        if not versions:
            raise FileNotFoundError(f"Key '{key}' not found in storage")
        data = versions[-1]["data"]
        return data[:max_bytes] if max_bytes else data

    def copy_object(
        self,
        source_key: str,
        dest_key: str,
        version_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        versions = self.store.get(source_key)
        if not versions:
            raise FileNotFoundError(f"Source '{source_key}' not found")
        matched = None
        if version_id:
            for v in versions:
                if v["version_id"] == version_id:
                    matched = v
                    break
        else:
            matched = versions[-1]
        if not matched:
            raise FileNotFoundError(f"Source version '{version_id}' not found")

        dest_version_id = f"v-{uuid.uuid4().hex[:8]}"
        dest_entry = {
            "version_id": dest_version_id,
            "data": matched["data"],
            "size_bytes": matched["size_bytes"],
            "sha256": matched["sha256"],
            "created_at": time.time(),
        }
        if dest_key not in self.store:
            self.store[dest_key] = []
        self.store[dest_key].append(dest_entry)
        return dest_key, dest_version_id

    def delete_object(self, key: str, version_id: Optional[str] = None) -> None:
        if key in self.store:
            if version_id:
                self.store[key] = [v for v in self.store[key] if v["version_id"] != version_id]
            else:
                del self.store[key]

class InMemoryMetadataAdapter(MetadataRepositoryPort):
    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.objects: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_data: Dict[str, Any]) -> None:
        self.sessions[session_data["session_id"]] = dict(session_data)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def update_session_state(
        self,
        session_id: str,
        state: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["state"] = state
            if extra_fields:
                self.sessions[session_id].update(extra_fields)

    def commit_available_object(self, object_metadata: Dict[str, Any]) -> None:
        self.objects[object_metadata["object_id"]] = dict(object_metadata)

    def get_object(self, object_id: str) -> Optional[Dict[str, Any]]:
        return self.objects.get(object_id)

class InMemoryQuotaAdapter(QuotaPort):
    def __init__(self, tenant_quota_bytes: int = 10 * 1024 * 1024 * 1024) -> None:
        self.default_quota = tenant_quota_bytes
        self.used_quota: Dict[str, int] = {}
        self.open_sessions: Dict[str, int] = {}

    def reserve_quota(self, tenant_id: str, size_bytes: int) -> bool:
        current_used = self.used_quota.get(tenant_id, 0)
        if current_used + size_bytes > self.default_quota:
            return False
        self.used_quota[tenant_id] = current_used + size_bytes
        self.open_sessions[tenant_id] = self.open_sessions.get(tenant_id, 0) + 1
        return True

    def release_quota(self, tenant_id: str, size_bytes: int) -> None:
        current_used = self.used_quota.get(tenant_id, 0)
        self.used_quota[tenant_id] = max(0, current_used - size_bytes)
        current_sessions = self.open_sessions.get(tenant_id, 0)
        self.open_sessions[tenant_id] = max(0, current_sessions - 1)

    def count_open_sessions(self, tenant_id: str) -> int:
        return self.open_sessions.get(tenant_id, 0)
