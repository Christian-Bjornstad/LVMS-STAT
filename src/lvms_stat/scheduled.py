"""Headless scheduled run for the statistics pipeline.

``run_scheduled`` is the entry point for Windows Task Scheduler: it
fetches every configured unit incrementally, archives to the share and
exits. No GUI, no prompts - safe to run unattended.
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

Fetcher = Callable[..., FetchOutcome]


def run_scheduled(
    config_path: Path,
    *,
    unit_keys: tuple[str, ...] | None = None,
    today: date | None = None,
    output: TextIO | None = None,
    fetcher: Fetcher = run_incremental_fetch,
) -> int:
    """Fetch all units incrementally; return a process exit code."""
    stream = output
    day = today or date.today()
    if unit_keys is None:
        try:
            from lvms_stat.units import load_units

            unit_keys = tuple(
                unit.key for unit in load_units(config_path.with_name("units.json"))
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
    return exit_code
