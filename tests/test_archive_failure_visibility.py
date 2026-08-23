"""Task 4: a failed archive must be loud - the user must never wonder
where the files went. The error names the staging folder and tells the
user exactly what to do."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from lvms_stat.fetch_orchestrator import (
    FetchOrchestrationError,
    run_incremental_fetch,
)


def _config(tmp_path: Path, statistics_root: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"statistics_root": str(statistics_root)}),
        encoding="utf-8",
    )
    (tmp_path / "units.json").write_text(
        json.dumps(
            {
                "units": {
                    "hemato": {
                        "label": "Hemato",
                        "analysis_codes": ["CALR-OU"],
                        "reports": [
                            {
                                "job_key": "ordered",
                                "report_id": "PAT-DIT-ANTALL-OU",
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return config


def test_failed_archive_is_loud(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged file that cannot be archived raises with the staging
    path and remediation guidance in the message."""
    root = tmp_path / "Statistikk"
    config = _config(tmp_path, root)

    staging = tmp_path / "raadata"
    staging.mkdir(parents=True)
    # A file that matches this unit's expected stem, so the orchestrator
    # will try to archive it.
    (staging / "hemato-PAT-DIT-ANTALL-OU__2026-08-17__2026-08-22.csv").write_text(
        "x", encoding="cp1252"
    )
    # Make every archive attempt fail, as if K: were unreachable.
    # Patch where the orchestrator looks the function up.
    from lvms_stat import fetch_orchestrator as fo

    monkeypatch.setattr(
        fo,
        "archive_downloaded_file",
        lambda *a, **k: (_ for _ in ()).throw(Exception("disk is full")),
    )

    monkeypatch.setattr(fo, "staging_directory", lambda: staging)
    # No real LVMS session here; skip straight to the archive step.
    monkeypatch.setattr(fo, "_run_positional_batch", lambda *a, **k: 0)

    today = date(2026, 8, 22)
    with pytest.raises(FetchOrchestrationError) as excinfo:
        run_incremental_fetch(config, unit_key="hemato", today=today)

    message = str(excinfo.value)
    assert str(staging) in message  # where the file still lies
    assert "hemato-PAT-DIT-ANTALL-OU__2026-08-17__2026-08-22.csv" in message
    assert "IKKE slettet" in message
