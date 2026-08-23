from __future__ import annotations

import json
from pathlib import Path

import pytest

from lvms_stat.settings_store import (
    DEFAULT_EXTRACTION_CODES,
    DEFAULT_UNITS,
    Settings,
    SettingsError,
    default_settings,
    load_settings,
    save_settings,
    settings_path,
    settings_root,
    validate_settings,
)


@pytest.fixture()
def local_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path


def test_default_settings_are_complete(local_home: Path) -> None:
    settings = default_settings()
    assert settings.statistics_root.endswith("Statistikk")
    assert settings.profile_directory.lower().endswith("edge-profile")
    assert set(settings.units) == {"hemato", "solide"}
    assert len(settings.units["hemato"]["analysis_codes"]) == 70
    assert settings.units["solide"]["profile"] == "solide"


def test_save_then_load_roundtrip(local_home: Path) -> None:
    settings = default_settings()
    settings.landing_url = "https://lvms.example.invalid/clims"
    path = save_settings(settings)
    assert path == settings_path()
    assert path.exists()
    loaded = load_settings()
    assert loaded.landing_url == "https://lvms.example.invalid/clims"
    assert loaded.units["solide"]["profile"] == "solide"
    # files are exactly the ones the pipeline reads
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["expected_origin"] == "https://lvms.example.invalid"


def test_validate_rejects_missing_landing_url(local_home: Path) -> None:
    settings = default_settings()
    settings.landing_url = ""
    with pytest.raises(SettingsError):
        validate_settings(settings)


def test_validate_rejects_bad_units(local_home: Path) -> None:
    settings = default_settings()
    settings.landing_url = "https://lvms.example.invalid/clims"
    settings.units["hemato"]["reports"] = []
    with pytest.raises(SettingsError):
        save_settings(settings)
    # nothing was written
    assert not settings_path().exists()


def test_saved_files_satisfy_pipeline_validators(
    local_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: GUI-saved files must pass the real loaders."""
    from lvms_stat.manifest import load_statistics_settings
    from lvms_stat.units import load_units

    settings = default_settings()
    settings.landing_url = "https://lvms.example.invalid/clims"
    save_settings(settings)

    root = load_statistics_settings(settings_path())
    assert root.name == "Statistikk"
    units = load_units(settings_root() / "units.json")
    assert [unit.key for unit in units] == ["hemato", "solide"]
    assert units[1].profile == "solide"


def test_environment_root_used_as_default(
    local_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LVMS_STATISTICS_ROOT", "D:/Annet/Statistikk")
    settings = default_settings()
    assert settings.statistics_root == "D:/Annet/Statistikk"


def test_load_heals_partial_settings_file(local_home: Path) -> None:
    """The exact failure the user hit: a settings.json with only a few
    keys must load with defaults filled in, not crash the GUI."""
    import json

    root = settings_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text(
        json.dumps({"landing_url": "https://lvms.sykehus.no/clims"}),
        encoding="utf-8",
    )
    # no units.json at all
    loaded = load_settings()
    assert loaded.landing_url == "https://lvms.sykehus.no/clims"
    assert loaded.statistics_root  # healed from default
    assert loaded.profile_directory  # healed from default
    assert set(loaded.units) == {"hemato", "solide"}  # healed from default


def test_load_returns_defaults_when_settings_absent(local_home: Path) -> None:
    loaded = load_settings()
    assert loaded.landing_url == "https://lvms.sykehus.no/clims"
    assert loaded.statistics_root.endswith("Statistikk")


def test_degenerate_code_lists_self_heal(local_home: Path) -> None:
    """The exact failure from the work computer: an old units.json whose
    code lists collapsed to a single entry must load with the full
    built-in lists restored, not with one lonely analysis code."""
    import json

    root = settings_root()
    root.mkdir(parents=True, exist_ok=True)
    # A valid settings.json so load_settings proceeds to read units.json
    # instead of returning pure defaults.
    (root / "settings.json").write_text(
        json.dumps({"landing_url": "https://lvms.sykehus.no/clims"}),
        encoding="utf-8",
    )
    (root / "units.json").write_text(
        json.dumps(
            {
                "units": {
                    "hemato": {
                        "label": "Hemato",
                        "profile": "hemato",
                        "analysis_codes": ["CALR-OU"],
                        "reports": [
                            {"job_key": "ordered", "report_id": "PAT-DIT-ANTALL-OU"}
                        ],
                    },
                    "solide": {
                        "label": "Solide",
                        "profile": "solide",
                        "analysis_codes": ["EKSTRAKSJON-SO-OU"],
                        "reports": [
                            {
                                "job_key": "extraction",
                                "report_id": "PAT-DIT-EKSTRAKSJON-OU",
                            }
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings()

    hemato = loaded.units["hemato"]
    solide = loaded.units["solide"]
    # Restored to the full built-in lists, not the degenerate singletons:
    assert len(hemato["analysis_codes"]) == len(
        DEFAULT_UNITS["hemato"]["analysis_codes"]
    )
    assert len(solide["analysis_codes"]) == len(
        DEFAULT_UNITS["solide"]["analysis_codes"]
    )
    assert hemato["analysis_codes"][0] != "CALR-OU"
    assert "BRCA1-OU" in solide["analysis_codes"]
    # Reports are also healed back to the known-good triple.
    assert [r["job_key"] for r in hemato["reports"]] == [
        "ordered",
        "answered",
        "extraction",
    ]


def test_legacy_report_routing_self_heals(local_home: Path) -> None:
    """A complete old report set must still migrate extraction routing.

    Older installations stored only ``report_id``.  That made the third
    job run the non-existent EKSTRAKSJON report instead of running
    RESULTATER with the extraction-code override.
    """
    import copy
    import json

    root = settings_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text(
        json.dumps({"landing_url": "https://lvms.sykehus.no/clims"}),
        encoding="utf-8",
    )
    legacy_units = copy.deepcopy(DEFAULT_UNITS)
    for unit in legacy_units.values():
        unit["reports"] = [
            {"job_key": "ordered", "report_id": "PAT-DIT-ANTALL-OU"},
            {"job_key": "answered", "report_id": "PAT-DIT-RESULTATER-OU"},
            {
                "job_key": "extraction",
                "report_id": "PAT-DIT-EKSTRAKSJON-OU",
            },
        ]
    (root / "units.json").write_text(
        json.dumps({"units": legacy_units}), encoding="utf-8"
    )

    loaded = load_settings()

    for unit_key in ("hemato", "solide"):
        reports = {
            item["job_key"]: item for item in loaded.units[unit_key]["reports"]
        }
        extraction = reports["extraction"]
        assert extraction["fetch_report_id"] == "PAT-DIT-RESULTATER-OU"
        assert extraction["report_id"] == "PAT-DIT-EKSTRAKSJON-OU"
        assert extraction["analysis_codes"] == list(DEFAULT_EXTRACTION_CODES)


def test_partial_units_json_keeps_user_units_but_heals_missing_ones(
    local_home: Path,
) -> None:
    """A units.json that only defines hemato gets solide healed in from
    defaults instead of loading with a missing unit."""
    import json

    root = settings_root()
    root.mkdir(parents=True, exist_ok=True)
    # Same: settings.json must exist for units.json to be considered.
    (root / "settings.json").write_text(
        json.dumps({"landing_url": "https://lvms.sykehus.no/clims"}),
        encoding="utf-8",
    )
    (root / "units.json").write_text(
        json.dumps(
            {
                "units": {
                    "hemato": {
                        "label": "Hemato",
                        "analysis_codes": ["CALR-OU"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings()

    # hemato was degenerate -> healed; solide was absent -> added.
    assert set(loaded.units) == {"hemato", "solide"}
    assert (
        loaded.units["hemato"]["analysis_codes"]
        == DEFAULT_UNITS["hemato"]["analysis_codes"]
    )
