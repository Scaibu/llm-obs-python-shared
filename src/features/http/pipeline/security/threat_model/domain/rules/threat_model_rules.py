"""
Blueprint:
- Verification rules to evaluate runtime compliance against STRIDE threat model invariants.
"""
from typing import List, Dict, Any
from src.features.http.pipeline.security.threat_model.contracts.threat_model_constants import (
    THREAT_MODEL_MATRIX,
    TrustBoundaryThreat,
)

class ThreatModelRules:
    @staticmethod
    def audit_pipeline_controls(active_controls: List[str]) -> Dict[str, Any]:
        unmitigated: List[TrustBoundaryThreat] = []
        mitigated_count = 0

        for item in THREAT_MODEL_MATRIX:
            control_parts = [c.strip() for c in item.mandatory_control_id.replace("+", " ").split()]
            if any(ctrl in active_controls for ctrl in control_parts):
                mitigated_count += 1
            else:
                unmitigated.append(item)

        return {
            "total_threats": len(THREAT_MODEL_MATRIX),
            "mitigated_count": mitigated_count,
            "all_mitigated": len(unmitigated) == 0,
            "unmitigated_threats": [t.dict() for t in unmitigated],
        }
