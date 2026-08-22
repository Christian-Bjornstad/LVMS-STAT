"""Modern PyQt6 dashboard for the statistics pipeline.

Design language: dark card layout, one status card per unit, a single
prominent action ("Hent oppdatering"), live progress and a quiet log.
All heavy work runs on a worker thread; the UI thread only paints.

The pure logic lives in :mod:`lvms_stat.dashboard_state` and
:mod:`lvms_stat.fetch_orchestrator` - both fully unit tested without Qt.
"""

from __future__ import annotations

import importlib
import queue
import sys
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

DARK_BACKGROUND = "#12151c"
CARD_BACKGROUND = "#1b2029"
CARD_BORDER = "#2a3140"
TEXT_PRIMARY = "#e8ecf3"
TEXT_MUTED = "#8b94a7"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#6b9fff"
OK_GREEN = "#3ecf8e"
AMBER = "#f5a623"

STYLESHEET = f"""
QWidget {{ background: {DARK_BACKGROUND}; color: {TEXT_PRIMARY};
           font-family: 'Segoe UI'; font-size: 13px; }}
QLabel#Title {{ font-size: 22px; font-weight: 650; }}
QLabel#Subtitle {{ color: {TEXT_MUTED}; }}
QLabel#CardTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#Muted {{ color: {TEXT_MUTED}; }}
QPushButton#Primary {{ background: {ACCENT}; border: none; border-radius: 8px;
    padding: 12px 26px; font-size: 14px; font-weight: 600; color: white; }}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: {CARD_BORDER}; color: {TEXT_MUTED}; }}
QFrame#Card {{ background: {CARD_BACKGROUND}; border: 1px solid {CARD_BORDER};
    border-radius: 10px; }}
QProgressBar {{ background: {CARD_BORDER}; border: none; border-radius: 6px;
    height: 12px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QPlainTextEdit#Log {{ background: {CARD_BACKGROUND};
    border: 1px solid {CARD_BORDER}; border-radius: 8px;
    color: {TEXT_MUTED}; font-family: Consolas; font-size: 12px; }}
"""


class PyQtUnavailable(RuntimeError):
    """The approved Python installation cannot create the PyQt6 UI."""


def load_pyqt6(
    *, importer: Callable[[str], Any] = importlib.import_module
) -> tuple[Any, Any]:
    try:
        return importer("PyQt6.QtCore"), importer("PyQt6.QtWidgets")
    except (ImportError, RuntimeError) as exc:
        raise PyQtUnavailable("PyQt6 is unavailable") from exc


def build_dashboard(
    config_path: Path,
    *,
    fetch_runner: Callable[..., object],
    today_provider: Callable[[], date] = date.today,
) -> tuple[Any, Any]:
    """Construct the dashboard window. Returns ``(window, app)``."""
    QtCore, QtWidgets = load_pyqt6()
    from lvms_stat.dashboard_state import (
        describe_failure,
        describe_outcome,
        load_unit_statuses,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setStyleSheet(STYLESHEET)

    window = QtWidgets.QWidget()
    window.setWindowTitle("LVMS Statistikk")
    window.setMinimumSize(720, 560)
    root = QtWidgets.QVBoxLayout(window)
    root.setContentsMargins(28, 24, 28, 20)
    root.setSpacing(14)

    header = QtWidgets.QHBoxLayout()
    titles = QtWidgets.QVBoxLayout()
    title = QtWidgets.QLabel("Statistikk")
    title.setObjectName("Title")
    subtitle = QtWidgets.QLabel(
        "Inkrementell henting fra LVMS - arkiveres automatisk på statistikk-disken."
    )
    subtitle.setObjectName("Subtitle")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles)
    header.addStretch(1)
    refresh_button = QtWidgets.QPushButton("Oppdater status")
    refresh_button.setObjectName("Muted")
    header.addWidget(refresh_button)
    root.addLayout(header)

    cards_layout = QtWidgets.QVBoxLayout()
    cards_layout.setSpacing(10)
    root.addLayout(cards_layout)
    card_widgets: dict[str, dict[str, Any]] = {}

    def make_card(unit: Any) -> None:
        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        inner = QtWidgets.QVBoxLayout(card)
        inner.setContentsMargins(18, 14, 18, 14)
        inner.setSpacing(6)
        head = QtWidgets.QHBoxLayout()
        name = QtWidgets.QLabel(unit.label)
        name.setObjectName("CardTitle")
        badge = QtWidgets.QLabel()
        head.addWidget(name)
        head.addStretch(1)
        head.addWidget(badge)
        detail = QtWidgets.QLabel()
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        inner.addLayout(head)
        inner.addWidget(detail)
        run_button = QtWidgets.QPushButton("Hent nå")
        run_button.setCursor(
            QtCore.Qt.CursorShape.PointingHandCursor
        )
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(run_button)
        inner.addLayout(row)
        cards_layout.addWidget(card)
        card_widgets[unit.key] = {
            "badge": badge,
            "detail": detail,
            "run": run_button,
            "unit": unit,
        }
        run_button.clicked.connect(lambda _=False, key=unit.key: start_fetch(key))

    progress = QtWidgets.QProgressBar()
    progress.setVisible(False)
    progress.setTextVisible(False)
    progress.setFixedHeight(12)
    root.addWidget(progress)

    status_label = QtWidgets.QLabel("")
    status_label.setObjectName("Subtitle")
    status_label.setWordWrap(True)
    root.addWidget(status_label)

    log_box = QtWidgets.QPlainTextEdit()
    log_box.setObjectName("Log")
    log_box.setReadOnly(True)
    log_box.setVisible(False)
    root.addWidget(log_box, stretch=1)

    footer = QtWidgets.QHBoxLayout()
    hint = QtWidgets.QLabel("K:\\-arkiv og manifest oppdateres etter hver kjøring.")
    hint.setObjectName("Muted")
    footer.addWidget(hint)
    footer.addStretch(1)
    root.addLayout(footer)

    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def post(kind: str, value: Any = None) -> None:
        events.put((kind, value))

    # -- state rendering -------------------------------------------------

    def refresh_cards() -> None:
        try:
            statuses = load_unit_statuses(
                config_path, today=today_provider()
            )
        except Exception as exc:
            post("status", f"Klarte ikke lese oppsettet: {describe_failure(exc)}")
            return
        while cards_layout.count():
            item = cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        card_widgets.clear()
        for unit in statuses:
            make_card(unit)
        for unit in statuses:
            widgets = card_widgets[unit.key]
            stale = [r for r in unit.reports if r.needs_fetch]
            if not stale:
                widgets["badge"].setText(f"● Oppdatert")
                widgets["badge"].setStyleSheet(f"color: {OK_GREEN};")
                widgets["run"].setEnabled(True)
            else:
                widgets["badge"].setText(f"● {len(stale)} må hentes")
                widgets["badge"].setStyleSheet(f"color: {AMBER};")
            lines = []
            for report in unit.reports:
                lines.append(f"{report.report_id} - {report.headline}")
            lines.append(f"{unit.analysis_code_count} analysekoder")
            widgets["detail"].setText("\n".join(lines))

    # -- fetching ----------------------------------------------------------

    running_key: list[str | None] = [None]

    def start_fetch(unit_key: str) -> None:
        if running_key[0] is not None:
            return
        running_key[0] = unit_key
        for widgets in card_widgets.values():
            widgets["run"].setEnabled(False)
        refresh_button.setEnabled(False)
        progress.setRange(0, 0)  # busy indicator
        progress.setVisible(True)
        log_box.clear()
        log_box.setVisible(True)
        status_label.setText("Kjører - åpner LVMS …")

        def worker() -> None:
            def on_status(message: str) -> None:
                post("log", message)

            def on_progress(current: int, total: int) -> None:
                post("progress", (current, total))

            def on_failure(stage: str) -> None:
                post("log", f"stopp ved {stage}")

            try:
                outcome = fetch_runner(
                    config_path,
                    unit_key=unit_key,
                    output=log_stream(),
                    progress=on_progress,
                    failure=on_failure,
                )
                post("outcome", outcome)
            except Exception as exc:
                post("failed", exc)

        def log_stream() -> Any:
            class Stream:
                def write(self, text: str) -> None:
                    if text.strip():
                        post("log", text.strip())

                def flush(self) -> None:
                    pass

            return Stream()

        threading.Thread(target=worker, daemon=True).start()

    def finish_success(outcome: Any) -> None:
        running_key[0] = None
        progress.setVisible(False)
        status_label.setText(describe_outcome(outcome))
        refresh_cards()

    def finish_failure(error: Exception) -> None:
        running_key[0] = None
        progress.setVisible(False)
        status_label.setText(describe_failure(error))
        refresh_cards()

    def poll_events() -> None:
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                return
            if kind == "status":
                status_label.setText(str(value))
            elif kind == "log":
                log_box.appendPlainText(str(value))
            elif kind == "progress":
                current, total = value
                progress.setRange(0, max(total, 1))
                progress.setValue(min(current, total))
            elif kind == "outcome":
                finish_success(value)
            elif kind == "failed":
                finish_failure(value)

    refresh_button.clicked.connect(refresh_cards)
    timer = QtCore.QTimer(window)
    timer.timeout.connect(poll_events)
    timer.start(120)
    refresh_cards()

    window.show()
    return window, app


def run_app(config_path: Path, **kwargs: Any) -> int:
    """Open the modern statistics dashboard."""
    from lvms_stat.fetch_orchestrator import run_incremental_fetch

    try:
        _, app = build_dashboard(
            config_path,
            fetch_runner=run_incremental_fetch,
            **kwargs,
        )
        return int(app.exec())
    except Exception:
        print("LVMS-STAT dashboard is unavailable.", file=sys.stderr)
        return 2
