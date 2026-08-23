from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lvms_stat.manifest import ManifestStore, RunRecord


FILENAME_PATTERN = re.compile(
    r"^(?P<stem>[A-Za-z0-9][A-Za-z0-9_-]{0,79})"
    r"__(?P<from>\d{4}-\d{2}-\d{2})"
    r"__(?P<to>\d{4}-\d{2}-\d{2})\.csv$"
)

# Staging names carry a lowercase unit prefix ("<unit>-<STEM>__...") so
# two units can never produce the same filename in the shared raadata
# folder. UNIT_PREFIX_PATTERN splits that prefix back off.
UNIT_PREFIX_PATTERN = re.compile(
    r"^(?P<unit>[a-z][a-z0-9]{0,19})-(?P<rest>.+)$"
)


class ArchiveError(ValueError):
    """A downloaded report could not be archived safely."""


def split_unit_prefix(filename: str) -> tuple[str | None, str]:
    """Return ``(unit_prefix, canonical_filename)`` for a staged file.

    ``hemato-PAT-DIT-ANTALL-OU__2024-01-01__2026-08-23.csv`` becomes
    ``("hemato", "PAT-DIT-ANTALL-OU__2024-01-01__2026-08-23.csv")``.
    Files without a recognizable prefix are returned unchanged with
    ``None`` so legacy staged files keep archiving under their own unit.
    """
    match = UNIT_PREFIX_PATTERN.fullmatch(filename)
    if match is None:
        return None, filename
    rest = match.group("rest")
    if FILENAME_PATTERN.fullmatch(rest) is None:
        return None, filename
    return match.group("unit"), rest


@dataclass(frozen=True)
class ArchivedRun:
    record: RunRecord
    archived_path: Path


def parse_batch_filename(filename: str, *, job_key: str, unit: str) -> RunRecord:
    """Turn a deterministic batch filename into a run record."""
    match = FILENAME_PATTERN.fullmatch(filename)
    if match is None:
        raise ArchiveError("downloaded file name is not a batch filename")
    try:
        created_from = date.fromisoformat(match.group("from"))
        created_to = date.fromisoformat(match.group("to"))
    except ValueError as exc:
        raise ArchiveError("batch file name contains an invalid date") from exc
    if created_from > created_to:
        raise ArchiveError("batch file name interval is invalid")
    return RunRecord(
        unit=unit,
        job_key=job_key,
        report_id=match.group("stem"),
        created_from=created_from,
        created_to=created_to,
        filename=filename,
    )


def archive_downloaded_file(
    source: Path,
    *,
    statistics_root: Path,
    unit: str,
    job_key: str,
) -> ArchivedRun:
    """Move one finished CSV into the statistics tree and log the run.

    Destination layout: ``<root>/<unit>/raa/<report_id>/<filename>``
    The move is refused when a file already exists at the destination or
    the manifest already contains the same unit + filename.
    """
    source = Path(source)
    statistics_root = Path(statistics_root)
    if not source.is_absolute() or not statistics_root.is_absolute():
        raise ArchiveError("archive paths must be absolute")

    # A unit-prefixed staging file must belong to this unit; a leftover
    # from another unit is refused so it can never be archived as ours.
    file_unit, canonical_name = split_unit_prefix(source.name)
    if file_unit is not None and file_unit != unit:
        raise ArchiveError(
            "downloaded file belongs to another unit "
            f"({file_unit}, expected {unit})"
        )

    record = parse_batch_filename(canonical_name, job_key=job_key, unit=unit)
    destination_directory = (
        statistics_root / record.unit / "raa" / record.report_id
    )
    destination = destination_directory / record.filename

    store = ManifestStore(statistics_root / "manifest.sqlite")
    # The manifest is keyed by canonical filename (without prefix); if
    # the prefixed file was already archived under another unit, the
    # manifest check will catch it.
    if store.has_filename(record.unit, record.filename):
        raise ArchiveError("run is already recorded in the manifest")
    if destination.exists():
        raise ArchiveError("archived file already exists")

    try:
        destination_directory.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    except OSError as exc:
        raise ArchiveError("archiving the downloaded file failed") from exc

    try:
        store.record_run(record)
    except BaseException:
        # Roll the file back so a failed manifest write never loses data.
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            pass
        raise
    return ArchivedRun(record=record, archived_path=destination)


def archive_pending_downloads(
    download_directory: Path,
    *,
    statistics_root: Path,
    unit: str,
    jobs: dict[str, str] | None = None,
) -> list[ArchivedRun]:
    """Archive every finished batch CSV in the local download directory.

    ``jobs`` maps output stem -> job_key; unknown stems are skipped so
    unrelated files in the directory are never touched.
    """
    directory = Path(download_directory)
    if not directory.is_absolute():
        raise ArchiveError("download directory must be absolute")
    mapping = jobs or {}
    archived: list[ArchivedRun] = []
    for item in sorted(directory.iterdir()):
        if not item.is_file() or item.suffix.lower() != ".csv":
            continue
        stem = item.name.split("__", 1)[0]
        job_key = mapping.get(stem)
        if job_key is None:
            continue
        archived.append(
            archive_downloaded_file(
                item,
                statistics_root=statistics_root,
                unit=unit,
                job_key=job_key,
            )
        )
    return archived
