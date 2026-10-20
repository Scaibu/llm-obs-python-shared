"""
Blueprint:
- Pure business rules for safe downloads, headers generation, and origin isolation (Section 6).
"""
from typing import Dict, List, Optional
import urllib.parse

class DownloadPolicyRules:
    INLINE_SAFE_MIMES: List[str] = [
        "image/png",
        "image/jpeg",
        "image/webp",
        "application/pdf",
    ]

    @staticmethod
    def build_serving_headers(
        content_type: str,
        filename: str,
        size_bytes: int,
        sha256_hash: str,
        force_attachment: bool = False,
    ) -> Dict[str, str]:
        # RFC 6266 & RFC 8187 filename* encoding
        encoded_filename = urllib.parse.quote(filename)
        
        # Determine disposition: inline allowed only for strictly vetted non-executable types
        if not force_attachment and content_type in DownloadPolicyRules.INLINE_SAFE_MIMES:
            disposition = f"inline; filename*=UTF-8''{encoded_filename}"
        else:
            disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

        headers = {
            "Content-Type": content_type,
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": disposition,
            "Content-Security-Policy": "sandbox",
            "Content-Digest": f"sha-256=:{sha256_hash}:",
            "ETag": f'"{sha256_hash}"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(size_bytes),
        }
        return headers

    @staticmethod
    def validate_range_header(range_header: Optional[str], total_size: int) -> Optional[tuple[int, int]]:
        # RFC 9110 §14 single range limit (CVE-2011-3192 Range DoS prevention)
        if not range_header:
            return None
        
        if not range_header.startswith("bytes="):
            raise ValueError("Invalid Range header format")
        
        parts = range_header[6:].split(",")
        if len(parts) > 1:
            raise ValueError("Multiple overlapping ranges forbidden")

        range_val = parts[0].strip()
        if "-" not in range_val:
            raise ValueError("Malformed byte range")

        start_str, end_str = range_val.split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else total_size - 1

        if start > end or start >= total_size:
            raise ValueError("Range Not Satisfiable")

        return (start, min(end, total_size - 1))
