"""Unit (device group) configuration for the statistics pipeline.

A unit is one clinical area (hemato, solide, ...) with its own report
IDs. The unit configuration is data, not code: adding a new unit means
editing ``units.json`` next to the app config, nothing else.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from lvms_stat.report_job import (
    KEY_PATTERN,
    OUTPUT_STEM_PATTERN,
    ReportJobError,
)


class UnitsConfigError(ValueError):
    """The units configuration is missing or invalid."""


@dataclass(frozen=True)
class UnitReport:
    """One tracked LVMS report within one unit."""

    job_key: str
    report_id: str


@dataclass(frozen=True)
class Unit:
    """One clinical area with its reports."""

    key: str
    label: str
    reports: tuple[UnitReport, ...]

    def report_by_key(self, job_key: str) -> UnitReport:
        for report in self.reports:
            if report.job_key == job_key:
                return report
        raise UnitsConfigError("report job was not found")


def _unit_key(raw_key: str) -> str:
    text = raw_key.strip()
    if not KEY_PATTERN.fullmatch(text) or len(text) > 80:
        raise UnitsConfigError("unit key is invalid")
    return text.lower()


def _label(raw: Mapping[str, object], fallback: str) -> str:
    value = raw.get("label")
    if not isinstance(value, str) or not value.strip():
        return fallback
    return value.strip()[:120]


def _reports(raw: Mapping[str, object]) -> tuple[UnitReport, ...]:
    items = raw.get("reports")
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise UnitsConfigError("unit reports list is invalid")
    reports: list[UnitReport] = []
    keys: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise UnitsConfigError("unit report is invalid")
        job_key = item.get("job_key")
        report_id = item.get("report_id")
        if not isinstance(job_key, str) or len(job_key) > 80:
            raise UnitsConfigError("unit report job key is invalid")
        if (
            not isinstance(report_id, str)
            or not OUTPUT_STEM_PATTERN.fullmatch(report_id)
        ):
            raise UnitsConfigError("unit report id is invalid")
        if job_key in keys:
            raise UnitsConfigError("unit report job keys contain duplicates")
        keys.add(job_key)
        reports.append(UnitReport(job_key=job_key, report_id=report_id))
    return tuple(reports)


def validate_units(raw: object) -> tuple[Unit, ...]:
    if not isinstance(raw, dict) or not isinstance(raw.get("units"), dict):
        raise UnitsConfigError("units configuration must contain a units object")
    raw_units = raw["units"]
    if not 1 <= len(raw_units) <= 20:
        raise UnitsConfigError("units count is invalid")
    units: list[Unit] = []
    seen: set[str] = set()
    for raw_key, raw_unit in raw_units.items():
        key = _unit_key(str(raw_key))
        if key in seen:
            raise UnitsConfigError("unit keys contain duplicates")
        seen.add(key)
        if not isinstance(raw_unit, dict):
            raise UnitsConfigError("unit is invalid")
        units.append(
            Unit(
                key=key,
                label=_label(raw_unit, key),
                reports=_reports(raw_unit),
            )
        )
    return tuple(units)


def load_units(path: Path) -> tuple[Unit, ...]:
    """Load and validate the units configuration file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise UnitsConfigError("units configuration could not be read") from exc
    except json.JSONDecodeError as exc:
        raise UnitsConfigError("units configuration is invalid JSON") from exc
    return validate_units(raw)


def default_units_path(config_path: Path) -> Path:
    """Units live next to config.json as units.json."""
    return config_path.with_name("units.json")
