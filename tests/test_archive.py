from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lvms_stat.archive import (
    ArchiveError,
    archive_downloaded_file,
    archive_pending_downloads,
    parse_batch_filename,
)
from lvms_stat.manifest import ManifestStore


def make_csv(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text("Sample ID;Analyse\nA;B-OU\n", encoding="utf-8")
    return path


def test_parse_batch_filename_round_trip() -> None:
    record = parse_batch_filename(
        "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv",
        job_key="ordered",
        unit="hemato",
    )
    assert record.report_id == "PAT-DIT-ANTALL-OU"
    assert record.created_from == date(2026, 8, 1)
    assert record.created_to == date(2026, 8, 7)


def test_parse_rejects_plain_names() -> None:
    with pytest.raises(ArchiveError):
        parse_batch_filename("rapport.csv", job_key="ordered", unit="hemato")


def test_archive_moves_file_and_records_run(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    statistics = tmp_path / "K"
    downloads.mkdir()
    source = make_csv(
        downloads, "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv"
    )
    result = archive_downloaded_file(
        source, statistics_root=statistics, unit="hemato", job_key="ordered"
    )
    expected = (
        statistics / "hemato" / "raa" / "PAT-DIT-ANTALL-OU"
        / "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv"
    )
    assert result.archived_path == expected
    assert expected.is_file()
    assert not source.exists()
    store = ManifestStore(statistics / "manifest.sqlite")
    assert store.last_completed_to(
        "hemato", "PAT-DIT-ANTALL-OU"
    ) == date(2026, 8, 7)


def test_archive_refuses_existing_destination(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    statistics = tmp_path / "K"
    downloads.mkdir()
    name = "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv"
    source = make_csv(downloads, name)
    destination = (
        statistics / "hemato" / "raa" / "PAT-DIT-ANTALL-OU" / name
    )
    destination.parent.mkdir(parents=True)
    make_csv(destination.parent, name)
    with pytest.raises(ArchiveError):
        archive_downloaded_file(
            source,
            statistics_root=statistics,
            unit="hemato",
            job_key="ordered",
        )


def test_archive_rolls_back_when_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lvms_stat import archive as archive_module

    downloads = tmp_path / "downloads"
    statistics = tmp_path / "K"
    downloads.mkdir()
    name = "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv"
    source = make_csv(downloads, name)

    class _Boom(Exception):
        pass

    monkeypatch.setattr(
        archive_module.ManifestStore,
        "record_run",
        lambda self, record: (_ for _ in ()).throw(_Boom()),
    )
    with pytest.raises(_Boom):
        archive_downloaded_file(
            source,
            statistics_root=statistics,
            unit="hemato",
            job_key="ordered",
        )
    # The file is back in the download directory; nothing is lost.
    assert source.is_file()


def test_archive_pending_skips_unknown_stems(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    statistics = tmp_path / "K"
    downloads.mkdir()
    make_csv(downloads, "PAT-DIT-ANTALL-OU__2026-08-01__2026-08-07.csv")
    make_csv(downloads, "random-export.csv")
    archived = archive_pending_downloads(
        downloads,
        statistics_root=statistics,
        unit="hemato",
        jobs={"PAT-DIT-ANTALL-OU": "ordered"},
    )
    assert len(archived) == 1
    assert (downloads / "random-export.csv").is_file()
