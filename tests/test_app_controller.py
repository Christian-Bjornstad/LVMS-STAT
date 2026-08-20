from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lvms_stat.app_controller import AppController, UiMessage
from lvms_stat.config import AppConfig
from lvms_stat.recording_service import ServiceEvent, ServiceEventKind
from lvms_stat.workflow import (
    ControlIdentity,
    ParameterRole,
    RecorderState,
    StepKind,
    WorkflowStep,
)


class FakeView:
    def __init__(self) -> None:
        self.models = []
        self.messages: list[UiMessage] = []
        self.allow = True

    def render(self, model: object) -> None:
        self.models.append(model)

    def confirm_privacy_boundary(self) -> bool:
        return self.allow

    def confirm_keep_incomplete(self) -> bool:
        return False

    def show_message(self, message: UiMessage) -> None:
        self.messages.append(message)


class FakeService:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.opened = False
        self.closed = False

    def start(self, config: AppConfig) -> None:
        self.started = True

    def request_stop(self) -> None:
        self.stopped = True

    def open_detected_csv(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True


class FakeStore:
    def __init__(self) -> None:
        self.saved = []

    def save(self, draft: object) -> Path:
        self.saved.append(draft)
        return Path("C:/opaque.json")


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(tempfile.gettempdir()).resolve()
        self.config = AppConfig("https://x.invalid/", "https://x.invalid", root / "p", root / "d", root / "w")
        self.view, self.service, self.store = FakeView(), FakeService(), FakeStore()
        self.controller = AppController(self.view, self.service, self.store, self.config)

    def test_starts_records_stops_assigns_and_saves(self) -> None:
        self.controller.start("Weekly report", "Safe note")
        self.assertEqual(self.view.models[-1].state, RecorderState.STARTING)
        self.controller.handle_service_event(ServiceEvent(ServiceEventKind.STARTED))
        step = WorkflowStep(1, StepKind.FIELD_EDITED, ControlIdentity("INPUT", label="From date"))
        self.controller.handle_service_event(ServiceEvent(ServiceEventKind.STEPS, (step,)))
        self.controller.stop()
        self.controller.handle_service_event(ServiceEvent(ServiceEventKind.STOPPED))
        self.controller.assign_role(1, ParameterRole.FROM_DATE)
        self.controller.save()
        self.assertEqual(self.store.saved[0].steps[0].parameter_role, ParameterRole.FROM_DATE)

    def test_rejects_invalid_start_and_requires_privacy_confirmation(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.start("", "")
        self.view.allow = False
        self.controller.start("Valid", "")
        self.assertFalse(self.service.started)

    def test_enables_open_only_after_download_and_closes_service(self) -> None:
        self.controller.start("Valid", "")
        self.controller.handle_service_event(ServiceEvent(ServiceEventKind.STARTED))
        self.assertFalse(self.view.models[-1].can_open_csv)
        self.controller.handle_service_event(ServiceEvent(ServiceEventKind.DOWNLOAD_DETECTED))
        self.assertTrue(self.view.models[-1].can_open_csv)
        self.controller.open_csv()
        self.controller.close()
        self.assertTrue(self.service.opened)
        self.assertTrue(self.service.closed)


if __name__ == "__main__":
    unittest.main()
