from __future__ import annotations

import importlib
import io
import queue
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lvms_stat.batch_runner import run_report_batch


DEFAULT_JOB_KEYS = ("ordered", "answered", "extraction")
BatchProgress = Callable[[int, int], None]
BatchRunner = Callable[[Path, Path, tuple[str, ...], BatchProgress], int]


class PyQtUnavailable(RuntimeError):
    """The approved Python installation cannot create the PyQt6 UI."""


def load_pyqt6(
    *, importer: Callable[[str], Any] = importlib.import_module
) -> tuple[Any, Any]:
    try:
        return importer("PyQt6.QtCore"), importer("PyQt6.QtWidgets")
    except (ImportError, RuntimeError) as exc:
        raise PyQtUnavailable("PyQt6 is unavailable") from exc


def _run_batch_silently(
    config_path: Path,
    jobs_path: Path,
    job_keys: tuple[str, ...],
    progress: BatchProgress,
) -> int:
    return run_report_batch(
        config_path,
        jobs_path,
        job_keys,
        output=io.StringIO(),
        progress=progress,
    )


def run_one_click_batch(
    config_path: Path,
    *,
    runner: BatchRunner = _run_batch_silently,
    status: Callable[[str], None],
) -> int:
    """Run the fixed local three-report batch from one app action."""
    status("Åpner LVMS og starter rapportene …")

    def report_progress(current: int, total: int) -> None:
        status(f"Kjører rapport {current} av {total} …")

    try:
        result = runner(
            config_path,
            config_path.with_name("jobs.json"),
            DEFAULT_JOB_KEYS,
            report_progress,
        )
    except Exception:
        result = 2
    if result == 0:
        status("Ferdig – 3 rapporter er lastet ned.")
    elif result == 130:
        status("Kjøringen ble avbrutt.")
    else:
        status("Kjøringen stoppet. Rett feilen og prøv igjen manuelt.")
    return result


def run_app(config_path: Path, *, runner: BatchRunner = _run_batch_silently) -> int:
    """Open the visible one-click PyQt6 batch app."""
    try:
        QtCore, QtWidgets = load_pyqt6()
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
        window = QtWidgets.QWidget()
        window.setWindowTitle("LVMS-STAT")
        window.setMinimumWidth(460)

        layout = QtWidgets.QVBoxLayout(window)
        title = QtWidgets.QLabel("LVMS statistikk")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        description = QtWidgets.QLabel(
            "Åpner synlig Edge og henter ordered, answered og extraction automatisk."
        )
        description.setWordWrap(True)
        status_label = QtWidgets.QLabel("Klar")
        run_button = QtWidgets.QPushButton("Kjør rapporter")
        run_button.setMinimumHeight(44)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(12)
        layout.addWidget(status_label)
        layout.addWidget(run_button)

        events: queue.Queue[tuple[str, object]] = queue.Queue()

        def update_status(message: str) -> None:
            events.put(("status", message))

        def worker() -> None:
            result = run_one_click_batch(
                config_path, runner=runner, status=update_status
            )
            events.put(("done", result))

        def start_batch() -> None:
            run_button.setEnabled(False)
            threading.Thread(target=worker, daemon=True).start()

        def poll_events() -> None:
            while True:
                try:
                    kind, value = events.get_nowait()
                except queue.Empty:
                    return
                if kind == "status":
                    status_label.setText(str(value))
                elif kind == "done":
                    run_button.setEnabled(True)

        run_button.clicked.connect(start_batch)
        timer = QtCore.QTimer(window)
        timer.timeout.connect(poll_events)
        timer.start(100)
        window.show()
        return int(app.exec())
    except Exception:
        print("LVMS-STAT PyQt6 app is unavailable.", file=sys.stderr)
        return 2
