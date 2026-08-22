"""One-call incremental fetch orchestration.

``run_incremental_fetch`` is the single entry point the GUI and a
scheduled run use:

1. plan the next intervals from the manifest
2. build concrete report jobs
3. run them through the existing Edge/CDP batch runner
4. archive every finished CSV to the statistics share and record runs

The LVMS batch workflow itself is untouched; this module only decides
*what* to fetch and files the results away afterwards.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO

from lvms_stat.archive import ArchiveError, archive_downloaded_file
from lvms_stat.batch_runner import BatchRunnerDependencies, run_report_batch
from lvms_stat.incremental import IncrementalPlanError, plan_unit
from lvms_stat.job_builder import (
    JobBuildError,
    UnitTemplate,
    build_jobs_for_unit,
)
from lvms_stat.manifest import ManifestStore, load_statistics_settings
from lvms_stat.report_job import ReportJob, batch_filename, select_batch_jobs
from lvms_stat.units import Unit, UnitsConfigError, load_units


class FetchOrchestrationError(ValueError):
    """The incremental fetch could not be planned or completed."""


@dataclass(frozen=True)
class FetchOutcome:
    """What one incremental fetch actually did."""

    unit_key: str
    downloaded: tuple[str, ...]
    archived: tuple[str, ...]
    up_to_date: tuple[str, ...]


def _statistics_root(config_path: Path) -> Path:
    try:
        return load_statistics_settings(config_path)
    except Exception as exc:
        raise FetchOrchestrationError(str(exc)) from exc


def _load_unit(config_path: Path, unit_key: str) -> Unit:
    try:
        units = load_units(config_path.with_name("units.json"))
    except UnitsConfigError as exc:
        raise FetchOrchestrationError(str(exc)) from exc
    for unit in units:
        if unit.key == unit_key:
            return unit
    raise FetchOrchestrationError("unit was not found in the configuration")


def run_incremental_fetch(
    config_path: Path,
    *,
    unit_key: str,
    today: date | None = None,
    repository_root: Path | None = None,
    dependencies: BatchRunnerDependencies | None = None,
    output: TextIO | None = None,
    timeout_seconds: float = 600,
    progress: Callable[[int, int], None] | None = None,
    failure: Callable[[str], None] | None = None,
) -> FetchOutcome:
    """Plan, fetch and archive the next incremental window for one unit."""
    stream = output or io.StringIO()
    root = repository_root or Path(__file__).resolve().parents[2]
    day = today or date.today()
    statistics_root = _statistics_root(config_path)
    unit = _load_unit(config_path, unit_key)

    try:
        plan = plan_unit(unit, statistics_root=statistics_root, today=day)
    except IncrementalPlanError as exc:
        raise FetchOrchestrationError(str(exc)) from exc

    if not plan.fetches:
        return FetchOutcome(
            unit_key=unit.key,
            downloaded=(),
            archived=(),
            up_to_date=plan.up_to_date,
        )

    template = UnitTemplate(unit_key=unit.key)
    try:
        jobs = build_jobs_for_unit(
            plan.fetches,
            analysis_codes=unit.analysis_codes,
            template=template,
        )
    except JobBuildError as exc:
        raise FetchOrchestrationError(str(exc)) from exc

    jobs_path = config_path.with_name(f"jobs.generated-{unit.key}.json")
    _write_generated_jobs(jobs_path, jobs)

    job_keys = tuple(job.job_key for job in jobs)
    # job keys repeat across reports of one unit (ordered/answered/...),
    # so select by position instead: run_report_batch needs distinct keys.
    result = _run_positional_batch(
        config_path,
        jobs_path,
        jobs,
        repository_root=root,
        dependencies=dependencies,
        output=stream,
        timeout_seconds=timeout_seconds,
        progress=progress,
        failure=failure,
    )
    if result != 0:
        raise FetchOrchestrationError(
            "rapportkjøringen stoppet - se status i appen"
        )

    return _archive_results(
        stream,
        statistics_root=statistics_root,
        unit=unit,
        jobs=jobs,
        up_to_date=plan.up_to_date,
    )


def _write_generated_jobs(jobs_path: Path, jobs: tuple[ReportJob, ...]) -> None:
    import json

    payload = {
        "jobs": [
            {
                "job_key": f"{job.job_key}__{job.output_stem}",
                "report_type": job.report_type,
                "category": job.category,
                "report_id": job.report_id,
                "analysis_codes": list(job.analysis_codes),
                "created_from": job.interval.created_from.strftime("%d.%m.%Y"),
                "created_to": job.interval.created_to.strftime("%d.%m.%Y"),
                "output_stem": job.output_stem,
            }
            for job in jobs
        ]
    }
    try:
        jobs_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        raise FetchOrchestrationError(
            "the generated jobs file could not be written"
        ) from exc


def _run_positional_batch(
    config_path: Path,
    jobs_path: Path,
    jobs: tuple[ReportJob, ...],
    **kwargs: object,
) -> int:
    """Run the generated jobs even when their keys are not distinct.

    ``run_report_batch`` selects jobs by key; generated jobs may share
    keys (ordered/answered/extraction per report id), so each job gets a
    unique synthetic key in the written file first.
    """
    unique_keys = tuple(
        f"{job.job_key}__{job.output_stem}" for job in jobs
    )
    return run_report_batch(
        config_path,
        jobs_path,
        unique_keys,
        **kwargs,  # type: ignore[arg-type]
    )


def _archive_results(
    stream: TextIO,
    *,
    statistics_root: Path,
    unit: Unit,
    jobs: tuple[ReportJob, ...],
    up_to_date: tuple[str, ...],
) -> FetchOutcome:
    store = ManifestStore(statistics_root / "manifest.sqlite")
    download_directory = Path(__file__).resolve().parents[2] / "rådata"
    stem_to_job_key = {job.output_stem: job.job_key for job in jobs}
    downloaded: list[str] = []
    archived: list[str] = []
    for item in sorted(download_directory.glob("*.csv")):
        match = item.name.split("__", 1)
        stem = match[0] if match else ""
        if stem not in stem_to_job_key:
            continue
        filename = item.name
        if store.has_filename(unit.key, filename):
            continue  # already archived in an earlier attempt
        try:
            outcome = archive_downloaded_file(
                item,
                statistics_root=statistics_root,
                unit=unit.key,
                job_key=stem_to_job_key[stem],
            )
        except ArchiveError as exc:
            stream.write(f"Archiving failed for {filename}: {exc}\n")
            raise FetchOrchestrationError(str(exc)) from exc
        downloaded.append(filename)
        archived.append(str(outcome.archived_path))
    return FetchOutcome(
        unit_key=unit.key,
        downloaded=tuple(downloaded),
        archived=tuple(archived),
        up_to_date=up_to_date,
    )
