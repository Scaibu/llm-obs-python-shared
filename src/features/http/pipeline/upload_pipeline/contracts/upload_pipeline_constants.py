"""
Blueprint:
- Canonical constants for the upload pipeline.
- State enumerations, error codes, and format limit constants.
"""
from typing import Final, Set

class UploadPipelineConstants:
    # State Machine States
    STATE_PENDING: Final[str] = "pending"
    STATE_UPLOADED: Final[str] = "uploaded"
    STATE_QUARANTINED: Final[str] = "quarantined"
    STATE_INSPECTING: Final[str] = "inspecting"
    STATE_PROMOTED: Final[str] = "available"
    STATE_REJECTED: Final[str] = "rejected"
    STATE_DELETING: Final[str] = "deleting"
    STATE_DELETED: Final[str] = "deleted"

    # Default limits
    MAX_SESSION_EXPIRY_SECONDS: Final[int] = 900
    MAX_PRESIGN_EXPIRY_SECONDS: Final[int] = 600
    MAX_OPEN_SESSIONS_PER_TENANT: Final[int] = 20
    DEFAULT_MAX_FILENAME_LENGTH: Final[int] = 255
    DEFAULT_PROXIED_MAX_BYTES: Final[int] = 1048576

    # Image constraints (C1 Pixel flood controls)
    IMAGE_MAX_WIDTH: Final[int] = 16384
    IMAGE_MAX_HEIGHT: Final[int] = 16384
    IMAGE_MAX_PIXELS: Final[int] = 100000000
    IMAGE_MAX_FRAMES: Final[int] = 300

    # Archive constraints (C5/C6 Zip slip & bomb controls)
    ARCHIVE_MAX_ENTRIES: Final[int] = 10000
    ARCHIVE_MAX_TOTAL_BYTES: Final[int] = 1073741824 # 1 GB
    ARCHIVE_MAX_DEPTH: Final[int] = 2

    # Magic Bytes (C8 Polyglot / Type validation)
    MAGIC_PNG: Final[bytes] = b"\x89PNG\r\n\x1a\n"
    MAGIC_JPEG: Final[bytes] = b"\xff\xd8\xff"
    MAGIC_GIF: Final[bytes] = b"GIF8"
    MAGIC_WEBP_RIFF: Final[bytes] = b"RIFF"
    MAGIC_WEBP: Final[bytes] = b"WEBP"
    MAGIC_PDF: Final[bytes] = b"%PDF"
    MAGIC_ZIP: Final[bytes] = b"PK\x03\x04"

    # Formula injection prefixes (C10)
    FORMULA_PREFIXES: Final[Set[str]] = {"=", "+", "-", "@", "\t", "\r"}

    # Error messages
    ERROR_SESSION_LIMIT_EXCEEDED: Final[str] = "Tenant '{tenant_id}' exceeded max open upload sessions ({limit})."
    ERROR_QUOTA_EXCEEDED: Final[str] = "Tenant '{tenant_id}' insufficient quota to reserve {bytes} bytes."
    ERROR_INVALID_SESSION_STATE: Final[str] = "Cannot transition upload session from state '{from_state}' to '{to_state}'."
    ERROR_CHECKSUM_MISMATCH: Final[str] = "Uploaded object checksum '{actual}' does not match declared checksum '{expected}'."
    ERROR_SIZE_MISMATCH: Final[str] = "Uploaded object size {actual} bytes does not match declared size {expected} bytes."
    ERROR_OBJECT_NOT_FOUND: Final[str] = "Uploaded object '{key}' not found in quarantine."
    ERROR_MAGIC_BYTE_MISMATCH: Final[str] = "Detected magic bytes do not match declared MIME type '{declared_type}'."
    ERROR_PIXEL_FLOOD: Final[str] = "Image dimensions ({width}x{height}, {pixels} px) exceed safe limit ({max_pixels} px)."
    ERROR_SVG_SCRIPT_DETECTED: Final[str] = "Active script or event handler detected in SVG content."
    ERROR_ZIP_SLIP: Final[str] = "Archive entry path '{entry}' attempts path traversal outside target root."
    ERROR_ZIP_BOMB: Final[str] = "Extracted archive size exceeds safe maximum ({max_bytes} bytes)."
    ERROR_UNAUTHORIZED_DOWNLOAD: Final[str] = "Principal '{principal_id}' not authorized to access object '{object_id}'."
    ERROR_OBJECT_NOT_AVAILABLE: Final[str] = "Object '{object_id}' is in state '{state}', cannot download."
