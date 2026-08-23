"""Headless scheduled run for the statistics pipeline.

``run_scheduled`` is the entry point for Windows Task Scheduler: it
fetches every configured unit incrementally, archives to the share,
refreshes ``Prosessert/*.csv`` for Power BI and exits. No GUI, no
prompts - safe to run unattended.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TextIO

from lvms_stat.dashboard_state import describe_failure, describe_outcome
from lvms_stat.fetch_orchestrator import (
    FetchOrchestrationError,
    FetchOutcome,
    run_incremental_fetch,
)
from lvms_stat.post_processing import process_unit
from lvms_stat.settings_store import load_effective_units

Fetcher = Callable[..., FetchOutcome]


def _find_lookup(
    config_path: Path,
    statistics_root: Path,
    *,
    unit_key: str | None = None,
) -> Path | None:
    """Find Analyse_lookup.xlsx in likely places (first hit wins).

    Order: unit folder under the statistics root (e.g. Solide/ has its
    own lookup), config directory, statistics root, repository root, and
    finally the Downloads/Statistikk folder where the R era kept it.
    Any of these can be a symlink/copy on the work PC.
    """
    candidates = []
    if unit_key:
        candidates.append(statistics_root / unit_key / "Analyse_lookup.xlsx")
    candidates += [
        config_path.with_name("Analyse_lookup.xlsx"),
        statistics_root / "Analyse_lookup.xlsx",
        Path(__file__).resolve().parents[2] / "Analyse_lookup.xlsx",
        Path.home() / "Downloads" / "Statistikk" / "Analyse_lookup.xlsx",
        (
            Path.home() / "Downloads" / "Statistikk" / "Solide"
            / "Analyse_lookup.xlsx"
        ),
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _process_after_fetch(
    config_path: Path,
    unit_key: str,
    stream: TextIO | None,
) -> None:
    """Refresh Prosessert/*.csv after a successful fetch."""
    try:
        units = {unit.key: unit for unit in load_effective_units(config_path)}
        unit = units[unit_key]
        statistics_root_str = None
        try:
            from lvms_stat.manifest import load_statistics_settings
            statistics_root_str = load_statistics_settings(config_path)
        except Exception:
            pass
        if statistics_root_str is None:
            return
        root = Path(statistics_root_str) / unit_key
        report_ids = {
            report.job_key: report.report_id for report in unit.reports
        }
        lookup_path = _find_lookup(
            config_path, Path(statistics_root_str), unit_key=unit_key
        )
        if lookup_path is None:
            if stream is not None:
                stream.write(
                    f"[{unit_key}] Analyse_lookup.xlsx ikke funnet - "
                    "prosessert ble ikke oppdatert\n"
                )
            return
        outcome = process_unit(
            root,
            lookup_path,
            report_ids,
            profile=getattr(unit, "profile", "hemato"),
        )
        if stream is not None and (
            outcome.antall_rows or outcome.resultater_rows
        ):
            stream.write(
                f"[{unit_key}] prosessert oppdatert: "
                f"{outcome.resultater_rows} resultater, "
                f"{outcome.antall_rows} antall-rader -> "
                f"{outcome.output_dir}\n"
            )
    except Exception as exc:
        # processing failure must never fail the fetch run itself;
        # raw data is already safely archived.
        if stream is not None:
            stream.write(f"[{unit_key}] prosessering feilet: {exc}\n")


def run_scheduled(
    config_path: Path,
    *,
    unit_keys: tuple[str, ...] | None = None,
    today: date | None = None,
    output: TextIO | None = None,
    fetcher: Fetcher = run_incremental_fetch,
    skip_processing: bool = False,
) -> int:
    """Fetch all units incrementally; return a process exit code."""
    stream = output
    day = today or date.today()
    if unit_keys is None:
        try:
            unit_keys = tuple(
                unit.key for unit in load_effective_units(config_path)
            )
        except Exception as exc:
            if stream is not None:
                stream.write(f"Oppsett kunne ikke leses: {describe_failure(exc)}\n")
            return 2

    exit_code = 0
    for unit_key in unit_keys:
        try:
            outcome = fetcher(
                config_path,
                unit_key=unit_key,
                today=day,
                output=stream,
            )
        except FetchOrchestrationError as exc:
            if stream is not None:
                stream.write(f"[{unit_key}] {describe_failure(exc)}\n")
            exit_code = 1
            continue
        except Exception as exc:
            if stream is not None:
                stream.write(f"[{unit_key}] {describe_failure(exc)}\n")
            exit_code = 1
            continue
        if stream is not None:
            stream.write(f"[{unit_key}] {describe_outcome(outcome)}\n")
        if not skip_processing:
            try:
                _process_after_fetch(config_path, unit_key, stream)
            except Exception as exc:
                # raw data is already safely archived - a processing
                # failure must never fail the fetch run itself.
                if stream is not None:
                    stream.write(f"[{unit_key}] prosessering feilet: {exc}\n")
    return exit_code
