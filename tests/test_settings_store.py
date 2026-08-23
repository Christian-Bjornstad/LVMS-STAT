from __future__ import annotations

import json
from pathlib import Path

import pytest

from lvms_stat.settings_store import (
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
