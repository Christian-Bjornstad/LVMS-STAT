"""Build concrete ReportJobs from an incremental plan.

The analysis code lists are unit-level templates in units.json (they are
shared by all reports in the unit, exactly like the existing manual jobs
files). This module turns PlannedFetch entries into validated ReportJob
objects ready for run_report_batch.
"""

from __future__ import annotations

from dataclasses import dataclass

from lvms_stat.incremental import PlannedFetch
from lvms_stat.report_job import (
    CODE_PATTERN,
    ReportInterval,
    ReportJob,
)


class JobBuildError(ValueError):
    """A planned fetch could not be turned into a report job."""


@dataclass(frozen=True)
class UnitTemplate:
    """Report type and category shared by every report of one unit."""

    unit_key: str
    report_type: str = "PRODSTAT"
    category: str = "PATOLOGI"


def validate_analysis_codes(raw: object) -> tuple[str, ...]:
    """Validate a raw analysis-codes list from units.json."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
        raise JobBuildError("analysis codes are invalid")
    codes: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not CODE_PATTERN.fullmatch(item.strip()):
            raise JobBuildError("analysis code is invalid")
        code = item.strip()
        if code in codes:
            raise JobBuildError("analysis codes contain duplicates")
        codes.append(code)
    return tuple(codes)


def build_report_job(
    fetch: PlannedFetch,
    *,
    analysis_codes: tuple[str, ...],
    template: UnitTemplate,
) -> ReportJob:
    """Create one validated ReportJob for a planned fetch."""
    if not analysis_codes:
        raise JobBuildError(
            f"{fetch.unit.key}/{fetch.report.report_id}: "
            "analysis_codes is missing"
        )
    return ReportJob(
        job_key=fetch.report.job_key,
        report_type=template.report_type,
        category=template.category,
        report_id=fetch.report.report_id,
        analysis_codes=tuple(analysis_codes),
        interval=ReportInterval(fetch.created_from, fetch.created_to),
        output_stem=fetch.report.report_id,
    )


def build_jobs_for_unit(
    fetches: tuple[PlannedFetch, ...] | list[PlannedFetch],
    *,
    analysis_codes: tuple[str, ...],
    template: UnitTemplate,
) -> tuple[ReportJob, ...]:
    """Create report jobs for every planned fetch of one unit."""
    if not fetches:
        raise JobBuildError("no planned fetches to build jobs from")
    return tuple(
        build_report_job(
            fetch,
            analysis_codes=analysis_codes,
            template=template,
        )
        for fetch in fetches
    )
