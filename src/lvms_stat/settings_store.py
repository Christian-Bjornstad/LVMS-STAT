"""App-managed settings so the whole setup happens inside the GUI.

The dashboard's «Oppsett» page collects every knob (LVMS address,
statistics root, folders, units) and stores two files under
``%LOCALAPPDATA%/LVMS-STAT``:

- ``settings.json``  - browser/statistics configuration
- ``units.json``     - clinical units (hemato/solide) with profiles

Both filenames are exactly what the rest of the pipeline already reads
(``load_statistics_settings`` + ``load_units`` resolve siblings of the
config path), so saving here makes the whole pipeline work with no
manual JSON editing. Sensible defaults (including all known analysis
codes) are baked in below so a fresh machine only needs a review.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lvms_stat.config import ConfigError, validate_app_config
from lvms_stat.units import UnitsConfigError, validate_units

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

SETTINGS_DIRNAME = "LVMS-STAT"

DEFAULT_STATISTICS_ROOT = (
    "K:/Sensitivt/Klinikk/Sensitiv_mappe_MolPat/Hemato/Statistikk"
)


class SettingsError(ValueError):
    """Settings could not be loaded, validated, or saved."""


DEFAULT_EXTRACTION_CODES: tuple[str, ...] = (
    "EKSTRAKSJON-OU", "EKSTRAQIACRNA-OU", "EKSTRAFFPEKOL-OU",
    "EKSTRAEZ1VEV-OU", "EKSTRARECALL-OU", "EKSTRAFFPETRNA-OU",
    "EKSTRAANNETRNA-OU", "EKSTRAANNETDNA-OU", "EKSTRAQIACRNA-H-OU",
    "EKSTRAFFPEKOL-H-OU", "EKSTRAEZ1DNA-H-OU", "EKSTRAEZ1VEV-H-OU",
    "EKSTRAQIASDNA-H-OU", "EKSTRAQIASDNA-OU", "EKSTRAQIASRNA-H-OU",
    "EKSTRAMAXDNA-OU", "EKSTRAMAXDNA-H-OU", "EKSTRAMAXRNA-OU",
    "EKSTRAMAXRNA-H-OU", "EKSTRAANNETRNA-H-OU", "EKSTRAANNETDNA-H-OU",
    "EKSTRAAPKOL-H-OU", "EKSTRMAXRNA-KML-H-OU", "EKSTRAGENXDNA-OU",
    "EKSTRAGENXRNA-OU"
)

EXTRACTION_CODES = list(DEFAULT_EXTRACTION_CODES)

# Known-good unit definitions (mirrors units.example.json). The GUI lets
# the user edit every part of this - it is a starting point, not a lock.
DEFAULT_UNITS: dict[str, Any] = {
    "hemato": {
        "label": "Hemato",
        "profile": "hemato",
        "analysis_codes": [
            "EKSTRAKSJON-H-OU", "AVVENTFLOW-OU", "OPPBEVARING-OU", "HEMAVISION-OU",
            "PML-RARA-OU", "CBFB-MYH11-OU", "RUNX1-RUNX1T1-OU", "BCR-ABL1-OU",
            "AFF1-KMT2A-OU", "MLLT3-KMT2A-OU", "FLT3-ITD-OU", "FLT3-TKD-OU",
            "NPM1-FRAG-OU", "PDGFRA-OU", "PDGFRB-OU", "FIP1L1-PDGFRA-RNA-OU",
            "FIP1L1-PDGFRA-DNA-OU", "WT1-OU", "PRAME-OU", "NPM1A-OU",
            "FUSJON-DPCR-OU", "NPM1-OU", "BCR-ABL1-MAJOR-Q-OU",
            "BCR-ABL1-MINOR-Q-OU", "CBFB-MYH11A-Q-OU", "CBFB-MYH11D-Q-OU",
            "CBFB-MYH11E-Q-OU", "DEK-NUP214-OU", "ETV6-RUNX1-Q-OU",
            "AFF1-KMT2A9-Q-OU", "AFF1-KMT2A10-Q-OU", "MLLT3-KMT2A-E8-Q-OU",
            "MLLT3-KMT2A-E9-Q-OU", "PML-RARA-BCR1-Q-OU", "PML-RARA-BCR2-Q-OU",
            "PML-RARA-BCR3-Q-OU", "RUNX1-RUNX1T-Q-OU", "TCF3-PBX1-Q-OU",
            "KML-UTREDNING-OU", "KML-BCRABL1-MAJOR-OU", "KML-BCRABL1-MINOR-OU",
            "KML-BCRABL1-MIKRO-OU", "JAK2-V617F-OU", "JAK2-EX12-OU", "CALR-OU",
            "MPL-W515L-OU", "MPL-W515K-OU", "KIT-D816V-OU", "IGH-VDJ-OU",
            "IGH-DJ-OU", "IGK-OU", "TRB-OU", "TRG-OU", "TRD-OU", "TRDA-OU",
            "IKZF1-OU", "STILTAL-OU", "DNA-LADDER-OU", "MYD88-L265P-OU",
            "ASO-MRD-OU", "ASO-MRD-29-OU", "ASO-MRD-50-OU", "ASO-MRD-71-OU",
            "ASO-MRD-B-ETA-OU", "ASO-MRD-T-ETA-OU", "HTS-MYELOID-OU",
            "HTS-MYELOID-TP53-OU", "HTS-KIMKTR-OU", "HTS-PAN-HEM-OU", "HTS-IGH-OU"
        ],
        "reports": [
            {"job_key": "ordered",
             "fetch_report_id": "PAT-DIT-ANTALL-OU",
             "report_id": "PAT-DIT-ANTALL-OU"},
            {"job_key": "answered",
             "fetch_report_id": "PAT-DIT-RESULTATER-OU",
             "report_id": "PAT-DIT-RESULTATER-OU"},
            {"job_key": "extraction",
             # PAK analysetid runs in LVMS under the RESULTATER id
             # with its own EKSTRA* codes; export is saved as
             # PAT-DIT-EKSTRAKSJON-OU.
             "fetch_report_id": "PAT-DIT-RESULTATER-OU",
             "report_id": "PAT-DIT-EKSTRAKSJON-OU",
             "analysis_codes": EXTRACTION_CODES},
        ],
    },
    "solide": {
        "label": "Solide",
        "profile": "solide",
        # NB: solide reports keep the same LVMS names as hemato (-OU);
        # the export is filtered on OU-SOLIDE and stored under Solide/.
        "analysis_codes": [
            "FORBVIDERE-OU", "TERT-OU", "POLE-OU", "CTNNB1-OU", "FOXL2-OU",
            "H3F3A-OU", "H3C2-OU", "H3C3-OU", "H3C14-OU", "IDH1-OU", "IDH2-OU",
            "BCRABL1-OU", "PDGFRA-SEK2-OU", "KIT-OU", "ID-PCR-OU", "MOLA-PCR-OU",
            "MLPA-OU", "MGMT-OU", "HPV-OU", "MLH1-OU", "MSI-OU", "KRAS-VAR-OU",
            "NRASBRAF-VAR-OU", "EGFR-VAR-OU", "GENEFUSION-OU", "PROSIGNA-OU",
            "HTS-ONCCHILD-OU", "HTS-CRC-OU", "HTS-NSCLC-OU", "HTS-MELANOM-OU",
            "HTS-MELANOM-FUS-OU", "HTS-GIST-OU", "HTS-BARNGLIOM-HG-OU",
            "HTS-BARNETUMOR-OU", "HTS-NERUOBLAST-OU", "HTS-HODE-HALS-OU",
            "HTS-THYROIDEA-OU", "HTS-GYN-OU", "HTS-BARNGLIOM-OU",
            "HTS-VOKSENGLIOM-OU", "HTS-MEDULLOBLAST-OU", "HTS-EPENDYOMOM-OU",
            "HTS-SMAACELLE-OU", "HTS-SARKOM-OU", "HTS-GALLE-PANC-GI-OU", "HRR-OU",
            "MYRIAD-OU", "BRCA1-OU", "BRCA2-OU", "HTS-EKSTRA-DNA-OU",
            "HTS-EKSTRA-RNA-OU", "HTS-PA-EKSTRA-RNA-OU", "HTS-CH-NSCLC-OU",
            "HTS-PA-NSCLC-OU", "HTS-CH-GALLE-PANC-OU", "HTS-PA-GALLE-PANC-OU",
            "HTS-CH-MELANOMFUS-OU", "HTS-PA-MELANOMFUS-OU", "HTS-CH-MELANOM-OU",
            "HTS-PA-MELANOM-OU", "HTS-CH-CRC-OU", "HTS-PA-CRC-OU",
            "HTS-CH-GIST-OU", "HTS-PA-GIST-OU", "HTS-CH-THYROIDEA-OU",
            "HTS-PA-THYROIDEA-OU", "HTS-ANNET-OU", "HTS-CH-ANNET-OU",
            "HTS-PA-ANNET-OU", "POLE-HRR-OU"
        ],
        "reports": [
            {"job_key": "ordered",
             "fetch_report_id": "PAT-DIT-ANTALL-OU",
             "report_id": "PAT-DIT-ANTALL-OU"},
            {"job_key": "answered",
             "fetch_report_id": "PAT-DIT-RESULTATER-OU",
             "report_id": "PAT-DIT-RESULTATER-OU"},
            {"job_key": "extraction",
             # PAK analysetid runs in LVMS under the RESULTATER id
             # with its own EKSTRA* codes; export is saved as
             # PAT-DIT-EKSTRAKSJON-OU.
             "fetch_report_id": "PAT-DIT-RESULTATER-OU",
             "report_id": "PAT-DIT-EKSTRAKSJON-OU",
             "analysis_codes": EXTRACTION_CODES},
        ],
    },
}


@dataclass
class Settings:
    """Everything the «Oppsett» page edits. Mutable on purpose: the GUI
    form fills and tweaks one instance before saving."""

    landing_url: str = ""
    statistics_root: str = ""
    profile_directory: str = ""
    download_directory: str = ""
    units: dict[str, Any] = field(default_factory=dict)


def settings_root() -> Path:
    base = os.environ.get("LOCALAPPDATA", "")
    if not base.strip():
        raise SettingsError(
            "lokaldatamappen (LOCALAPPDATA) er utilgjengelig"
        )
    return Path(base) / SETTINGS_DIRNAME


def settings_path() -> Path:
    return settings_root() / "settings.json"


def default_settings() -> Settings:
    """First-run values - everything is editable in the GUI."""
    local = settings_root()
    environment_root = os.environ.get("LVMS_STATISTICS_ROOT", "").strip()
    return Settings(
        landing_url="https://lvms.sykehus.no/clims",
        statistics_root=environment_root or DEFAULT_STATISTICS_ROOT,
        profile_directory=str(local / "edge-profile"),
        download_directory=str(local / "downloads"),
        units=copy.deepcopy(DEFAULT_UNITS),
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"{path.name} mangler") from exc
    except OSError as exc:
        raise SettingsError(f"{path.name} kunne ikke leses") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"{path.name} er ikke gyldig JSON") from exc


def load_settings() -> Settings:
    """Load saved settings, healing any missing keys with defaults.

    A partially written ``settings.json`` (e.g. only ``landing_url``
    from an early manual test) must never block the GUI: every absent
    key falls back to :func:`default_settings`, and a missing or
    unreadable ``units.json`` falls back to the built-in unit set.
    """
    base = default_settings()
    try:
        raw = _read_json(settings_path())
    except SettingsError:
        return base
    if not isinstance(raw, dict):
        return base

    def merged(value: Any, fallback: str) -> str:
        text = value.strip() if isinstance(value, str) else ""
        return text or fallback

    units = copy.deepcopy(base.units)
    try:
        units_raw = _read_json(settings_root() / "units.json")
        if (
            isinstance(units_raw, dict)
            and isinstance(units_raw.get("units"), dict)
            and units_raw["units"]
        ):
            units = copy.deepcopy(units_raw["units"])
    except SettingsError:
        pass

    return Settings(
        landing_url=merged(raw.get("landing_url"), base.landing_url),
        statistics_root=merged(raw.get("statistics_root"), base.statistics_root),
        profile_directory=merged(
            raw.get("profile_directory"), base.profile_directory
        ),
        download_directory=merged(
            raw.get("download_directory"), base.download_directory
        ),
        units=units,
    )


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def validate_settings(settings: Settings) -> None:
    """Run the exact validators the pipeline will apply later."""
    if not settings.landing_url.strip():
        raise SettingsError(
            "LVMS-adressen må fylles inn (f.eks. https://lvms.sykehus.no/clims)"
        )
    if not settings.statistics_root.strip():
        raise SettingsError("Statistikk-roten må fylles inn")
    app_raw = {
        "landing_url": settings.landing_url.strip(),
        "profile_directory": settings.profile_directory.strip(),
        "download_directory": settings.download_directory.strip(),
    }
    try:
        validate_app_config(app_raw, repository_root=REPOSITORY_ROOT)
    except ConfigError as exc:
        raise SettingsError(str(exc)) from exc
    try:
        validate_units({"units": settings.units})
    except UnitsConfigError as exc:
        raise SettingsError(f"Enheter er ugyldige: {exc}") from exc


def save_settings(settings: Settings) -> Path:
    """Validate and persist settings + units. Returns settings.json path."""
    validate_settings(settings)
    root = settings_root()
    root.mkdir(parents=True, exist_ok=True)
    settings_payload = {
        "landing_url": settings.landing_url.strip(),
        "expected_origin": _origin_of(settings.landing_url.strip()),
        "statistics_root": settings.statistics_root.strip(),
        "profile_directory": str(
            Path(settings.profile_directory.strip()).expanduser()
        ),
        "download_directory": str(
            Path(settings.download_directory.strip()).expanduser()
        ),
    }
    _atomic_write(root / "settings.json", json.dumps(settings_payload, indent=2))
    _atomic_write(
        root / "units.json",
        json.dumps({"units": settings.units}, indent=2, ensure_ascii=False),
    )
    return root / "settings.json"


def _origin_of(landing_url: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(landing_url)
    host = parsed.hostname or ""
    port = parsed.port
    return f"https://{host}" if port is None else f"https://{host}:{port}"
