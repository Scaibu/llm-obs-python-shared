"""
Blueprint:
- Exhaustive unit tests for validation lifecycle state machine.
- Tests valid transitions, illegal transitions, terminal states.
"""

import pytest
from src.features.validation.contracts.validation_types import ValidationStatus
from src.features.validation.domain.machines.validation_machine import ValidationStateMachine


def test_state_machine_valid_transitions():
    assert ValidationStateMachine.can_transition(ValidationStatus.PENDING, ValidationStatus.IN_PROGRESS)
    assert ValidationStateMachine.can_transition(ValidationStatus.IN_PROGRESS, ValidationStatus.VALID)
    assert ValidationStateMachine.can_transition(ValidationStatus.IN_PROGRESS, ValidationStatus.INVALID)
    assert ValidationStateMachine.can_transition(ValidationStatus.IN_PROGRESS, ValidationStatus.FAILED)


def test_state_machine_illegal_transitions():
    assert not ValidationStateMachine.can_transition(ValidationStatus.PENDING, ValidationStatus.VALID)
    assert not ValidationStateMachine.can_transition(ValidationStatus.VALID, ValidationStatus.IN_PROGRESS)
    assert not ValidationStateMachine.can_transition(ValidationStatus.INVALID, ValidationStatus.VALID)

    with pytest.raises(ValueError, match="Illegal state transition"):
        ValidationStateMachine.transition(ValidationStatus.VALID, ValidationStatus.PENDING)


def test_state_machine_transition_execution():
    status = ValidationStatus.PENDING
    status = ValidationStateMachine.transition(status, ValidationStatus.IN_PROGRESS)
    assert status == ValidationStatus.IN_PROGRESS

    status = ValidationStateMachine.transition(status, ValidationStatus.VALID)
    assert status == ValidationStatus.VALID
