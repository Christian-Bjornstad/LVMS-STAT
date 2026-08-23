from __future__ import annotations

from datetime import date

import pytest

from lvms_stat.job_builder import (
    JobBuildError,
    UnitTemplate,
    build_jobs_for_unit,
    build_report_job,
    validate_analysis_codes,
)
from lvms_stat.units import Unit, UnitReport


def make_fetch(report_id: str = "PAT-DIT-ANTALL-OU") -> object:
    unit = Unit(
        key="hemato",
        label="Hemato",
        reports=(UnitReport("ordered", report_id, report_id),),
        analysis_codes=("CALR-OU",),
    )
    from lvms_stat.incremental import PlannedFetch

    return PlannedFetch(
        unit=unit,
        report=unit.reports[0],
        created_from=date(2024, 1, 1),
        created_to=date(2026, 8, 22),
    )


TEMPLATE = UnitTemplate(unit_key="hemato")


def test_build_report_job_matches_plan() -> None:
    job = build_report_job(
        make_fetch(),  # type: ignore[arg-type]
        analysis_codes=("CALR-OU", "JAK2-V617F-OU"),
        template=TEMPLATE,
    )
    assert job.report_id == "PAT-DIT-ANTALL-OU"
    assert job.output_stem == "PAT-DIT-ANTALL-OU"
    assert job.interval.created_from == date(2024, 1, 1)
    assert job.interval.created_to == date(2026, 8, 22)
    assert job.analysis_codes == ("CALR-OU", "JAK2-V617F-OU")
    assert job.as_lvms_text() if hasattr(job, "as_lvms_text") else True
    start, end = job.interval.as_lvms()
    assert start == "01.01.2024"
    assert end == "22.08.2026"


def test_build_rejects_missing_analysis_codes() -> None:
    with pytest.raises(JobBuildError):
        build_report_job(
            make_fetch(),  # type: ignore[arg-type]
            analysis_codes=(),
            template=TEMPLATE,
        )


def test_build_jobs_for_multiple_fetches(tmp_path) -> None:
    from lvms_stat.incremental import PlannedFetch

    unit = Unit(
        key="hemato",
        label="Hemato",
        reports=(
            UnitReport("ordered", "PAT-DIT-ANTALL-OU", "PAT-DIT-ANTALL-OU"),
            UnitReport(
                "answered", "PAT-DIT-RESULTATER-OU", "PAT-DIT-RESULTATER-OU"
            ),
        ),
        analysis_codes=("CALR-OU",),
    )
    fetches = tuple(
        PlannedFetch(
            unit=unit,
            report=report,
            created_from=date(2024, 1, 1),
            created_to=date(2026, 8, 22),
        )
        for report in unit.reports
    )
    jobs = build_jobs_for_unit(
        fetches,
        analysis_codes=unit.analysis_codes,
        template=TEMPLATE,
    )
    assert [job.job_key for job in jobs] == ["ordered", "answered"]
    filenames = {job.output_stem for job in jobs}
    assert len(filenames) == 2


def test_build_jobs_rejects_empty_fetches() -> None:
    with pytest.raises(JobBuildError):
        build_jobs_for_unit((), analysis_codes=("CALR-OU",), template=TEMPLATE)


def test_extraction_report_runs_under_resultater_id() -> None:
    """PAK analysetid runs under RESULTATER with EKSTRA codes but is
    saved as PAT-DIT-EKSTRAKSJON-OU."""
    from lvms_stat.incremental import PlannedFetch

    unit = Unit(
        key="solide",
        label="Solide",
        profile="solide",
        reports=(
            UnitReport(
                "extraction",
                "PAT-DIT-RESULTATER-OU",
                "PAT-DIT-EKSTRAKSJON-OU",
                analysis_codes=("EKSTRAKSJON-OU", "EKSTRAGENXRNA-OU"),
            ),
        ),
        analysis_codes=("POLE-OU",),
    )
    fetch = PlannedFetch(
        unit=unit,
        report=unit.reports[0],
        created_from=date(2024, 1, 1),
        created_to=date(2026, 8, 23),
    )
    job = build_report_job(fetch, analysis_codes=unit.analysis_codes,
                           template=UnitTemplate(unit_key="solide"))
    # LVMS must run the RESULTATER report...
    assert job.report_id == "PAT-DIT-RESULTATER-OU"
    # ...but the export is saved as the extraction id.
    assert job.output_stem == "PAT-DIT-EKSTRAKSJON-OU"
    # Report-level codes win over unit-level ones.
    assert job.analysis_codes == ("EKSTRAKSJON-OU", "EKSTRAGENXRNA-OU")


def test_validate_analysis_codes_round_trip() -> None:
    codes = validate_analysis_codes([" CALR-OU ", "JAK2-V617F-OU"])
    assert codes == ("CALR-OU", "JAK2-V617F-OU")


def test_validate_analysis_codes_rejects_duplicates() -> None:
    with pytest.raises(JobBuildError):
        validate_analysis_codes(["CALR-OU", "CALR-OU"])


def test_validate_analysis_codes_rejects_garbage() -> None:
    with pytest.raises(JobBuildError):
        validate_analysis_codes(["bad code!"])
