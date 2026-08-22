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
DEFAULT_JOBS_FILENAME = "jobs.hematology-test.json"
BatchProgress = Callable[[int, int], None]
BatchFailure = Callable[[str], None]
BatchRunner = Callable[
    [Path, Path, tuple[str, ...], BatchProgress, BatchFailure], int
]

FAILURE_LABELS = {
    "configuration": "oppsettet",
    "job_definitions": "rapportoppsettet",
    "output_check": "kontroll av nedlastinger",
    "edge_start": "oppstart av Edge",
    "cdp_connect": "tilkobling til Edge",
    "lvms_open": "åpning av LVMS",
    "download_setup": "oppsett av nedlasting",
    "defined_reports": "navigering til Definerte rapporter",
    "defined_reports_probe_form": "kontroll av rapportskjemaet",
    "defined_reports_contract_origin": "kontroll av LVMS-adressen for rapportskjemaet",
    "defined_reports_wait_origin": "venting på LVMS-siden etter intern overgang",
    "defined_reports_contract_metadata": "validering av rapportskjemaets kontrollmetadata",
    "defined_reports_contract_evaluation": "lesing av rapportskjemaets DOM",
    "defined_reports_missing_job_type": "finner ikke feltet Rapporttype",
    "defined_reports_missing_clear": "finner ikke knappen Tøm",
    "defined_reports_missing_export": "finner ikke knappen Eksportere",
    "defined_reports_find_direct": "søk etter Definerte rapporter i tram-lines",
    "defined_reports_activate_direct": "klikk på Definerte rapporter i tram-lines",
    "defined_reports_wait_form": "venting på rapportskjemaet etter klikk",
    "defined_reports_find_section": "søk etter Eksterne rapporter",
    "defined_reports_hover_section": "åpning av undermenyen Eksterne rapporter",
    "defined_reports_activate_section": "klikk på Eksterne rapporter",
    "defined_reports_find_more": "søk etter Mer-menyen",
    "defined_reports_activate_more": "klikk på Mer-menyen",
    "defined_reports_ready": "gjenkjenning av rapportskjemaet",
    "cleanup": "avslutning av Edge",
    **{
        f"report_{number}_{stage}": f"rapport {number} – {label}"
        for number in range(1, 4)
        for stage, label in (
            ("clear", "tømming av skjema"),
            ("fill", "utfylling"),
            ("export", "eksport"),
            ("download", "nedlasting"),
        )
    },
}


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
    failure: BatchFailure,
) -> int:
    return run_report_batch(
        config_path,
        jobs_path,
        job_keys,
        output=io.StringIO(),
        progress=progress,
        failure=failure,
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

    failed_stage: str | None = None

    def report_failure(stage: str) -> None:
        nonlocal failed_stage
        if stage in FAILURE_LABELS:
            failed_stage = stage

    try:
        result = runner(
            config_path,
            config_path.with_name(DEFAULT_JOBS_FILENAME),
            DEFAULT_JOB_KEYS,
            report_progress,
            report_failure,
        )
    except Exception:
        result = 2
    if result == 0:
        status("Ferdig – 3 rapporter er lastet ned.")
    elif result == 130:
        status("Kjøringen ble avbrutt.")
    else:
        if failed_stage is None:
            status("Kjøringen stoppet. Rett feilen og prøv igjen manuelt.")
        else:
            status(f"Kjøringen stoppet ved: {FAILURE_LABELS[failed_stage]}.")
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
