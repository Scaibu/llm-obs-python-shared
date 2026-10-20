"""
Blueprint:
- Exhaustive unit tests for upload lifecycle machine, content inspection rules, and download policy rules.
"""
import pytest
import struct
import io
import zipfile
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
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

def test_upload_lifecycle_machine_transitions():
    # Valid forward transitions
    assert UploadLifecycleMachine.can_transition("pending", "uploaded")
    assert UploadLifecycleMachine.can_transition("uploaded", "quarantined")
    assert UploadLifecycleMachine.can_transition("quarantined", "inspecting")
    assert UploadLifecycleMachine.can_transition("inspecting", "available")
    assert UploadLifecycleMachine.can_transition("available", "deleting")
    assert UploadLifecycleMachine.can_transition("deleting", "deleted")

    # Invalid bypass transitions
    assert not UploadLifecycleMachine.can_transition("pending", "available")
    assert not UploadLifecycleMachine.can_transition("quarantined", "available")
    assert not UploadLifecycleMachine.can_transition("deleted", "pending")

    with pytest.raises(ValueError):
        UploadLifecycleMachine.validate_transition("pending", "available")

def test_presign_rules_opaque_key_generation():
    key = PresignRules.generate_opaque_quarantine_key("tenant-123", "sess-abc")
    assert key == "quarantine/tenant-123/sess-abc"
    assert ".." not in key

    clean_key = PresignRules.generate_immutable_clean_key("tenant-123", "obj-1", "hash-sha256")
    assert clean_key == "clean/tenant-123/obj-1/hash-sha256"

def test_content_inspection_magic_bytes_sniffing():
    png_data = UploadPipelineConstants.MAGIC_PNG + b"\x00" * 20
    assert ContentInspectionRules.sniff_mime_type(png_data) == "image/png"

    pdf_data = UploadPipelineConstants.MAGIC_PDF + b"-1.5\n"
    assert ContentInspectionRules.sniff_mime_type(pdf_data) == "application/pdf"

    svg_data = b"<svg xmlns='http://www.w3.org/2000/svg'><circle/></svg>"
    assert ContentInspectionRules.sniff_mime_type(svg_data) == "image/svg+xml"

def test_c1_pixel_flood_rejection():
    # Construct a 200,000 x 200,000 pixel PNG header
    png_header = UploadPipelineConstants.MAGIC_PNG + b"\x00\x00\x00\rIHDR"
    dimensions = struct.pack(">II", 200000, 200000)
    fake_png = png_header + dimensions + b"\x08\x06\x00\x00\x00"

    with pytest.raises(ValueError) as exc:
        ContentInspectionRules.inspect_png_dimensions(fake_png)
    assert "exceed safe limit" in str(exc.value)

def test_c3_svg_script_detection():
    clean_svg = b"<svg><rect width='10' height='10'/></svg>"
    ContentInspectionRules.inspect_svg_security(clean_svg) # Should pass

    xss_svg = b"<svg><script>alert(1)</script></svg>"
    with pytest.raises(ValueError) as exc1:
        ContentInspectionRules.inspect_svg_security(xss_svg)
    assert "Active script or event handler detected" in str(exc1.value)

    onload_svg = b"<svg onload='alert(1)'><rect/></svg>"
    with pytest.raises(ValueError) as exc2:
        ContentInspectionRules.inspect_svg_security(onload_svg)
    assert "Active script or event handler detected" in str(exc2.value)

def test_c5_zip_slip_rejection():
    # Create an in-memory zip file attempting directory traversal
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "malicious payload")
    
    with pytest.raises(ValueError) as exc:
        ContentInspectionRules.inspect_archive_safety(buf.getvalue())
    assert "attempts path traversal" in str(exc.value)

def test_download_policy_headers():
    headers = DownloadPolicyRules.build_serving_headers(
        content_type="image/png",
        filename="test image.png",
        size_bytes=1024,
        sha256_hash="abcdef123456",
    )
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "sandbox"
    assert "inline" in headers["Content-Disposition"]
    assert "filename*=UTF-8''test%20image.png" in headers["Content-Disposition"]

    # Active or unsafe content forces attachment
    html_headers = DownloadPolicyRules.build_serving_headers(
        content_type="text/html",
        filename="page.html",
        size_bytes=500,
        sha256_hash="123456",
    )
    assert "attachment" in html_headers["Content-Disposition"]

def test_single_byte_range_validation():
    # Valid single range
    bounds = DownloadPolicyRules.validate_range_header("bytes=0-499", 1000)
    assert bounds == (0, 499)

    # Multi-range rejection (CVE-2011-3192 protection)
    with pytest.raises(ValueError) as exc:
        DownloadPolicyRules.validate_range_header("bytes=0-10,20-30", 1000)
    assert "Multiple overlapping ranges forbidden" in str(exc.value)
