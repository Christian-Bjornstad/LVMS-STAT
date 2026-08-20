from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class WorkflowError(ValueError):
    """Workflow metadata is incomplete or unsafe."""


class RecorderState(StrEnum):
    READY = "ready"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPED = "stopped"
    DOWNLOAD_DETECTED = "download_detected"
    ERROR = "error"


class StepKind(StrEnum):
    ACTIVATE = "activate"
    SELECT = "select"
    FIELD_EDITED = "field_edited"


class ParameterRole(StrEnum):
    FROM_DATE = "from_date"
    TO_DATE = "to_date"
    OTHER_PARAMETER = "other_parameter"


@dataclass(frozen=True)
class ControlIdentity:
    tag: str
    control_type: str = ""
    element_id: str = ""
    name: str = ""
    role: str = ""
    label: str = ""
    locator: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowStep:
    step_id: int
    kind: StepKind
    control: ControlIdentity
    parameter_role: ParameterRole | None = None


@dataclass(frozen=True)
class WorkflowDraft:
    name: str
    notes: str
    steps: tuple[WorkflowStep, ...] = ()
    download_detected: bool = False


_TRANSITIONS = {
    (RecorderState.READY, "start"): RecorderState.STARTING,
    (RecorderState.STARTING, "connected"): RecorderState.RECORDING,
    (RecorderState.STARTING, "fail"): RecorderState.ERROR,
    (RecorderState.RECORDING, "stop"): RecorderState.STOPPED,
    (RecorderState.RECORDING, "download_detected"): RecorderState.DOWNLOAD_DETECTED,
    (RecorderState.RECORDING, "fail"): RecorderState.ERROR,
    (RecorderState.STOPPED, "download_detected"): RecorderState.DOWNLOAD_DETECTED,
}
for _state in RecorderState:
    _TRANSITIONS[(_state, "close")] = RecorderState.READY


def transition(state: RecorderState, command: str) -> RecorderState:
    try:
        return _TRANSITIONS[(state, command)]
    except KeyError as exc:
        raise WorkflowError("invalid recorder state transition") from exc


def validate_workflow(draft: WorkflowDraft) -> WorkflowDraft:
    if not isinstance(draft.name, str) or not 1 <= len(draft.name.strip()) <= 80:
        raise WorkflowError("workflow name is invalid")
    if not isinstance(draft.notes, str) or len(draft.notes.strip()) > 500:
        raise WorkflowError("workflow notes are invalid")
    if not isinstance(draft.steps, tuple) or len(draft.steps) > 2000:
        raise WorkflowError("workflow has too many steps")
    for expected_id, step in enumerate(draft.steps, 1):
        if step.step_id != expected_id or not isinstance(step.kind, StepKind):
            raise WorkflowError("workflow steps are invalid")
        control = step.control
        if not isinstance(control, ControlIdentity):
            raise WorkflowError("workflow control identity is invalid")
        fields = (
            control.tag, control.control_type, control.element_id,
            control.name, control.role, control.label,
        )
        if (
            not control.tag
            or any(not isinstance(value, str) or len(value) > 120 for value in fields)
            or not isinstance(control.locator, tuple)
            or len(control.locator) > 12
            or any(not isinstance(part, str) or len(part) > 120 for part in control.locator)
        ):
            raise WorkflowError("workflow control identity is invalid")
        if step.parameter_role is not None and step.kind is not StepKind.FIELD_EDITED:
            raise WorkflowError("only edited fields can be parameters")
        if step.parameter_role is not None and not isinstance(step.parameter_role, ParameterRole):
            raise WorkflowError("workflow parameter role is invalid")
    return replace(draft, name=draft.name.strip(), notes=draft.notes.strip())


def assign_parameter_role(
    draft: WorkflowDraft, step_id: int, role: ParameterRole
) -> WorkflowDraft:
    updated: list[WorkflowStep] = []
    found = False
    for step in draft.steps:
        if step.step_id == step_id:
            found = True
            if step.kind is not StepKind.FIELD_EDITED:
                raise WorkflowError("only edited fields can be parameters")
            step = replace(step, parameter_role=role)
        updated.append(step)
    if not found:
        raise WorkflowError("workflow step was not found")
    return validate_workflow(replace(draft, steps=tuple(updated)))
