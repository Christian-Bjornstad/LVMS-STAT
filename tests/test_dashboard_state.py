from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from lvms_stat.dashboard_state import (
    DashboardStateError,
    describe_failure,
    describe_outcome,
    load_unit_statuses,
)
from lvms_stat.fetch_orchestrator import FetchOrchestrationError
from lvms_stat.manifest import ManifestStore, RunRecord


def make_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"statistics_root": str(tmp_path / "K")}), encoding="utf-8")
    (tmp_path / "units.json").write_text(
        json.dumps(
            {
                "units": {
                    "hemato": {
                        "label": "Hemato",
                        "analysis_codes": ["CALR-OU"],
                        "reports": [
                            {"job_key": "ordered", "report_id": "PAT-DIT-ANTALL-OU"},
                            {
                                "job_key": "answered",
                                "report_id": "PAT-DIT-RESULTATER-OU",
                            },
                        ],
                    },
                    "solide": {
                        "label": "Solide",
                        "analysis_codes": ["EKSTRAKSJON-SO-OU"],
                        "reports": [
                            {"job_key": "ordered", "report_id": "PAT-DIT-ANTALL-SO"}
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return config


def seed(tmp_path: Path, unit: str, report_id: str, last_to: date) -> None:
    store = ManifestStore(tmp_path / "K" / "manifest.sqlite")
    store.record_run(
        RunRecord(
            unit=unit,
            job_key="ordered",
            report_id=report_id,
            created_from=last_to - timedelta(days=6),
            created_to=last_to,
            filename=f"{report_id}__x__{last_to.isoformat()}.csv",
        )
    )
    return store.last_completed_to("hemato", report_id)


def test_statuses_reflect_manifest_history(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    today = date(2026, 8, 22)
    seed(tmp_path, "hemato", "PAT-DIT-ANTALL-OU", today - timedelta(days=1))
    statuses = load_unit_statuses(config, today=today)

    assert [unit.key for unit in statuses] == ["hemato", "solide"]
    hemato = statuses[0]
    assert hemato.label == "Hemato"
    ordered = hemato.reports[0]
    assert ordered.state == "klar"
    assert ordered.headline == "Oppdatert til 21.08.2026"
    answered = hemato.reports[1]
    assert answered.last_created_to is None
    assert answered.needs_fetch is True
    assert answered.state == "klar"
    assert "01.01.2024" in answered.headline
    # solide untouched -> first fetch flag
    assert statuses[1].reports[0].needs_fetch is True


def test_missing_config_raises_state_error(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    with pytest.raises(DashboardStateError):
        load_unit_statuses(config, today=date(2026, 8, 22))


def test_describe_outcome_variants() -> None:
    class Outcome:
        downloaded = ("a.csv", "b.csv")
        up_to_date: tuple[str, ...] = ()

    assert "2 rapporter hentet" in describe_outcome(Outcome())

    class Nothing:
        downloaded: tuple[str, ...] = ()
        up_to_date: tuple[str, ...] = ()

    assert describe_outcome(Nothing()) == "Ingen nye data ble hentet."


def test_describe_failure_hides_internal_details() -> None:
    message = describe_failure(FetchOrchestrationError("rapportkjøringen stoppet"))
    assert message == "rapportkjøringen stoppet"
    message = describe_failure(RuntimeError("C:/Users/molpa secret path"))
    assert "molpa" not in message
