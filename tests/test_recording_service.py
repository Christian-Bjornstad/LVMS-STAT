from __future__ import annotations

import queue
import tempfile
import unittest
from pathlib import Path

from lvms_stat.config import AppConfig
from lvms_stat.downloads import DownloadStatus
from lvms_stat.recording_service import (
    FailureKind,
    RecordingDependencies,
    RecordingService,
    ServiceEventKind,
)
from lvms_stat.workflow import ControlIdentity, StepKind, WorkflowStep


class Closable:
    def __init__(self, *, fail_close: bool = False) -> None:
        self.port = 49152
        self.closed = False
        self.fail_close = fail_close

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise RuntimeError("sensitive cleanup detail")


class FakePage:
    def navigate(self, *args: object, **kwargs: object) -> object:
        return object()


class FakeRecorder:
    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.installed = False

    def install(self) -> None:
        self.installed = True

    def poll(self) -> tuple[WorkflowStep, ...]:
        if self.fail:
            raise self.fail
        return (WorkflowStep(1, StepKind.ACTIVATE, ControlIdentity("BUTTON", label="Export")),)


class FakeDetector:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def poll(self) -> DownloadStatus:
        return DownloadStatus.DETECTED

    def detected_path(self) -> Path | None:
        return Path("C:/synthetic/report.csv")


class RecordingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.config = AppConfig(
            "https://lvms.example.invalid/",
            "https://lvms.example.invalid",
            root / "profile",
            root / "downloads",
            root / "workflows",
        )

    def service(self, recorder: FakeRecorder) -> tuple[RecordingService, Closable, Closable]:
        edge, connection = Closable(), Closable()
        dependencies = RecordingDependencies(
            edge_start=lambda profile: edge,
            target_wait=lambda port: object(),
            connection_open=lambda target: connection,
            page_factory=lambda active: FakePage(),
            recorder_factory=lambda page, origin: recorder,
            detector_factory=lambda path: FakeDetector(),
            worker_submit=lambda work: work(),
            sleeper=lambda seconds: None,
        )
        return RecordingService(dependencies), edge, connection

    def test_emits_safe_sequence_and_cleans_resources(self) -> None:
        service, edge, connection = self.service(FakeRecorder())
        service.start(self.config)
        events = []
        while True:
            try:
                events.append(service.events().get_nowait())
            except queue.Empty:
                break
        self.assertEqual(
            [event.kind for event in events],
            [ServiceEventKind.STARTED, ServiceEventKind.STEPS, ServiceEventKind.DOWNLOAD_DETECTED],
        )
        self.assertTrue(edge.closed)
        self.assertTrue(connection.closed)

    def test_sanitizes_failure_and_rejects_second_start(self) -> None:
        service, _, _ = self.service(FakeRecorder(RuntimeError("sensitive detail")))
        service.start(self.config)
        events = list(service.events().queue)
        self.assertEqual(events[-1].kind, ServiceEventKind.FAILED)
        self.assertEqual(events[-1].failure, FailureKind.INTERNAL)
        self.assertNotIn("sensitive detail", repr(events[-1]))
        with self.assertRaises(RuntimeError):
            service.start(self.config)

    def test_cleanup_failure_does_not_escape_worker(self) -> None:
        edge, connection = Closable(fail_close=True), Closable(fail_close=True)
        dependencies = RecordingDependencies(
            edge_start=lambda profile: edge,
            target_wait=lambda port: object(),
            connection_open=lambda target: connection,
            page_factory=lambda active: FakePage(),
            recorder_factory=lambda page, origin: FakeRecorder(),
            detector_factory=lambda path: FakeDetector(),
            worker_submit=lambda work: work(),
            sleeper=lambda seconds: None,
        )
        service = RecordingService(dependencies)
        service.start(self.config)
        events = list(service.events().queue)
        self.assertEqual(events[-1].kind, ServiceEventKind.FAILED)
        self.assertEqual(events[-1].failure, FailureKind.INTERNAL)


if __name__ == "__main__":
    unittest.main()
