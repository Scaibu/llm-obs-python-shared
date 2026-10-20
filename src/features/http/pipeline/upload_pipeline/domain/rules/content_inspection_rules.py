"""
Blueprint:
- Content inspection and format threat mitigation rules (Section 4).
- C1: Pixel flood mitigation (checks header before decode).
- C3/C4: SVG XSS & XXE detection (blocks scripts, inline handlers, and entity declarations).
- C5/C6: Archive Zip slip & bomb prevention (streaming validation, directory traversal checks).
- C8: Polyglot mitigation via magic-byte verification.
- C10: Formula injection escaping.
"""
import struct
import io
import zipfile
import re
from typing import Dict, List, Optional, Tuple
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
)

class ContentInspectionRules:
    @staticmethod
    def sniff_mime_type(data: bytes) -> str:
        # C8: Magic-byte sniffing
        if data.startswith(UploadPipelineConstants.MAGIC_PNG):
            return "image/png"
        if data.startswith(UploadPipelineConstants.MAGIC_JPEG):
            return "image/jpeg"
        if data.startswith(UploadPipelineConstants.MAGIC_GIF):
            return "image/gif"
        if data.startswith(UploadPipelineConstants.MAGIC_WEBP_RIFF) and len(data) >= 12 and data[8:12] == UploadPipelineConstants.MAGIC_WEBP:
            return "image/webp"
        if data.startswith(UploadPipelineConstants.MAGIC_PDF):
            return "application/pdf"
        if data.startswith(UploadPipelineConstants.MAGIC_ZIP):
            return "application/zip"
        
        # Check text/xml/svg
        sample = data[:1024].decode("utf-8", errors="ignore").strip().lower()
        if "<svg" in sample:
            return "image/svg+xml"
        if sample.startswith("<?xml") or "<html" in sample:
            return "application/xml"

        return "application/octet-stream"

    @staticmethod
    def inspect_png_dimensions(data: bytes) -> Tuple[int, int]:
        # C1: Fast header reading without full decompression/decode
        if len(data) < 24 or not data.startswith(UploadPipelineConstants.MAGIC_PNG):
            raise ValueError("Invalid PNG header")
        width, height = struct.unpack(">II", data[16:24])
        pixels = width * height
        if width > UploadPipelineConstants.IMAGE_MAX_WIDTH or height > UploadPipelineConstants.IMAGE_MAX_HEIGHT or pixels > UploadPipelineConstants.IMAGE_MAX_PIXELS:
            raise ValueError(
                UploadPipelineConstants.ERROR_PIXEL_FLOOD.format(
                    width=width,
                    height=height,
                    pixels=pixels,
                    max_pixels=UploadPipelineConstants.IMAGE_MAX_PIXELS,
                )
            )
        return width, height

    @staticmethod
    def inspect_svg_security(data: bytes) -> None:
        # C3 & C4: SVG XSS & XXE protection
        text = data.decode("utf-8", errors="ignore")
        # Block active scripts, event handlers, and external entity inclusions
        dangerous_patterns = [
            r"<script\b",
            r"javascript\s*:",
            r"on\w+\s*=",
            r"<!ENTITY\b",
            r"SYSTEM\s+[\"']",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValueError(UploadPipelineConstants.ERROR_SVG_SCRIPT_DETECTED)

    @staticmethod
    def inspect_archive_safety(data: bytes) -> None:
        # C5 & C6: Zip slip and Zip bomb controls
        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
                infolist = zf.infolist()
                if len(infolist) > UploadPipelineConstants.ARCHIVE_MAX_ENTRIES:
                    raise ValueError(f"Archive entry count {len(infolist)} exceeds maximum limit")

                total_extracted_bytes = 0
                for info in infolist:
                    # C5 Zip Slip traversal check
                    entry_name = info.filename.replace("\\", "/")
                    if entry_name.startswith("/") or ".." in entry_name.split("/"):
                        raise ValueError(
                            UploadPipelineConstants.ERROR_ZIP_SLIP.format(entry=info.filename)
                        )
                    
                    # C6 Running total extraction size
                    total_extracted_bytes += info.file_size
                    if total_extracted_bytes > UploadPipelineConstants.ARCHIVE_MAX_TOTAL_BYTES:
                        raise ValueError(
                            UploadPipelineConstants.ERROR_ZIP_BOMB.format(
                                max_bytes=UploadPipelineConstants.ARCHIVE_MAX_TOTAL_BYTES
                            )
                        )
        except zipfile.BadZipFile:
            raise ValueError("Corrupt or invalid zip archive")

    @staticmethod
    def escape_formula_cell(value: str) -> str:
        # C10: Spreadsheet Formula injection escaping
        if value and value[0] in UploadPipelineConstants.FORMULA_PREFIXES:
            return f"'{value}"
        return value
