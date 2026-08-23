from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path

from lvms_stat.manifest import ManifestStore, RunRecord
from lvms_stat.scheduled import run_scheduled


def make_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"statistics_root": str(tmp_path / "K")}), encoding="utf-8"
    )
    (tmp_path / "units.json").write_text(
        json.dumps(
            {
                "units": {
                    "hemato": {
                        "label": "Hemato",
                        "analysis_codes": ["CALR-OU"],
                        "reports": [
                            {"job_key": "ordered", "report_id": "PAT-DIT-ANTALL-OU"}
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


def test_missing_units_config_returns_error(tmp_path: Path) -> None:
    stream = io.StringIO()
    code = run_scheduled(
        tmp_path / "config.json", output=stream
    )
    assert code == 2


def test_all_up_to_date_runs_clean_and_reports_per_unit(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    today = date(2026, 8, 22)

    def fake_fetch(config_path: Path, *, unit_key: str, **_: object) -> object:
        class Outcome:
            downloaded: tuple[str, ...] = ()
            up_to_date = ("PAT-DIT-ANTALL-" + ("OU" if unit_key == "hemato" else "SO"),)

        return Outcome()

    stream = io.StringIO()
    code = run_scheduled(
        config, today=today, output=stream, fetcher=fake_fetch
    )
    assert code == 0
    text = stream.getvalue()
    assert "[hemato]" in text and "[solide]" in text


def test_one_unit_failing_does_not_stop_the_other(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    today = date(2026, 8, 22)

    def fake_fetch(config_path: Path, *, unit_key: str, **_: object) -> object:
        if unit_key == "hemato":
            raise RuntimeError("edge failed")
        return type(
            "Outcome", (), {"downloaded": ("x.csv",), "up_to_date": ()}
        )()

    stream = io.StringIO()
    code = run_scheduled(
        config, today=today, output=stream, fetcher=fake_fetch
    )
    assert code == 1
    text = stream.getvalue()
    assert "[hemato]" in text
    assert "[solide]" in text and "1 rapporter hentet" in text


def test_selected_units_only(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    called: list[str] = []

    def fake_fetch(config_path: Path, *, unit_key: str, **_: object) -> object:
        called.append(unit_key)
        return type("Outcome", (), {"downloaded": (), "up_to_date": ()})()

    stream = io.StringIO()
    code = run_scheduled(
        config,
        unit_keys=("solide",),
        today=date(2026, 8, 22),
        output=stream,
        fetcher=fake_fetch,
    )
    assert code == 0
    assert called == ["solide"]
