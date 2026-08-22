from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from lvms_stat.fetch_orchestrator import (
    FetchOrchestrationError,
    run_incremental_fetch,
)
from lvms_stat.manifest import ManifestStore


def make_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "statistics_root": str(tmp_path / "K"),
            }
        ),
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


def seed_history(tmp_path: Path, last_to: date) -> None:
    store = ManifestStore(tmp_path / "K" / "manifest.sqlite")
    store.record_run(
        type(
            "R",
            (),
            {},
        )()
        if False
        else __import__(
            "lvms_stat.manifest", fromlist=["RunRecord"]
        ).RunRecord(
            unit="hemato",
            job_key="ordered",
            report_id="PAT-DIT-ANTALL-OU",
            created_from=date(2026, 8, 1),
            created_to=last_to,
            filename=f"PAT-DIT-ANTALL-OU__2026-08-01__{last_to.isoformat()}.csv",
        )
    )


def test_missing_statistics_root_is_reported(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    with pytest.raises(FetchOrchestrationError):
        run_incremental_fetch(config, unit_key="hemato")


def test_unknown_unit_is_reported(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(FetchOrchestrationError, match="unit was not found"):
        run_incremental_fetch(config, unit_key="finnes-ikke")


def test_everything_up_to_date_returns_empty_outcome(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    today = date(2026, 8, 22)
    seed_history(tmp_path, today)
    outcome = run_incremental_fetch(config, unit_key="hemato", today=today)
    assert outcome.downloaded == ()
    assert outcome.up_to_date == ("PAT-DIT-ANTALL-OU",)


def test_plan_with_history_builds_generated_jobs_file(tmp_path: Path) -> None:
    """Without a real LVMS session the batch fails; the plan file is still built."""
    config = make_config(tmp_path)
    today = date(2026, 8, 22)
    seed_history(tmp_path, date(2026, 8, 19))
    with pytest.raises(FetchOrchestrationError, match="stoppet"):
        run_incremental_fetch(config, unit_key="hemato", today=today)
    generated = tmp_path / "jobs.generated-hemato.json"
    assert generated.is_file()
    payload = json.loads(generated.read_text(encoding="utf-8"))
    job = payload["jobs"][0]
    assert job["job_key"] == "ordered__PAT-DIT-ANTALL-OU"
    assert job["created_from"] == "17.08.2026"
    assert job["created_to"] == "22.08.2026"
    assert job["output_stem"] == "PAT-DIT-ANTALL-OU"


def test_first_run_plans_from_backfill_start(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    today = date(2026, 8, 22)
    with pytest.raises(FetchOrchestrationError, match="stoppet"):
        run_incremental_fetch(config, unit_key="hemato", today=today)
    payload = json.loads(
        (tmp_path / "jobs.generated-hemato.json").read_text(encoding="utf-8")
    )
    assert payload["jobs"][0]["created_from"] == "01.01.2024"
