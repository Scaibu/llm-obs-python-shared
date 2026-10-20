"""
Blueprint:
- Abstract hexagonal outbound port definitions for storage, metadata, and quota.
"""
from typing import Any, Dict, Optional, Protocol, Tuple

class StoragePort(Protocol):
    def generate_presigned_post(
        self,
        key: str,
        content_type: str,
        size_bytes: int,
        sha256_checksum: str,
        expires_seconds: int = 600,
    ) -> Tuple[str, Dict[str, str]]: ...

    def get_object_metadata(self, key: str) -> Optional[Dict[str, Any]]: ...

    def read_object_bytes(self, key: str, max_bytes: Optional[int] = None) -> bytes: ...

    def copy_object(
        self,
        source_key: str,
        dest_key: str,
        version_id: Optional[str] = None,
    ) -> Tuple[str, str]: ... # returns (dest_key, version_id)

    def delete_object(self, key: str, version_id: Optional[str] = None) -> None: ...

class MetadataRepositoryPort(Protocol):
    def create_session(self, session_data: Dict[str, Any]) -> None: ...

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]: ...

    def update_session_state(
        self,
        session_id: str,
        state: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None: ...

    def commit_available_object(self, object_metadata: Dict[str, Any]) -> None: ...

    def get_object(self, object_id: str) -> Optional[Dict[str, Any]]: ...

class QuotaPort(Protocol):
    def reserve_quota(self, tenant_id: str, size_bytes: int) -> bool: ...

    def release_quota(self, tenant_id: str, size_bytes: int) -> None: ...

    def count_open_sessions(self, tenant_id: str) -> int: ...
