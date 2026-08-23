"""Modern PyQt6 dashboard for the statistics pipeline.

Design language (ui-ux-pro-max derived): dark charcoal shell with a
Power-BI-inspired yellow accent (#F2C811), fixed left sidebar navigation
with three pages - Dashbord, Logg and Oppsett (in-app configuration).
All heavy work runs on a worker thread; the UI thread only paints.

The pure logic lives in :mod:`lvms_stat.dashboard_state`,
:mod:`lvms_stat.fetch_orchestrator` and :mod:`lvms_stat.settings_store`
- all fully unit tested without Qt.
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

# -- design tokens (warm yellow / Power BI inspired) --------------------
BG = "#1f1f1f"
SIDEBAR_BG = "#181818"
CARD_BG = "#292827"
CARD_BORDER = "#3b3a39"
TEXT_PRIMARY = "#f3f2f1"
TEXT_MUTED = "#a19f9d"
ACCENT = "#f2c811"  # Power BI yellow
ACCENT_HOVER = "#ffd83d"
ON_ACCENT = "#1f1f1f"
OK_GREEN = "#6ccb5f"
WARN_AMBER = "#eda73c"

SIDEBAR_WIDTH = 216

STYLESHEET = f"""
QWidget {{ background: {BG}; color: {TEXT_PRIMARY};
           font-family: 'Segoe UI'; font-size: 13px; }}
QLabel#Title {{ font-size: 24px; font-weight: 650; }}
QLabel#Subtitle {{ color: {TEXT_MUTED}; }}
QLabel#CardTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#Muted {{ color: {TEXT_MUTED}; }}
QLabel#Brand {{ font-size: 15px; font-weight: 700; color: {TEXT_PRIMARY};
                padding: 2px 0; }}
QLabel#BrandDot {{ color: {ACCENT}; font-size: 15px; }}
QLineEdit {{ background: {SIDEBAR_BG}; border: 1px solid {CARD_BORDER};
    border-radius: 6px; padding: 7px 10px;
    selection-background-color: {ACCENT}; selection-color: {ON_ACCENT}; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QPlainTextEdit {{ background: {SIDEBAR_BG}; border: 1px solid {CARD_BORDER};
    border-radius: 6px; padding: 6px 8px; font-size: 12.5px;
    selection-background-color: {ACCENT}; selection-color: {ON_ACCENT}; }}
QPlainTextEdit:focus {{ border-color: {ACCENT}; }}

QPushButton#Nav {{ background: transparent; border: none; border-radius: 8px;
    padding: 11px 14px; text-align: left; font-size: 13.5px;
    color: {TEXT_MUTED}; }}
QPushButton#Nav:hover {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; }}
QPushButton#Nav:checked {{ background: {CARD_BG}; color: {TEXT_PRIMARY};
    font-widget: 600; font-weight: 600; }}

QPushButton#Primary {{ background: {ACCENT}; border: none; border-radius: 8px;
    padding: 11px 24px; font-size: 13.5px; font-weight: 650;
    color: {ON_ACCENT}; }}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: #dcb60e; }}
QPushButton#Primary:disabled {{ background: {CARD_BORDER};
    color: {TEXT_MUTED}; }}

QPushButton#Ghost {{ background: transparent; border: 1px solid {CARD_BORDER};
    border-radius: 8px; padding: 9px 18px; font-size: 13px;
    color: {TEXT_PRIMARY}; }}
QPushButton#Ghost:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#Ghost:disabled {{ color: {TEXT_MUTED}; border-color: {CARD_BORDER}; }}

QFrame#Card {{ background: {CARD_BG}; border: 1px solid {CARD_BORDER};
    border-radius: 12px; }}
QFrame#SideRule {{ background: {CARD_BORDER}; max-height: 1px; border: none; }}

QProgressBar {{ background: {CARD_BORDER}; border: none; border-radius: 6px;
    height: 10px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}

QPlainTextEdit#Log {{ background: {SIDEBAR_BG};
    border: 1px solid {CARD_BORDER}; border-radius: 10px;
    color: {TEXT_PRIMARY}; font-family: Consolas; font-size: 12px; }}
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


def _cursor_shape() -> Any:
    QtCore, _ = load_pyqt6()
    return QtCore.Qt.CursorShape


def _nav_button(text: str) -> Any:
    """A sidebar navigation toggle (checkable, mutually exclusive group)."""
    _, QtWidgets = load_pyqt6()
    button = QtWidgets.QPushButton(text)
    button.setObjectName("Nav")
    button.setCheckable(True)
    button.setCursor(_cursor_shape().PointingHandCursor)
    return button


def build_dashboard(
    config_path: Path,
    *,
    fetch_runner: Callable[..., object],
    today_provider: Callable[[], date] = date.today,
) -> tuple[Any, Any]:
    """Construct the dashboard window. Returns ``(window, app)``.

    ``config_path`` is still accepted for compatibility with tests and
    the CLI, but the app now reads/writes its settings through
    :mod:`lvms_stat.settings_store` under ``%LOCALAPPDATA%``.
    """
    QtCore, QtWidgets = load_pyqt6()
    from lvms_stat.dashboard_state import (
        describe_failure,
        describe_outcome,
        load_unit_statuses,
    )
    from lvms_stat.settings_store import (
        Settings,
        default_settings,
        load_settings,
        save_settings,
        settings_path,
        validate_settings,
    )

    # Once the user has saved setup through the GUI, those files are the
    # single source of truth - everything downstream (dashboard state,
    # fetching, post-processing) just sees a normal config path.
    saved_settings = settings_path()
    effective_config = saved_settings if saved_settings.exists() else Path(config_path)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setStyleSheet(STYLESHEET)

    window = QtWidgets.QWidget()
    window.setWindowTitle("LVMS Statistikk")
    window.setMinimumSize(940, 640)

    shell = QtWidgets.QHBoxLayout(window)
    shell.setContentsMargins(0, 0, 0, 0)
    shell.setSpacing(0)

    # -- left sidebar ---------------------------------------------------
    sidebar = QtWidgets.QFrame()
    sidebar.setFixedWidth(SIDEBAR_WIDTH)
    sidebar.setStyleSheet(f"background: {SIDEBAR_BG};")
    side = QtWidgets.QVBoxLayout(sidebar)
    side.setContentsMargins(16, 20, 16, 16)
    side.setSpacing(6)

    brand_row = QtWidgets.QHBoxLayout()
    brand_dot = QtWidgets.QLabel("●")
    brand_dot.setObjectName("BrandDot")
    brand = QtWidgets.QLabel("LVMS Statistikk")
    brand.setObjectName("Brand")
    brand_row.addWidget(brand_dot)
    brand_row.addSpacing(6)
    brand_row.addWidget(brand)
    brand_row.addStretch(1)
    side.addLayout(brand_row)

    side_sub = QtWidgets.QLabel("Statistikk-pipeline")
    side_sub.setObjectName("Muted")
    side_sub.setIndent(22)
    side.addWidget(side_sub)

    rule = QtWidgets.QFrame()
    rule.setObjectName("SideRule")
    rule.setFixedHeight(1)
    side.addSpacing(12)
    side.addWidget(rule)
    side.addSpacing(8)

    nav_dash = _nav_button("  ▤  Dashbord")
    nav_log = _nav_button("  ≡  Logg")
    nav_setup = _nav_button("  ⚙  Oppsett")
    nav_dash.setChecked(True)
    for btn in (nav_dash, nav_log, nav_setup):
        side.addWidget(btn)

    side.addStretch(1)

    env_label = QtWidgets.QLabel(
        "Innstillingene lagres i\n%LOCALAPPDATA%\\LVMS-STAT."
    )
    env_label.setObjectName("Muted")
    env_label.setWordWrap(True)
    side.addWidget(env_label)

    # -- main column ------------------------------------------------------
    main = QtWidgets.QVBoxLayout()
    main.setContentsMargins(28, 22, 28, 20)
    main.setSpacing(14)
    shell.addWidget(sidebar)
    shell.addLayout(main, stretch=1)

    pages = QtWidgets.QStackedWidget()
    main.addWidget(pages, stretch=1)
    dash_page = QtWidgets.QWidget()
    dash_layout = QtWidgets.QVBoxLayout(dash_page)
    dash_layout.setContentsMargins(0, 0, 0, 0)
    dash_layout.setSpacing(14)
    log_page = QtWidgets.QWidget()
    log_layout = QtWidgets.QVBoxLayout(log_page)
    log_layout.setContentsMargins(0, 0, 0, 0)
    log_layout.setSpacing(10)
    setup_page = QtWidgets.QWidget()
    setup_layout = QtWidgets.QVBoxLayout(setup_page)
    setup_layout.setContentsMargins(0, 0, 0, 0)
    setup_layout.setSpacing(12)
    for page in (dash_page, log_page, setup_page):
        pages.addWidget(page)

    def switch_to(index: int) -> None:
        pages.setCurrentIndex(index)

    nav_dash.clicked.connect(lambda _=False: switch_to(0))
    nav_log.clicked.connect(lambda _=False: switch_to(1))
    nav_setup.clicked.connect(lambda _=False: switch_to(2))

    # header (dashboard page)
    header = QtWidgets.QHBoxLayout()
    titles = QtWidgets.QVBoxLayout()
    title = QtWidgets.QLabel("Dashbord")
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
    refresh_button.setObjectName("Ghost")
    refresh_button.setCursor(_cursor_shape().PointingHandCursor)
    header.addWidget(refresh_button)
    dash_layout.addLayout(header)

    # unit cards grid
    cards_grid = QtWidgets.QGridLayout()
    cards_grid.setSpacing(12)
    dash_layout.addLayout(cards_grid)
    card_widgets: dict[str, dict[str, Any]] = {}

    def make_card(unit: Any, slot: int) -> None:
        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        inner = QtWidgets.QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(8)
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
        run_row = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Hent nå")
        run_button.setObjectName("Primary")
        run_row.addStretch(1)
        run_row.addWidget(run_button)
        inner.addLayout(run_row)
        cards_grid.addWidget(card, slot // 2, slot % 2)
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
    progress.setFixedHeight(10)
    dash_layout.addWidget(progress)

    status_label = QtWidgets.QLabel("")
    status_label.setObjectName("Subtitle")
    status_label.setWordWrap(True)
    dash_layout.addWidget(status_label)
    dash_layout.addStretch(1)

    # log page
    log_head = QtWidgets.QHBoxLayout()
    log_title = QtWidgets.QLabel("Logg")
    log_title.setObjectName("Title")
    log_head.addWidget(log_title)
    log_head.addStretch(1)
    clear_button = QtWidgets.QPushButton("Tøm")
    clear_button.setObjectName("Ghost")
    clear_button.setCursor(_cursor_shape().PointingHandCursor)
    log_head.addWidget(clear_button)
    log_layout.addLayout(log_head)
    log_box = QtWidgets.QPlainTextEdit()
    log_box.setObjectName("Log")
    log_box.setReadOnly(True)
    log_box.setPlaceholderText(
        "Ingen aktivitet ennå - henting og prosessering logges her."
    )
    log_layout.addWidget(log_box, stretch=1)
    clear_button.clicked.connect(log_box.clear)

    # ------------------------------------------------------------------
    # Oppsett page (all in-app configuration)
    # ------------------------------------------------------------------
    setup_head = QtWidgets.QHBoxLayout()
    setup_title = QtWidgets.QLabel("Oppsett")
    setup_title.setObjectName("Title")
    setup_head.addWidget(setup_title)
    setup_head.addStretch(1)
    reload_button = QtWidgets.QPushButton("Last inn på nytt")
    reload_button.setObjectName("Ghost")
    reload_button.setCursor(_cursor_shape().PointingHandCursor)
    setup_head.addWidget(reload_button)
    setup_layout.addLayout(setup_head)

    setup_hint = QtWidgets.QLabel(
        "Alt oppsett gjøres her - ingen JSON-filer å redigere. "
        "Feltene valideres mot det pipelinen faktisk krever når du lagrer."
    )
    setup_hint.setObjectName("Subtitle")
    setup_hint.setWordWrap(True)
    setup_layout.addWidget(setup_hint)

    form_scroll = QtWidgets.QScrollArea()
    form_scroll.setWidgetResizable(True)
    form_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    form_scroll.setStyleSheet("background: transparent;")
    form_host = QtWidgets.QWidget()
    form_host.setStyleSheet("background: transparent;")
    form = QtWidgets.QVBoxLayout(form_host)
    form.setContentsMargins(0, 4, 4, 0)
    form.setSpacing(10)

    def add_field(label: str, tooltip: str = "") -> Any:
        row = QtWidgets.QVBoxLayout()
        caption = QtWidgets.QLabel(label)
        caption.setObjectName("Muted")
        edit = QtWidgets.QLineEdit()
        if tooltip:
            edit.setToolTip(tooltip)
        row.addWidget(caption)
        row.addWidget(edit)
        form.addLayout(row)
        return edit

    field_landing = add_field(
        "LVMS-adresse",
        "Full HTTPS-adressen til LVMS, f.eks. https://lvms.sykehus.no/clims",
    )
    field_root = add_field(
        "Statistikk-rot (K:\\)",
        "Mappen der manifest.sqlite og raa/arkiv/prosessert ligger.",
    )

    folders_card = QtWidgets.QFrame()
    folders_card.setObjectName("Card")
    folders_inner = QtWidgets.QVBoxLayout(folders_card)
    folders_inner.setContentsMargins(16, 12, 16, 12)
    folders_inner.setSpacing(8)
    folders_title = QtWidgets.QLabel("Mapper")
    folders_title.setObjectName("CardTitle")
    folders_inner.addWidget(folders_title)

    root_caption = QtWidgets.QLabel(
        "Statistikk-rot - mappen alle data lagres i (f.eks. K:\\... "
        "\\Statistikk). Opprettes automatisk ved første henting."
    )
    root_caption.setObjectName("Muted")
    root_caption.setWordWrap(True)
    field_root.setToolTip(
        "Under denne mappen opprettes <enhet>/raa (rå-CSV-er), "
        "<enhet>/merged og <enhet>/prosessert (antall.csv + "
        "resultater.csv for Power BI) samt manifest.sqlite."
    )

    prof_caption = QtWidgets.QLabel(
        "Edge-profilmappe - Edge-profilen appen bruker (kan være tom, "
        "opprettes automatisk). Ikke din vanlige Edge-profil."
    )
    prof_caption.setObjectName("Muted")
    prof_caption.setWordWrap(True)
    field_profile = QtWidgets.QLineEdit()
    dl_caption = QtWidgets.QLabel(
        "Midlertidig nedlastingsmappe - CSV-filene havner her først "
        "før de arkiveres automatisk. Du trenger normalt ikke å se her."
    )
    dl_caption.setObjectName("Muted")
    dl_caption.setWordWrap(True)
    field_downloads = QtWidgets.QLineEdit()
    folders_inner.addWidget(root_caption)
    folders_inner.addWidget(field_root)
    folders_inner.addWidget(prof_caption)
    folders_inner.addWidget(field_profile)
    folders_inner.addWidget(dl_caption)
    folders_inner.addWidget(field_downloads)
    form.addWidget(folders_card)

    units_card = QtWidgets.QFrame()
    units_card.setObjectName("Card")
    units_inner = QtWidgets.QVBoxLayout(units_card)
    units_inner.setContentsMargins(16, 12, 16, 12)
    units_inner.setSpacing(8)
    units_title = QtWidgets.QLabel("Enheter")
    units_title.setObjectName("CardTitle")
    units_inner.addWidget(units_title)
    field_hemato_codes = QtWidgets.QPlainTextEdit()
    field_solide_codes = QtWidgets.QPlainTextEdit()
    for editor in (field_hemato_codes, field_solide_codes):
        editor.setMinimumHeight(120)
    for caption, editor in (
        (
            "Hemato - analysekoder, rapport 1+2 (én per linje, "
            "ekstraksjon har sin egen liste)",
            field_hemato_codes,
        ),
        (
            "Solide - analysekoder, rapport 1+2 (én per linje, "
            "ekstraksjon har sin egen liste)",
            field_solide_codes,
        ),
    ):
        label = QtWidgets.QLabel(caption)
        label.setObjectName("Muted")
        units_inner.addWidget(label)
        units_inner.addWidget(editor)
    units_note = QtWidgets.QLabel(
        "Analysekodene styres per rapport (bestilt / besvart / "
        "ekstraksjon) og følger med enhetene fra spesifikasjonen - "
        "normalt skal de ikke endres her."
    )
    units_note.setObjectName("Muted")
    units_note.setWordWrap(True)
    units_inner.addWidget(units_note)
    form.addWidget(units_card)

    save_bar = QtWidgets.QHBoxLayout()
    save_status = QtWidgets.QLabel("")
    save_status.setObjectName("Subtitle")
    save_status.setWordWrap(True)
    save_button = QtWidgets.QPushButton("Lagre oppsett")
    save_button.setObjectName("Primary")
    save_button.setCursor(_cursor_shape().PointingHandCursor)
    # Save bar is pinned OUTSIDE the scroll area so the result of the
    # click (success or error) is always visible without scrolling.
    save_bar.addWidget(save_status, stretch=1)
    save_bar.addWidget(save_button)

    form_scroll.setWidget(form_host)
    setup_layout.addWidget(form_scroll, stretch=1)
    setup_layout.addLayout(save_bar)

    def fill_form(settings: Any) -> None:
        field_landing.setText(settings.landing_url)
        field_root.setText(settings.statistics_root)
        field_profile.setText(settings.profile_directory)
        field_downloads.setText(settings.download_directory)
        hemato = settings.units.get("hemato", {})
        solide = settings.units.get("solide", {})
        field_hemato_codes.setPlainText(
            "\n".join(hemato.get("analysis_codes", []))
        )
        field_solide_codes.setPlainText(
            "\n".join(solide.get("analysis_codes", []))
        )

    def collect_form() -> Any:
        settings = default_settings()

        def codes_from(editor: Any, fallback: list[str]) -> list[str]:
            lines = [
                line.strip()
                for line in editor.toPlainText().splitlines()
                if line.strip()
            ]
            return lines or fallback

        settings.units["hemato"]["analysis_codes"] = codes_from(
            field_hemato_codes,
            settings.units["hemato"]["analysis_codes"],
        )
        settings.units["solide"]["analysis_codes"] = codes_from(
            field_solide_codes,
            settings.units["solide"]["analysis_codes"],
        )
        settings.landing_url = field_landing.text().strip()
        settings.statistics_root = field_root.text().strip()
        settings.profile_directory = field_profile.text().strip()
        settings.download_directory = field_downloads.text().strip()
        return settings

    def refresh_setup_status() -> None:
        from lvms_stat.settings_store import settings_path

        if settings_path().exists():
            save_status.setText("Lagret oppsett i bruk.")
        else:
            save_status.setText(
                "Ikke satt opp ennå - fyll ut og lagre for å ta i bruk appen."
            )

    def load_into_form() -> None:
        from lvms_stat.settings_store import (
            Settings as _Settings,
            default_settings,
            load_settings,
        )

        try:
            settings: Any = load_settings()
        except Exception:
            settings = default_settings()
        fill_form(settings)
        refresh_setup_status()

    reload_button.clicked.connect(load_into_form)

    def on_save() -> None:
        from lvms_stat.settings_store import SettingsError, save_settings

        try:
            path = save_settings(collect_form())
        except Exception as exc:
            message = str(exc) if str(exc).strip() else repr(exc)
            save_status.setText(f"❌ Kunne ikke lagre: {message}")
            save_status.setStyleSheet("color: #ff9d8f;")
            show_status(f"Kunne ikke lagre oppsettet: {message}")
            return
        save_status.setStyleSheet("")  # back to default subtitle colour
        save_status.setText(f"Lagret ✓ ({path})")
        show_status("Nytt oppsett lagret - klart til å hente.")
        refresh_cards()

    save_button.clicked.connect(on_save)

    # -- events / state rendering -----------------------------------------

    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def post(kind: str, value: Any = None) -> None:
        events.put((kind, value))

    def show_status(message: str) -> None:
        """Route user-facing messages: visible on the dashboard too."""
        status_label.setText(str(message))
        if message.strip():
            log_box.appendPlainText(str(message))

    def refresh_cards() -> None:
        from lvms_stat.dashboard_state import RootUnavailableError
        from lvms_stat.settings_store import settings_path as _sp

        try:
            statuses = load_unit_statuses(
                effective_config, today=today_provider()
            )
        except RootUnavailableError as exc:
            # Setup is valid - only the storage location is unreachable
            # (e.g. K: not mounted yet). Still show the unit cards, with
            # manifest-dependent info marked as unknown.
            card_widgets.clear()
            while cards_grid.count():
                item = cards_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            try:
                from lvms_stat.settings_store import load_settings as _load

                offline_units = _load().units
            except Exception:
                offline_units = {}

            class _OfflineUnit:
                """Duck-typed Unit for cards when the manifest is away."""

                def __init__(self, key: str, cfg: dict) -> None:
                    self.key = key
                    self.label = str(cfg.get("label", key))
                    self._reports = cfg.get("reports", []) or []

            for slot, (unit_key, unit_cfg) in enumerate(
                sorted(offline_units.items())
            ):
                make_card(_OfflineUnit(unit_key, unit_cfg), slot)
                widgets = card_widgets[unit_key]
                widgets["badge"].setText("● Klar - manifest utilgjengelig")
                widgets["badge"].setStyleSheet(f"color: {WARN_AMBER};")
                codes = unit_cfg.get("analysis_codes", []) or []
                lines = [
                    f"{report.get('report_id', '?')} - sist hentet: ukjent"
                    for report in unit_cfg.get("reports", [])
                    if isinstance(report, dict)
                ]
                lines.append(f"{len(codes)} analysekoder")
                widgets["detail"].setText("\n".join(lines))
            subtitle.setText(
                f"⚠ {exc} - oppsettet er lagret og klart, men mappen er "
                "ikke tilgjengelig (f.eks. K: er ikke koblet til enda)."
            )
            return
        except Exception:
            # Genuinely unusable setup: no saved settings at all, or a
            # config that fails validation.
            if not _sp().exists():
                message = (
                    "Appen er ikke satt opp - åpne «Oppsett» i menyen."
                )
            else:
                message = (
                    "Kunne ikke lese oppsettet - åpne «Oppsett» og trykk "
                    "«Lagre oppsett» på nytt."
                )
            card_widgets.clear()
            while cards_grid.count():
                item = cards_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            subtitle.setText(message)
            return
        while cards_grid.count():
            item = cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        card_widgets.clear()
        stale_total = 0
        for slot, unit in enumerate(statuses):
            make_card(unit, slot)
            widgets = card_widgets[unit.key]
            stale = [r for r in unit.reports if r.needs_fetch]
            stale_total += len(stale)
            if not stale:
                widgets["badge"].setText("● Oppdatert")
                widgets["badge"].setStyleSheet(f"color: {OK_GREEN};")
                widgets["run"].setEnabled(True)
            else:
                widgets["badge"].setText(f"● {len(stale)} må hentes")
                widgets["badge"].setStyleSheet(f"color: {WARN_AMBER};")
            lines = []
            for report in unit.reports:
                lines.append(f"{report.report_id} - {report.headline}")
            lines.append(f"{unit.analysis_code_count} analysekoder")
            widgets["detail"].setText("\n".join(lines))
        if stale_total:
            summary = f"{stale_total} rapporter venter på henting."
        elif statuses:
            summary = "Alt er oppdatert."
        else:
            summary = ""
        if summary:
            subtitle.setText(summary)

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
        log_box.appendPlainText(f"— starter henting for «{unit_key}» —")
        pages.setCurrentIndex(0)
        show_status("Kjører - åpner LVMS …")

        def worker() -> None:
            def on_status(message: str) -> None:
                post("log", message)

            def on_progress(current: int, total: int) -> None:
                post("progress", (current, total))

            def on_failure(stage: str) -> None:
                post("log", f"stopp ved {stage}")

            try:
                outcome = fetch_runner(
                    effective_config,
                    unit_key=unit_key,
                    output=log_stream(),
                    progress=on_progress,
                    failure=on_failure,
                )
                post("outcome", outcome)
                # Make the file locations explicit - the user must be
                # able to find the raw and processed CSVs.
                try:
                    from lvms_stat.settings_store import load_settings

                    settings_now = load_settings()
                    unit_root = (
                        Path(settings_now.statistics_root) / unit_key
                    )
                    post(
                        "log",
                        "Filer: rå-CSV-er arkiveres under "
                        f"{unit_root / 'raa'}",
                    )
                    post(
                        "log",
                        "Filer: prosesserte filer for Power BI i "
                        f"{unit_root / 'prosessert'} (antall.csv, "
                        "resultater.csv)",
                    )
                except Exception:
                    pass
                if getattr(outcome, "downloaded", ()) or getattr(
                    outcome, "archived", ()
                ):
                    from lvms_stat.scheduled import _process_after_fetch

                    _process_after_fetch(effective_config, unit_key, log_stream())
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
        refresh_button.setEnabled(True)
        refresh_cards()

    def finish_failure(error: Exception) -> None:
        running_key[0] = None
        progress.setVisible(False)
        status_label.setText(describe_failure(error))
        refresh_button.setEnabled(True)
        refresh_cards()

    def poll_events() -> None:
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                return
            if kind == "status":
                show_status(str(value))
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
    load_into_form()

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
