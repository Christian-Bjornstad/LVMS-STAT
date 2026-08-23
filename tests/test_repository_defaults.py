from __future__ import annotations

import json
import tomllib
from pathlib import Path

import lvms_stat


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_and_example_json_files_are_shipped_and_valid() -> None:
    for stem in ("config", "jobs", "units"):
        canonical = ROOT / f"{stem}.json"
        example = ROOT / f"{stem}.example.json"

        canonical_payload = json.loads(canonical.read_text(encoding="utf-8"))
        example_payload = json.loads(example.read_text(encoding="utf-8"))

        assert canonical_payload
        assert canonical_payload == example_payload


def test_package_metadata_matches_runtime_version() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == lvms_stat.__version__
    assert metadata["project"]["scripts"]["lvms-stat-portal"] == (
        "lvms_stat.portal:main"
    )
