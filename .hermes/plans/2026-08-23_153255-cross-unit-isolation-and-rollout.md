# Cross-unit CSV-forurensning + utrulling til jobb-PC — Implementeringsplan

> **For Hermes:** Bruk subagent-driven-development til å implementere planen oppgave for oppgave. Hver oppgave er TDD (rød → grønn → commit).

**Mål:** Stoppe at solide-henting arver hemato-filer (per-enhet mellomlagring), få alle fiksene faktisk ut til jobb-PC-en (merge til main), og la Oppsett-siden selvhelbrede konfig og validere stier.

**Arkitektur:** Batch-runner (frossen) lagrer alt i `<repo>/rådata/` med filnavn `<output_stem>__<fra>__<til>.csv`. Begge enheter produserer identiske stems (samme rapport-ID-er, samme backfill-vindu) → kollisjon. Løsning: gjør `output_stem` unik per enhet i job_builder (staging-navn), og kanoniser navnet tilbake til spesifikasjonsnavnet i archive-steget (vår kode). Konfig-helbredelse utvides til å gjenkjenne gammel units.json-form og reparere den automatisk på alle maskiner.

**Tech stack:** Python 3.12 stdlib + PyQt6, pytest, pytest-qt (offscreen), git.

---

## Diagnose (hvorfor brukeren så dette)

| Symptom hos bruker | Rotårsak funnet i kode |
|---|---|
| «Siste commit hadde ingen endringer» | Alt arbeid ligger på branch `fix/work-computer-validation`; `origin/main` er på `ae5588e` (før alle fikser). Jobb-PC trekker main → gammel kode. |
| «Ekstraksjon ble forsøkt med EKSTRAKSJON i rapport-id-feltet» | Gammel kode (pre-`520f672`) brukte `report_id=EKSTRAKSJON-*` som LVMS-rapport. Ny kode fyller `RESULTATER` og lagrer som `EKSTRAKSJON`. Bekrefter at jobb-PC kjørte gammel kode. |
| «Solide tror hemato-filer er solide, går rett på siste rapport, feiler for hemato» | **Ekte bug også i ny kode:** `batch_runner.py:147` bruker felles `<repo>/rådata/`; `batch_filename()` gir identiske filnavn for begge enheter (samme stems + samme 01.01.2024-backfill-vindu). Solide-run ser hemato-filen → «Batch job already complete» → hopper over henting → arkiverer hemato-fila under `unit=solide`. |
| «Filene blir liggende i rådata» | Arkivering flytter bare ved suksess; når `statistics_root` peker et sted som ikke kan skrives, blir filene igjen i det delte Mellomlageret uten skilt. |
| «Solide-koder ser ut som 1 linje» | Jobb-PC-en har sin egen `%LOCALAPPDATA%\LVMS-STAT\units.json`. Reparasjonen jeg gjorde, skjedde kun på dev-maskina. Gammel/degenerert fil på jobb-PC gir 1 kode. Mangler selvhelbredelse ved innlasting. |
| «Mapper i Oppsett gir ikke mening» | Sti-forslag fra dev-maskin finnes ikke i Citrix-VM. Mangler eksistens-indikator og «opprettes automatisk»-feedback. |

## Aktuelle antagelser

- `batch_runner.py` og `report_job.py` røres IKKE (brukerkrav: bevare LVMS-workflowen).
- Filnavn-mønsteret i `archive.FILENAME_PATTERN` (`[A-Za-z0-9][A-Za-z0-9_-]{0,79}`) aksepterer allerede enhets-prefikserte stems — verifisert.
- Manifest-nøkkel er `(unit, filename)`; kanoniske navn er konsistente på tvers av maskiner.

---

### Task 1: Regressionstest som reproduserer «hemato blir solide»

**Objective:** Lås feilen inn i en test som feiler nå, passer etter Task 2–4.

**Files:**
- Create: `tests/test_cross_unit_isolation.py`

**Step 1: Write failing test**

```python
"""Regression: one unit's staged CSV must never be consumed as another
unit's result. Reproduces the field report 'solide thinks hemato files
are solide'."""
from __future__ import annotations

import json
from pathlib import Path

from lvms_stat.archive import archive_pending_downloads


def _stage(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("a;b\n1;2\n", encoding="cp1252")


def test_hemato_leftover_cannot_archive_as_solide(tmp_path: Path) -> None:
    staging = tmp_path / "rådata"
    # Hemato ran first and its archive FAILED, so the file is still here,
    # staged with hemato's unit prefix (Task 2 adds prefixes).
    _stage(staging, "hemato-PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv")

    root = tmp_path / "Statistikk"
    jobs = {"PAT-DIT-EKSTRAKSJON-OU": "extraction"}
    archived = archive_pending_downloads(
        staging, statistics_root=root, unit="solide", jobs=jobs
    )

    assert archived == []  # foreign unit file must be ignored entirely
    assert not (root / "solide" / "raa").exists()


def test_unit_prefixed_file_archives_under_canonical_name(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "rådata"
    _stage(staging, "solide-PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv")
    root = tmp_path / "Statistikk"
    jobs = {
        "solide-PAT-DIT-EKSTRAKSJON-OU": (
            "solide",
            "PAT-DIT-EKSTRAKSJON-OU",
        )
    }
    archived = archive_pending_downloads(
        staging, statistics_root=root, unit="solide", jobs=jobs
    )
    assert len(archived) == 1
    landed = archived[0].archived_path
    # Canonical spec name on disk, not the staging name:
    assert landed.name == "PAT-DIT-EKSTRAKSJON-OU__2024-01-01__2026-08-23.csv"
    assert landed.parent == root / "solide" / "raa" / "PAT-DIT-EKSTRAKSJON-OU"
```

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=src python -m pytest tests/test_cross_unit_isolation.py -v`
Expected: FAIL (i dag arkiveres fremmed fil + landing heter prefikset navn).

**Step 3:** Implementering kommer i Task 2–3; ikke commit ennå.

---

### Task 2: Enhets-unike staging-navn i job_builder

**Objective:** Ingen to enheter kan lage samme filnavn i det felles mellomlageret.

**Files:**
- Modify: `src/lvms_stat/job_builder.py:68-76` (`build_report_job`)
- Modify: `src/lvms_stat/fetch_orchestrator.py` (`_write_generated_jobs` sender allerede `output_stem` videre — uendret)
- Test: `tests/test_job_builder.py`

**Step 1: Write failing test**

```python
def test_output_stem_is_unit_scoped() -> None:
    job = build_report_job(FETCH, analysis_codes=("CALR-OU",), template=TEMPLATE)
    # Staging name carries the unit so two units can never collide in the
    # shared rådata folder; archive step restores the spec name.
    assert job.output_stem == f"{FETCH.unit.key}-PAT-DIT-RESULTATER-OU"
```

**Step 2: Verify failure** — `pytest tests/test_job_builder.py::test_output_stem_is_unit_scoped -v` → FAIL.

**Step 3: Minimal implementation** (i `build_report_job`):

```python
    return ReportJob(
        job_key=fetch.report.job_key,
        report_type=template.report_type,
        category=template.category,
        report_id=fetch.report.fetch_report_id,
        analysis_codes=codes,
        interval=ReportInterval(fetch.created_from, fetch.created_to),
        # Unit-scoped staging name; the archive step renames to the
        # canonical spec filename (see archive.canonical_batch_name).
        output_stem=f"{fetch.unit.key}-{fetch.report.report_id}",
    )
```

Oppdater eksisterende assertions i `tests/test_fetch_orchestrator.py` som sjekker `output_stem`.

**Step 4: Verify pass** — `pytest tests/test_job_builder.py tests/test_fetch_orchestrator.py -v` → PASS.

**Step 5: Commit** — `git commit -m "fix: unit-scope staging filenames to stop cross-unit bleed"`

---

### Task 3: Kanonisk navn i archive-steget + fremmed-filer ignoreres

**Objective:** Prefiksert staging-fil lander med spesifikasjonsnavn i `<rot>/<enhet>/raa/<rapport>/`; filer fra andre enheter hoppes over.

**Files:**
- Modify: `src/lvms_stat/archive.py` (`parse_batch_filename`, `archive_downloaded_file`, `archive_pending_downloads`)
- Test: `tests/test_cross_unit_isolation.py` (fra Task 1)

**Step 1: Write failing test** — dekket av Task 1.

**Step 2: Implementation**

I `archive.py`:

```python
UNIT_PREFIX_PATTERN = re.compile(
    r"^(?P<unit>[a-z][a-z0-9]{0,19})-(?P<stem>[A-Za-z0-9][A-Za-z0-9_-]{0,79})"
    r"__(?P<from>\d{4}-\d{2}-\d{2})__(?P<to>\d{4}-\d{2}-\d{2})\.csv$"
)


def split_unit_prefix(filename: str) -> tuple[str | None, str]:
    """Return (unit_prefix, canonical_filename).

    Files without a unit prefix are returned unchanged with ``None``;
    legacy files stay archiveable under their own unit.
    """
    match = UNIT_PREFIX_PATTERN.fullmatch(filename)
    if match is None:
        return None, filename
    return (
        match.group("unit"),
        f"{match.group('stem')}__{match.group('from')}__{match.group('to')}.csv",
    )
```

- `archive_downloaded_file(..., expected_unit)`: kall `split_unit_prefix(source.name)`; hvis prefiks finnes og ≠ `expected_unit` → raise `ArchiveError("file belongs to another unit")` (kalleren fanger og hopper over). Kanoniskt navn brukes til `record.filename`, `destination` og manifest.
- `archive_pending_downloads`: bytt verdi-format i `jobs` til `(unit, canonical_stem)` eller les prefiksen direkte fra filnavnet (enklere: dropp `jobs`-mappingen for unit-bestemmelse; behold den kun for å begrense hvilke stems som er aktuelle). Unknown stems skipes som før.

**Step 3: Verify** — `pytest tests/test_cross_unit_isolation.py tests/test_archive.py -v` → PASS (juster eldre archive-tester til nye signaturen).

**Step 4: Commit** — `git commit -m "fix: archive restores canonical spec names; foreign-unit files refused"`

---

### Task 4: Høylytt feil når arkivering mislykkes

**Objective:** Filene skal aldri ligge taust i `rådata` — bruker skal se nøyaktig hva som ble værende og hvorfor.

**Files:**
- Modify: `src/lvms_stat/fetch_orchestrator.py` (`FetchOutcome`, `_archive_results`)
- Modify: `src/lvms_stat/qt_app.py` (rød statuslinje ved `failed_archives`)
- Test: `tests/test_fetch_orchestrator.py`

**Step 1: Failing test**

```python
def test_outcome_reports_failed_archives(...) -> None:
    outcome = run_incremental_fetch(...)  # med statistics_root som feiler
    assert outcome.failed_archives  # navngitte filer
    assert "arkivering feilet" in captured.out.lower()
```

**Step 2:** `FetchOutcome` får `failed_archives: tuple[str, ...] = ()`; `_archive_results` fanger `ArchiveError` per fil, samler navn, skriver `ARKIVERINGSFEIL: <fil> ligger fortsatt i <rådata> (<årsak>)` og returnerer likevel outcome (fetch var OK). `qt_app` viser rød melding med stien når listen ikke er tom.

**Step 3: Verify** — pytest → PASS. **Commit:** `feat: loud archive failures with remaining-file paths`

---

### Task 5: Selvhelbredende units.json (fiks «1 kode»-symptomet på alle maskiner)

**Objective:** Gammel/degenerert units.json repareres automatisk ved innlasting — ingen manuell filjobb på jobb-PC.

**Files:**
- Modify: `src/lvms_stat/settings_store.py` (`load_settings`-healing)
- Test: `tests/test_settings_store.py`

**Step 1: Failing test**

```python
def test_legacy_units_without_per_report_lists_are_rebuilt(tmp_path):
    # units.json in the OLD shape: flat analysis_codes, no reports[]
    write_units({"units": {"solide": {"analysis_codes": ["EKSTRAKSJON-SO-OU"]}}})
    settings = ss.load_settings()
    solide = next(u for u in settings.units if u.key == "solide")
    extraction = next(r for r in solide.reports if r.job_key == "extraction")
    assert len(extraction.analysis_codes) == 25
    assert extraction.analysis_codes[0].startswith("EKSTRA")
    assert extraction.fetch_report_id == "PAT-DIT-RESULTATER-OU"
    # original file preserved:
    assert Path(backup).exists()
```

**Step 2:** Utvid healingen: hvis noen `reports[]` mangler `analysis_codes`/`fetch_report_id` (gammel form) → bygg rapportlistene fra `DEFAULT_UNITS` (bevar brukerens øvrige felter), skriv `.bak-<dato>`-kopi før overskriving. Logg linjen `[units] utdatert format - rapportkodene ble gjenopprettet fra spesifikasjonen` til stream/GUI-loggen.

**Step 3: Verify** — `pytest tests/test_settings_store.py -v` → PASS. **Commit:** `fix: auto-repair legacy units.json with default per-report codes`

---

### Task 6: Oppsett — sti-validering + «gjenopprett standard koder»

**Objective:** Brukeren skal aldri lure på om stiene er riktige; kodelister kan nullstilles med én knapp.

**Files:**
- Modify: `src/lvms_stat/qt_app.py` (folders_card + units_card)
- Test: `tests/test_qt_app_setup.py` (offscreen)

**Step 1: Failing test** — bygg vinduet offscreen mot tmp-settings; assert at hver stifeled har en status-label `✓ finnes` / `⚠ opprettes ved første henting` basert på `Path.exists()`, og at klikk på «Gjenopprett standard analysekoder» fyller editorene med DEFAULT-listene.

**Step 2:** Legg til `_path_status_label(path_str) -> QLabel` + oppdater ved Lagre; knapp `btn_reset_codes` koblet til `DEFAULT_UNITS`.

**Step 3: Verify** — offscreen-pytest → PASS. **Commit:** `feat: setup page path indicators and reset-codes button`

---

### Task 7: Utrulling — merge til main + jobb-PC-instruks

**Objective:** Slutt på «jeg lastet ned, men ingenting endret seg».

**Files:**
- Modify: `JOBBS-PC.md` (kap. 8: «Verifiser at du har riktig versjon»)

**Steps:**

```bash
# 1. Alt grønt på branch:
PYTHONPATH=src python -m pytest tests/ -q          # forvent: alle grønne
python scripts/local_pipeline_test.py              # forvent: PASS hemato + solide

# 2. Merge til main og push BEGGE:
git checkout main && git pull origin main
git merge --no-ff fix/work-computer-validation -m "merge: incremental fetch, extraction fix, cross-unit isolation"
git push origin main fix/work-computer-validation

# 3. Verifiser remote:
git ls-remote origin refs/heads/main               # forvent: merge-commit-sha
```

I `JOBBS-PC.md` legges inn:

```text
Etter git pull: kjør  git log --oneline -1
Du skal se merge-committen "... merge: incremental fetch ..." øverst.
Ser du ae5588e eller noe annet, har du ikke fått de nye filene -
sjekk branch (git branch --show-current) og kjør git pull på nytt.
```

**Commit:** `docs: jobbs-pc version verification steps`

---

### Task 8: Ende-til-ende-verifikasjon (inkl. Citrix-blikk)

**Steps:**

1. Full suite: `PYTHONPATH=src python -m pytest tests/ -q` → alle grønne.
2. Offscreen E2E begge enheter mot lokal rot (`C:/Users/molpa/Documents/LVMS-STAT/Statistikk`): verifiser at `solide/raa/PAT-DIT-*-OU/*.csv` har **kanoniske** navn og at ingen hemato-fil havner under solide.
3. Simuler feilsituasjon: pek rot på en utilgjengelig sti → verifiser rød ARKIVERINGSFEIL-melding med filsti i GUI-loggen.
4. Valgfri visuell sjekk av appen inne i Citrix-vinduet med `computer_use` (kun observasjon/screenshot; vi kan ikke kopiere tekst inn i VM — brukeren skriver kommandoer selv, vi leser skjermbildet).

---

## Risikoer / tradeoffs

- **Prefikserte staging-navn** endrer filnavn i `rådata` midlertidig. Gamle uforskyvede filer derfra blir «ukjente» og skipps av arkiveringen — de må ryddes manuelt én gang (dokumenteres i JOBBS-PC.md: sammenlign mot `<rot>/<enhet>/raa/` før sletting).
- Manifestet kan ha rader fra den feilarkiverte hemato-som-solide-kjøringen. Disse må ryddes (lite SQL-script eller «sett manifest.toml-side»-notat) ellers nekter `has_filename` senere re-arkivering. Planlegger et lite verktøy `scripts/manifest_remove.py --unit solide --filename ...` i Task 3 hvis tid tillater; ellers notat i planoppfølging.
- `jobs`-parameter-signaturendring i `archive_pending_downloads` berører `scheduled.py`-kall — hold bakoverkompatibel default.
- Citrix-testbegrensning: ingen utklippstavle mellom vert og VM; all verifikasjon der skjer visuelt eller ved at brukeren limter inn logger i chatten.

## Åpne spørsmål

1. Merge rett til `main` (som ovenfor) eller via PR med review først?
2. Skal vi samtidig tømme/rydde den feilarkiverte solide-manifestraden på jobb-PC, eller lager vi verktøy og brukeren kjører det?
