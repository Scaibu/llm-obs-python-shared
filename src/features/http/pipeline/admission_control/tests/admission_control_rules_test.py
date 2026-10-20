"""
Blueprint:
- Unit tests for admission_control rules.
"""
import pytest
from src.features.http.pipeline.admission_control.domain.rules.admission_control_rules import (
    AdmissionControlRules,
)

def test_admission_control_acquired():
    AdmissionControlRules.evaluate_admission(True, 5)

def test_admission_control_exceeded():
    with pytest.raises(RuntimeError) as exc_info:
        AdmissionControlRules.evaluate_admission(False, 100)
    assert "Too Many Requests" in str(exc_info.value)
