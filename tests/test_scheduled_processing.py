from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch as mock_patch

from lvms_stat.post_processing import ProcessOutcome
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
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return config


def test_processing_runs_after_successful_download(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    calls: list[tuple[Path, dict[str, str]]] = []

    def fake_process_unit(unit_dir, lookup_path, report_ids):
        calls.append((unit_dir, report_ids))
        return ProcessOutcome(5, 3, 2, unit_dir / "prosessert")

    # _process_after_fetch(config_path, unit_key, stream) is the patched call
    def wrapper(config_path, unit_key, stream):
        return fake_process_unit(Path("unit"), Path("lookup"), {"ordered": "R1"})

    def fake_fetch(config_path, *, unit_key, **_):
        return type(
            "Outcome",
            (),
            {"downloaded": ("x.csv",), "archived": ("y.csv",), "up_to_date": ()},
        )()

    stream = io.StringIO()
    with mock_patch(
        "lvms_stat.scheduled._process_after_fetch", side_effect=wrapper
    ):
        code = run_scheduled(config, output=stream, fetcher=fake_fetch)
    assert code == 0
    assert calls == [(Path("unit"), {"ordered": "R1"})]


def test_processing_failure_does_not_fail_run(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    def failing_process(config_path, unit_key, stream):
        raise RuntimeError("boom")

    def fake_fetch(config_path, *, unit_key, **_):
        return type(
            "Outcome",
            (),
            {"downloaded": ("x.csv",), "archived": (), "up_to_date": ()},
        )()

    stream = io.StringIO()
    with mock_patch(
        "lvms_stat.scheduled._process_after_fetch",
        side_effect=failing_process,
    ):
        # exception inside processing must be swallowed by run_scheduled
        code = run_scheduled(config, output=stream, fetcher=fake_fetch)
    assert code == 0
    assert "prosessering feilet" in stream.getvalue()


def test_no_processing_when_up_to_date(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    processed: list[str] = []

    def fake_fetch(config_path, *, unit_key, **_):
        return type(
            "Outcome", (), {"downloaded": (), "archived": (), "up_to_date": ("R",)}
        )()

    with mock_patch(
        "lvms_stat.scheduled._process_after_fetch",
        side_effect=lambda *a, **k: processed.append(a),
    ):
        code = run_scheduled(config, output=io.StringIO(), fetcher=fake_fetch)
    assert code == 0
    assert processed == []
