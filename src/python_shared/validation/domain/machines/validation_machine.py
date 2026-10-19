"""
Blueprint:
- Deterministic finite state machine DAG for validation entity lifecycles.
- Defines legal states: PENDING -> IN_PROGRESS -> VALID | INVALID | FAILED.
- Pure transitions without side effects or I/O.
"""

from __future__ import annotations

from python_shared.validation.contracts.validation_types import ValidationStatus


class ValidationStateMachine:
    _TRANSITIONS: dict[ValidationStatus, set[ValidationStatus]] = {
        ValidationStatus.PENDING: {ValidationStatus.IN_PROGRESS, ValidationStatus.FAILED},
        ValidationStatus.IN_PROGRESS: {
            ValidationStatus.VALID,
            ValidationStatus.INVALID,
            ValidationStatus.FAILED,
        },
        ValidationStatus.VALID: set(),
        ValidationStatus.INVALID: set(),
        ValidationStatus.FAILED: set(),
    }

    @classmethod
    def can_transition(cls, from_status: ValidationStatus, to_status: ValidationStatus) -> bool:
        allowed = cls._TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def transition(cls, current: ValidationStatus, target: ValidationStatus) -> ValidationStatus:
        if not cls.can_transition(current, target):
            raise ValueError(
                f"Illegal state transition from '{current.value}' to '{target.value}'. Allowed: {[s.value for s in cls._TRANSITIONS.get(current, set())]}"
            )
        return target
