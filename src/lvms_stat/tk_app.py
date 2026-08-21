from __future__ import annotations

import importlib
import queue
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lvms_stat.app_controller import AppController, UiMessage, ViewModel
from lvms_stat.config import load_app_config
from lvms_stat.recording_service import RecordingService
from lvms_stat.workflow import ParameterRole, StepKind, WorkflowStep
from lvms_stat.workflow import WorkflowError
from lvms_stat.workflow_store import WorkflowStore


class TkUnavailable(RuntimeError):
    """The approved Python installation cannot create the local UI."""


def load_tkinter(
    *, importer: Callable[[str], Any] = importlib.import_module
) -> tuple[Any, Any, Any]:
    try:
        return (
            importer("tkinter"),
            importer("tkinter.ttk"),
            importer("tkinter.messagebox"),
        )
    except (ImportError, RuntimeError) as exc:
        raise TkUnavailable("Tkinter is unavailable") from exc


def _safe_label(step: WorkflowStep) -> str:
    if step.parameter_role is ParameterRole.FROM_DATE:
        return "From date"
    if step.parameter_role is ParameterRole.TO_DATE:
        return "To date"
    if step.parameter_role is ParameterRole.OTHER_PARAMETER:
        return "Other parameter"
    candidate = (
        step.control.label
        or step.control.element_id
        or step.control.name
        or step.control.tag.title()
    )
    lowered = candidate.lower()
    if "://" in candidate or ".csv" in lowered or "\\" in candidate or "/" in candidate:
        return "[sanitized control]"
    return candidate[:120]


def format_step(step: WorkflowStep) -> str:
    label = _safe_label(step)
    if step.kind is StepKind.FIELD_EDITED:
        return f"{step.step_id}. Edit field: {label} [value not recorded]"
    verb = "Select" if step.kind is StepKind.SELECT else "Click"
    return f"{step.step_id}. {verb}: {label}"


def safe_ui_call(action: Callable[[], None], show: Callable[[UiMessage], None]) -> None:
    try:
        action()
    except (WorkflowError, ValueError):
        show(UiMessage.INVALID_ACTION)


class TkRecorderView:
    def __init__(self, root: Any, tk: Any, ttk: Any, messagebox: Any, event_queue: Any) -> None:
        self._root = root
        self._messagebox = messagebox
        self._event_queue = event_queue
        self._controller: AppController | None = None
        root.title("LVMS-STAT — Safe workflow recorder")
        root.geometry("760x620")
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Workflow name").pack(anchor="w")
        self._name = ttk.Entry(frame)
        self._name.pack(fill="x", pady=(0, 8))
        ttk.Label(frame, text="Notes (never include patient, sample, or session data)").pack(anchor="w")
        self._notes = tk.Text(frame, height=4, wrap="word")
        self._notes.pack(fill="x", pady=(0, 8))
        self._status = ttk.Label(frame, text="Ready")
        self._status.pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        self._start = ttk.Button(buttons, text="Start recording", command=self._on_start)
        self._stop = ttk.Button(buttons, text="Stop", command=self._on_stop)
        self._save = ttk.Button(buttons, text="Save review", command=self._on_save)
        self._open = ttk.Button(buttons, text="Open CSV locally", command=self._on_open)
        for button in (self._start, self._stop, self._save, self._open):
            button.pack(side="left", padx=(0, 8))
        ttk.Label(frame, text="Sanitized recorded steps").pack(anchor="w", pady=(14, 4))
        self._steps = tk.Listbox(frame, height=16)
        self._steps.pack(fill="both", expand=True)
        role_frame = ttk.Frame(frame)
        role_frame.pack(fill="x", pady=(8, 0))
        self._role = ttk.Combobox(
            role_frame,
            state="readonly",
            values=[role.value for role in ParameterRole],
        )
        self._role.set(ParameterRole.FROM_DATE.value)
        self._role.pack(side="left")
        ttk.Button(role_frame, text="Assign selected field", command=self._on_assign).pack(side="left", padx=8)
        ttk.Label(
            frame,
            text="Version 1 records and reviews only. Replay, scheduling, and CSV processing are inactive.",
        ).pack(anchor="w", pady=(12, 0))

    def bind_controller(self, controller: AppController) -> None:
        self._controller = controller
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.after(100, self._poll_events)

    def render(self, model: ViewModel) -> None:
        self._name.delete(0, "end")
        self._name.insert(0, model.name)
        self._notes.delete("1.0", "end")
        self._notes.insert("1.0", model.notes)
        self._status.configure(text=model.state.value.replace("_", " ").title())
        self._steps.delete(0, "end")
        for step in model.steps:
            self._steps.insert("end", format_step(step))
        for widget, enabled in (
            (self._start, model.can_start), (self._stop, model.can_stop),
            (self._save, model.can_save), (self._open, model.can_open_csv),
        ):
            widget.configure(state="normal" if enabled else "disabled")

    def confirm_privacy_boundary(self) -> bool:
        return bool(self._messagebox.askyesno(
            "Start safe recording",
            "Record only an authorised Defined Reports workflow. Typed values and report contents are not recorded.",
        ))

    def confirm_keep_incomplete(self) -> bool:
        return bool(self._messagebox.askyesno(
            "Keep sanitized steps?", "Save the already sanitized incomplete review before closing?"
        ))

    def show_message(self, message: UiMessage) -> None:
        self._messagebox.showinfo("LVMS-STAT", str(message))

    def _on_start(self) -> None:
        if self._controller:
            safe_ui_call(
                lambda: self._controller.start(
                    self._name.get(), self._notes.get("1.0", "end-1c")
                ),
                self.show_message,
            )

    def _on_stop(self) -> None:
        if self._controller:
            safe_ui_call(self._controller.stop, self.show_message)

    def _on_save(self) -> None:
        if self._controller:
            safe_ui_call(self._controller.save, self.show_message)

    def _on_open(self) -> None:
        if self._controller:
            safe_ui_call(self._controller.open_csv, self.show_message)

    def _on_assign(self) -> None:
        if not self._controller or not self._steps.curselection():
            return
        safe_ui_call(
            lambda: self._controller.assign_role(
                self._steps.curselection()[0] + 1, ParameterRole(self._role.get())
            ),
            self.show_message,
        )

    def _poll_events(self) -> None:
        if self._controller:
            while True:
                try:
                    event = self._event_queue.get_nowait()
                except queue.Empty:
                    break
                safe_ui_call(
                    lambda event=event: self._controller.handle_service_event(event),
                    self.show_message,
                )
        self._root.after(100, self._poll_events)

    def _on_close(self) -> None:
        if self._controller:
            self._controller.close()
        self._root.destroy()


def run_app(config_path: Path) -> int:
    try:
        repository = Path(__file__).resolve().parents[2]
        config = load_app_config(config_path, repository_root=repository)
        tk, ttk, messagebox = load_tkinter()
        root = tk.Tk()
        service = RecordingService()
        view = TkRecorderView(root, tk, ttk, messagebox, service.events())
        controller = AppController(
            view, service, WorkflowStore(config.workflow_directory), config
        )
        view.bind_controller(controller)
        root.mainloop()
        return 0
    except Exception:
        print("LVMS-STAT app is unavailable in this Python installation.", file=sys.stderr)
        return 2
