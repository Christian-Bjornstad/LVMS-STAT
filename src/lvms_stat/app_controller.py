from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Protocol

from lvms_stat.config import AppConfig
from lvms_stat.recording_service import ServiceEvent, ServiceEventKind
from lvms_stat.workflow import (
    ParameterRole,
    RecorderState,
    WorkflowDraft,
    WorkflowError,
    WorkflowStep,
    assign_parameter_role,
    transition,
    validate_workflow,
)


class UiMessage(StrEnum):
    PRIVACY_CANCELLED = "Recording cancelled."
    RECORDING_FAILED = "Recording stopped safely."
    DOWNLOAD_AMBIGUOUS = "More than one new CSV was detected."
    WORKFLOW_SAVED = "Sanitized workflow saved locally."
    CSV_OPEN_FAILED = "The detected CSV could not be opened locally."


@dataclass(frozen=True)
class ViewModel:
    name: str
    notes: str
    state: RecorderState
    steps: tuple[WorkflowStep, ...]
    can_start: bool
    can_stop: bool
    can_save: bool
    can_open_csv: bool


class RecorderView(Protocol):
    def render(self, model: ViewModel) -> None: ...
    def confirm_privacy_boundary(self) -> bool: ...
    def confirm_keep_incomplete(self) -> bool: ...
    def show_message(self, message: UiMessage) -> None: ...


class AppController:
    def __init__(
        self,
        view: RecorderView,
        service: Any,
        store: Any,
        config: AppConfig,
    ) -> None:
        self._view = view
        self._service = service
        self._store = store
        self._config = config
        self._state = RecorderState.READY
        self._draft = WorkflowDraft("New workflow", "")
        self._render()

    def _model(self) -> ViewModel:
        stopped = self._state in {RecorderState.STOPPED, RecorderState.DOWNLOAD_DETECTED}
        return ViewModel(
            name=self._draft.name,
            notes=self._draft.notes,
            state=self._state,
            steps=self._draft.steps,
            can_start=self._state is RecorderState.READY,
            can_stop=self._state is RecorderState.RECORDING,
            can_save=stopped and bool(self._draft.steps),
            can_open_csv=self._state is RecorderState.DOWNLOAD_DETECTED,
        )

    def _render(self) -> None:
        self._view.render(self._model())

    def start(self, name: str, notes: str) -> None:
        draft = validate_workflow(WorkflowDraft(name, notes))
        if not self._view.confirm_privacy_boundary():
            self._view.show_message(UiMessage.PRIVACY_CANCELLED)
            return
        self._draft = draft
        self._state = transition(self._state, "start")
        self._render()
        self._service.start(self._config)

    def stop(self) -> None:
        if self._state is not RecorderState.RECORDING:
            raise WorkflowError("recording is not active")
        self._service.request_stop()

    def handle_service_event(self, event: ServiceEvent) -> None:
        if event.kind is ServiceEventKind.STARTED:
            self._state = transition(self._state, "connected")
        elif event.kind is ServiceEventKind.STEPS:
            if self._state is not RecorderState.RECORDING:
                raise WorkflowError("steps arrived outside recording")
            expected = len(self._draft.steps) + 1
            if not event.steps or event.steps[0].step_id != expected:
                raise WorkflowError("recorded steps are not sequential")
            self._draft = validate_workflow(
                replace(self._draft, steps=self._draft.steps + event.steps)
            )
        elif event.kind is ServiceEventKind.STOPPED:
            if self._state is RecorderState.RECORDING:
                self._state = transition(self._state, "stop")
        elif event.kind is ServiceEventKind.DOWNLOAD_DETECTED:
            self._state = transition(self._state, "download_detected")
            self._draft = replace(self._draft, download_detected=True)
        elif event.kind is ServiceEventKind.AMBIGUOUS_DOWNLOAD:
            if self._state is RecorderState.RECORDING:
                self._state = transition(self._state, "stop")
            self._view.show_message(UiMessage.DOWNLOAD_AMBIGUOUS)
        elif event.kind is ServiceEventKind.FAILED:
            if self._state in {RecorderState.STARTING, RecorderState.RECORDING}:
                self._state = transition(self._state, "fail")
            self._view.show_message(UiMessage.RECORDING_FAILED)
        self._render()

    def assign_role(self, step_id: int, role: ParameterRole) -> None:
        if self._state not in {RecorderState.STOPPED, RecorderState.DOWNLOAD_DETECTED}:
            raise WorkflowError("parameters can be assigned only after recording")
        self._draft = assign_parameter_role(self._draft, step_id, role)
        self._render()

    def save(self) -> None:
        if not self._model().can_save:
            raise WorkflowError("workflow is not ready to save")
        self._store.save(self._draft)
        self._view.show_message(UiMessage.WORKFLOW_SAVED)

    def open_csv(self) -> None:
        if not self._model().can_open_csv:
            raise WorkflowError("no CSV is ready to open")
        try:
            self._service.open_detected_csv()
        except Exception:
            self._view.show_message(UiMessage.CSV_OPEN_FAILED)

    def close(self) -> None:
        if self._state in {RecorderState.STARTING, RecorderState.RECORDING}:
            if self._view.confirm_keep_incomplete() and self._draft.steps:
                self._store.save(self._draft)
        self._service.close()
        self._state = RecorderState.READY
        self._render()
