from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from lvms_stat.cdp import CdpError, BrowserPage, CdpConnection
from lvms_stat.config import AppConfig
from lvms_stat.downloads import (
    CsvArrivalDetector,
    DownloadError,
    DownloadStatus,
    open_local,
)
from lvms_stat.edge import EdgeLaunchError, EdgeProcess
from lvms_stat.cdp import wait_for_page_target
from lvms_stat.recorder import RecorderSession, RecorderUnavailable
from lvms_stat.workflow import WorkflowStep


class ServiceEventKind(StrEnum):
    STARTED = "started"
    STEPS = "steps"
    STOPPED = "stopped"
    DOWNLOAD_DETECTED = "download_detected"
    AMBIGUOUS_DOWNLOAD = "ambiguous_download"
    FAILED = "failed"


class FailureKind(StrEnum):
    EDGE = "edge"
    CONNECTION = "connection"
    RECORDER = "recorder"
    DOWNLOAD = "download"
    INTERNAL = "internal"


@dataclass(frozen=True)
class ServiceEvent:
    kind: ServiceEventKind
    steps: tuple[WorkflowStep, ...] = ()
    failure: FailureKind | None = None


def _submit_thread(work: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=work, name="lvms-stat-recorder", daemon=False)
    thread.start()
    return thread


@dataclass(frozen=True)
class RecordingDependencies:
    edge_start: Callable[[Any], Any] = EdgeProcess.start
    target_wait: Callable[[int], Any] = wait_for_page_target
    connection_open: Callable[[Any], Any] = CdpConnection.open
    page_factory: Callable[[Any], Any] = BrowserPage
    recorder_factory: Callable[[Any, str], Any] = lambda page, origin: RecorderSession(page, origin)
    detector_factory: Callable[[Any], Any] = CsvArrivalDetector
    worker_submit: Callable[[Callable[[], None]], Any] = _submit_thread
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    csv_opener: Callable[..., None] = open_local


class RecordingService:
    def __init__(self, dependencies: RecordingDependencies | None = None) -> None:
        self._deps = dependencies or RecordingDependencies()
        self._events: queue.Queue[ServiceEvent] = queue.Queue()
        self._stop = threading.Event()
        self._close = threading.Event()
        self._started = False
        self._worker: Any | None = None
        self._detector: Any | None = None

    def events(self) -> queue.Queue[ServiceEvent]:
        return self._events

    def start(self, config: AppConfig) -> None:
        if self._started:
            raise RuntimeError("recording service already started")
        self._started = True
        self._worker = self._deps.worker_submit(lambda: self._run(config))

    def _emit(self, kind: ServiceEventKind, *, steps: tuple[WorkflowStep, ...] = (), failure: FailureKind | None = None) -> None:
        self._events.put(ServiceEvent(kind, steps, failure))

    def _run(self, config: AppConfig) -> None:
        edge: Any | None = None
        connection: Any | None = None
        try:
            self._detector = self._deps.detector_factory(config.download_directory)
            self._detector.start()
            edge = self._deps.edge_start(config.profile_directory)
            target = self._deps.target_wait(edge.port)
            connection = self._deps.connection_open(target)
            page = self._deps.page_factory(connection)
            page.navigate(config.landing_url, config.expected_origin, timeout_seconds=120)
            recorder = self._deps.recorder_factory(page, config.expected_origin)
            recorder.install()
            self._emit(ServiceEventKind.STARTED)
            while not self._close.is_set():
                if self._stop.is_set():
                    self._emit(ServiceEventKind.STOPPED)
                    self._wait_after_stop()
                    return
                steps = recorder.poll()
                if steps:
                    self._emit(ServiceEventKind.STEPS, steps=steps)
                status = self._detector.poll()
                if status is DownloadStatus.DETECTED:
                    self._emit(ServiceEventKind.DOWNLOAD_DETECTED)
                    return
                if status is DownloadStatus.AMBIGUOUS:
                    self._emit(ServiceEventKind.AMBIGUOUS_DOWNLOAD)
                    return
                self._deps.sleeper(0.25)
        except EdgeLaunchError:
            self._emit(ServiceEventKind.FAILED, failure=FailureKind.EDGE)
        except CdpError:
            self._emit(ServiceEventKind.FAILED, failure=FailureKind.CONNECTION)
        except RecorderUnavailable:
            self._emit(ServiceEventKind.FAILED, failure=FailureKind.RECORDER)
        except DownloadError:
            self._emit(ServiceEventKind.FAILED, failure=FailureKind.DOWNLOAD)
        except Exception:
            self._emit(ServiceEventKind.FAILED, failure=FailureKind.INTERNAL)
        finally:
            cleanup_failed = False
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    cleanup_failed = True
            if edge is not None:
                try:
                    edge.close()
                except Exception:
                    cleanup_failed = True
            if cleanup_failed:
                self._emit(ServiceEventKind.FAILED, failure=FailureKind.INTERNAL)

    def _wait_after_stop(self) -> None:
        deadline = self._deps.clock() + 10
        while not self._close.is_set() and self._deps.clock() < deadline:
            status = self._detector.poll()
            if status is DownloadStatus.DETECTED:
                self._emit(ServiceEventKind.DOWNLOAD_DETECTED)
                return
            if status is DownloadStatus.AMBIGUOUS:
                self._emit(ServiceEventKind.AMBIGUOUS_DOWNLOAD)
                return
            self._deps.sleeper(0.25)

    def request_stop(self) -> None:
        self._stop.set()

    def open_detected_csv(self) -> None:
        if self._detector is None or self._detector.detected_path() is None:
            raise DownloadError("detected CSV is unavailable")
        self._deps.csv_opener(self._detector.detected_path())

    def close(self) -> None:
        self._close.set()
        self._stop.set()
        if self._worker is not None and hasattr(self._worker, "join"):
            self._worker.join(timeout=5)
