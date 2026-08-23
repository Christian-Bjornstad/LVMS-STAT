"""Regression: one unit's staged CSV must never be consumed as another
unit's result. Reproduces the field report 'solide thinks hemato files
are solide': both units stage identically named exports in the shared
``raadata`` folder, so a leftover hemato file was archived under solide."""

from __future__ import annotations

from pathlib import Path

from lvms_stat.archive import (
    ArchiveError,
    archive_downloaded_file,
    archive_pending_downloads,
)


def _stage(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("a;b\n1;2\n", encoding="cp1252")
    return path


def test_hemato_leftover_cannot_archive_as_solide(tmp_path: Path) -> None:
    staging = tmp_path / "raadata"
    # Hemato ran first and its archive FAILED, so its file is still in
    # the shared staging folder, staged with hemato's unit prefix.
    _stage(
        staging,
        "hemato-PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv",
    )

    root = tmp_path / "Statistikk"
    archived = archive_pending_downloads(
        staging,
        statistics_root=root,
        unit="solide",
        jobs={"PAT-DIT-EKSTRAKSJON-OU": "extraction"},
    )

    assert archived == []  # foreign unit file must be ignored entirely
    assert not (root / "solide" / "raa").exists()


def test_prefixed_file_archives_under_canonical_spec_name(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "raadata"
    source = _stage(
        staging,
        "solide-PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv",
    )
    root = tmp_path / "Statistikk"

    archived_run = archive_downloaded_file(
        source,
        statistics_root=root,
        unit="solide",
        job_key="extraction",
    )

    landed = archived_run.archived_path
    # Canonical spec name on disk, not the staging name:
    assert landed.name == "PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv"
    assert landed.parent == root / "solide" / "raa" / "PAT-DIT-EKSTRAKSJON-OU"
    assert archived_run.record.report_id == "PAT-DIT-EKSTRAKSJON-OU"
    assert archived_run.record.unit == "solide"


def test_direct_archive_refuses_foreign_unit_prefix(tmp_path: Path) -> None:
    staging = tmp_path / "raadata"
    source = _stage(
        staging,
        "hemato-PAT-DIT-ANTALL-OU__2024-01-01__2026-08-23.csv",
    )
    root = tmp_path / "Statistikk"

    try:
        archive_downloaded_file(
            source,
            statistics_root=root,
            unit="solide",
            job_key="ordered",
        )
    except ArchiveError as exc:
        assert "another unit" in str(exc)
    else:
        raise AssertionError("foreign-unit file was archived")


def test_unprefixed_legacy_file_still_archives(tmp_path: Path) -> None:
    staging = tmp_path / "raadata"
    source = _stage(
        staging,
        "PAT-DIT-ANTALL-OU__2024-01-01__2026-08-23.csv",
    )
    root = tmp_path / "Statistikk"

    archived_run = archive_downloaded_file(
        source,
        statistics_root=root,
        unit="hemato",
        job_key="ordered",
    )

    assert (
        archived_run.archived_path.name
        == "PAT-DIT-ANTALL-OU__2024-01-01__2026-08-23.csv"
    )
