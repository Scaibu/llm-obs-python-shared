"""
Blueprint:
- Anti-Corruption Layer (ACL) and Pydantic validation schemas for API inputs and outputs.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator
import unicodedata
import re

class CreateSessionSchema(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=128)
    size_bytes: int = Field(..., gt=0)
    declared_sha256: str = Field(..., min_length=64, max_length=64)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        # C7: Normalize Unicode (NFC), strip bidi control characters & nulls
        normalized = unicodedata.normalize("NFC", v)
        # Strip bidi overrides (U+202A to U+202E, U+2066 to U+2069)
        cleaned = re.sub(r"[\u202A-\u202E\u2066-\u2069\x00]", "", normalized)
        # Remove any path traversal components
        base = cleaned.replace("\\", "/").split("/")[-1]
        if not base.strip():
            raise ValueError("Invalid filename after sanitization")
        return base

    @field_validator("declared_sha256")
    @classmethod
    def validate_hash_format(cls, v: str) -> str:
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("declared_sha256 must be a valid 64-character hex string")
        return v.lower()

class CompleteUploadSchema(BaseModel):
    session_id: str = Field(..., min_length=8)

class DownloadRequestSchema(BaseModel):
    object_id: str = Field(..., min_length=8)
    range_header: Optional[str] = Field(default=None)
