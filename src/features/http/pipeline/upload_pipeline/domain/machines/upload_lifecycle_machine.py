"""
Blueprint:
- Deterministic state machine DAG governing the upload session lifecycle.
- Enforces non-bypassable transitions:
    pending -> uploaded -> quarantined -> inspecting -> available (or rejected)
    available -> deleting -> deleted
"""
from typing import Dict, Set
from src.features.http.pipeline.upload_pipeline.contracts.upload_pipeline_constants import (
    UploadPipelineConstants,
)

class UploadLifecycleMachine:
    # Directed acyclic graph of allowed state transitions
    TRANSITIONS: Dict[str, Set[str]] = {
        UploadPipelineConstants.STATE_PENDING: {
            UploadPipelineConstants.STATE_UPLOADED,
            UploadPipelineConstants.STATE_REJECTED,
        },
        UploadPipelineConstants.STATE_UPLOADED: {
            UploadPipelineConstants.STATE_QUARANTINED,
            UploadPipelineConstants.STATE_REJECTED,
        },
        UploadPipelineConstants.STATE_QUARANTINED: {
            UploadPipelineConstants.STATE_INSPECTING,
            UploadPipelineConstants.STATE_REJECTED,
        },
        UploadPipelineConstants.STATE_INSPECTING: {
            UploadPipelineConstants.STATE_PROMOTED,
            UploadPipelineConstants.STATE_REJECTED,
        },
        UploadPipelineConstants.STATE_PROMOTED: {
            UploadPipelineConstants.STATE_DELETING,
        },
        UploadPipelineConstants.STATE_REJECTED: {
            UploadPipelineConstants.STATE_DELETED,
        },
        UploadPipelineConstants.STATE_DELETING: {
            UploadPipelineConstants.STATE_DELETED,
        },
        UploadPipelineConstants.STATE_DELETED: set(),
    }

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        allowed = cls.TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                UploadPipelineConstants.ERROR_INVALID_SESSION_STATE.format(
                    from_state=from_state,
                    to_state=to_state,
                )
            )
