"""Pure view-model logic for the statistics dashboard.

Everything the GUI displays is computed here without any Qt imports,
so it can be tested headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lvms_stat.fetch_orchestrator import FetchOrchestrationError
from lvms_stat.manifest import ManifestStore, load_statistics_settings
from lvms_stat.settings_store import load_effective_units
from lvms_stat.units import Unit, UnitReport


class DashboardStateError(ValueError):
    """The dashboard state could not be computed."""


@dataclass(frozen=True)
class ReportStatus:
    """Display state for one report of one unit."""

    job_key: str
    report_id: str
    last_created_to: date | None
    needs_fetch: bool

    @property
    def headline(self) -> str:
        if self.last_created_to is None:
            return "Aldri hentet - første kjøring henter fra 01.01.2024"
        return f"Oppdatert til {self.last_created_to.strftime('%d.%m.%Y')}"

    @property
    def state(self) -> str:
        return "klar" if self.needs_fetch else "oppdatert"


@dataclass(frozen=True)
class UnitStatus:
    """Display state for one unit."""

    key: str
    label: str
    analysis_code_count: int
    reports: tuple[ReportStatus, ...]

    @property
    def needs_fetch(self) -> bool:
        return any(report.needs_fetch for report in self.reports)


def load_unit_statuses(config_path: Path, *, today: date) -> tuple[UnitStatus, ...]:
    """Compute the display state for every configured unit."""
    statistics_root = _statistics_root(config_path)
    try:
        units = load_effective_units(config_path)
    except Exception as exc:
        raise DashboardStateError(str(exc)) from exc
    store = ManifestStore(statistics_root / "manifest.sqlite")
    statuses: list[UnitStatus] = []
    try:
        for unit in units:
            statuses.append(_unit_status(store, unit, today=today))
    except OSError as exc:
        # The setup itself is valid - only the storage location cannot be
        # reached (e.g. K: not mounted yet). Distinct from "not set up".
        raise RootUnavailableError(
            f"Statistikk-mappen kan ikke nås: {statistics_root}"
        ) from exc
    return tuple(statuses)


class RootUnavailableError(DashboardStateError):
    """Setup is saved and valid, but the statistics root is unreachable."""


def _statistics_root(config_path: Path) -> Path:
    try:
        return load_statistics_settings(config_path)
    except Exception as exc:
        raise DashboardStateError(str(exc)) from exc


def _unit_status(store: ManifestStore, unit: Unit, *, today: date) -> UnitStatus:
    reports = []
    for item in unit.reports:
        assert isinstance(item, UnitReport)
        last_to = store.last_completed_to(unit.key, item.report_id)
        needs = last_to is None or last_to < today
        reports.append(
            ReportStatus(
                job_key=item.job_key,
                report_id=item.report_id,
                last_created_to=last_to,
                needs_fetch=needs,
            )
        )
    return UnitStatus(
        key=unit.key,
        label=unit.label,
        analysis_code_count=len(unit.analysis_codes),
        reports=tuple(reports),
    )


def describe_outcome(outcome: object) -> str:
    """Human summary of one FetchOutcome."""
    downloaded = len(getattr(outcome, "downloaded", ()) or ())
    up_to_date = getattr(outcome, "up_to_date", ()) or ()
    if downloaded == 0 and not up_to_date:
        return "Ingen nye data ble hentet."
    parts: list[str] = []
    if downloaded:
        parts.append(f"{downloaded} rapporter hentet og arkivert")
    if up_to_date:
        parts.append(
            f"{len(up_to_date)} rapporter var allerede oppdaterte"
        )
    return "Ferdig - " + ", ".join(parts) + "."


def describe_failure(error: Exception) -> str:
    if isinstance(error, FetchOrchestrationError):
        return str(error)
    return "Uventet feil under kjøringen."
