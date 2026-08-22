# LVMS-STAT på jobb-PC — steg-for-steg guide

Alt er utviklet og validert hjemme mot en lokal kopi av dataene. Denne
guiden tar deg fra «ny maskin» til «kjører automatisk hver natt» på
jobb-PC-en med K:\ montert. Følg kapitlene i rekkefølge.

> **Kort versjon** (hvis alt allerede er satt opp fra før):
> ```cmd
> python -m lvms_stat auto --config config.json
> ```
> og en Task Scheduler-jobb som kjører samme kommando hver natt.

---

## 1. Forutsetninger

| Hva | Status du trenger |
|---|---|
| K:\ montert | `dir "K:\Sensitivt"` svarer uten feil |
| Python FELLES 3.14 (Microsoft Store) | `python --version` |
| PyQt6 installert | `python -c "import PyQt6"` |
| Edge med LVMS-tilgang | du kan logge inn i LVMS manuelt i Edge |
| Repoet | `C:\Users\molpa\Documents\LVMS-STAT` (eller klon på nytt) |

Hvis PyQt6 mangler:

```cmd
uv pip install --system PyQt6
```

---

## 2. Opprett konfig-filer (engang)

Konfig-filene ligger **ved siden av repoet** i `config/`-mappen (eller
rett i repo-roten — velg ett sted og behold det). Kopier eksemplene:

```cmd
cd C:\Users\molpa\Documents\LVMS-STAT
copy config.example.json config.json
copy units.example.json units.json
```

Åpne `config.json` og sett:

- `landing_url` / `expected_origin` — LVMS-adressen dere bruker
- `profile_directory` — en Edge-profilmappe jobb-PC-en har skriverett til
  (f.eks. `C:\Users\<bruker>\LVMS-STAT\edge-profile`)
- `download_directory` — midlertidig nedlastingsmappe (ikke på K:\)

**Ikke** endre `statistics_root` manuelt — den styres av miljøvariabelen
i kapittel 3.

`units.json` fra eksemplet er riktig som den er:

- **hemato** → rapporter `PAT-DIT-ANTALL-OU`, `PAT-DIT-RESULTATER-OU`,
  `PAT-DIT-EKSTRAKSJON-OU`, profile `hemato` (12/5-kolonne-layout)
- **solide** → samme rapportnavn (`-OU`), men eksporten fra LVMS skal
  lagres i `...\Statistikk\Solide\`-undermappen; profile `solide`
  (13/5-kolonne-layout med `Starttid.svartid`)

---

## 3. Pek på K:\ med miljøvariabel

Pipeline finner statistikk-området via `LVMS_STATISTICS_ROOT`:

```cmd
setx LVMS_STATISTICS_ROOT "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk"
```

(`setx` lagrer variabelen permanent — **åpne et NYTT cmd-vindu** etterpå
så den trer i kraft. Sjekk med `echo %LVMS_STATISTICS_ROOT%`.)

Denne mappen skal inneholde:

```
Statistikk\
├── manifest.sqlite          (opprettes automatisk ved første kjøring)
├── Analyse_lookup.xlsx      (kopieres dit av deg, kap. 4)
├── hemato\
│   ├── raa\                 (arkiv, opprettes automatisk)
│   ├── merged\              (opprettes automatisk)
│   └── prosessert\          (antall.csv + resultater.csv → PBIX leser her)
└── solide\
    ├── raa\  merged\  prosessert\   (samme struktur)
    └── Analyse_lookup.xlsx  (solides egen lookup, kap. 4)
```

---

## 4. Kopier oppslagsfilene (engang)

Pipeline trenger to lookup-filer:

```cmd
copy "%USERPROFILE%\Downloads\Statistikk\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Analyse_lookup.xlsx"
copy "%USERPROFILE%\Downloads\Statistikk\Solide\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Solide\Analyse_lookup.xlsx"
```

(Finn de riktige kilde-mappene hvis lookup-filene ligger et annet sted —
pipeline leter i denne rekkefølgen: `K:\...\Statistikk\Solide\` for
solide, config-mappen, statistikk-roten, repo-roten, Downloads.)

---

## 5. Første kjøring — manuelt, med øynene åpne

Første kjøring har ingen historikk i manifestet, så den henter **ett
vindu 01.01.2024 → i dag** per rapport. Dette tar noen minutter.

```cmd
cd C:\Users\molpa\Documents\LVMS-STAT
python -m lvms_stat auto --config config.json
```

Forventet oppførsel:

1. Edge åpner LVMS og eksporterer 3 rapporter for hemato, deretter 3 for
   solide (solide-eksporten lagres i `Solide\`-undermappen).
2. Hver fil arkiveres som `raa\<rapport>\<rapport>__fra__til.csv` **før**
   manifestet oppdateres — stopper noe, mister du ingenting.
3. Etter henting prosesseres begge enheter automatisk:

```
[hemato] prosessert oppdatert: 45300 resultater, 70117 antall-rader
[solide] prosessert oppdatert: 17030 resultater, 27632 antall-rader
```

4. Verifiser mot gullstandarden (tallene fra R-æraen):

| Fil | Forventet rader |
|---|---|
| `hemato\prosessert\resultater.csv` | 45 300 |
| `hemato\prosessert\antall.csv` | 70 117 |
| `solide\prosessert\resultater.csv` | 17 030 |
| `solide\prosessert\antall.csv` | 27 632 |

Begge enheter er validert celle-for-celle mot R-output (hemato: 6 kjente
avvik fra R sin ikke-determinisme; solide: 0 avvik).

**Lukket Edge-vindu / feil?** Bare kjør kommandoen på nytt — manifestet
fortsetter der det slapp, rådata overskrives aldri.

---

## 6. Sjekk Power BI

Åpne `Hemato_Statistikk.pbix` og `Solide_Statistikk.pbix` og trykk
**Oppdater**. PBIX-filene peker allerede på `Prosessert\*.csv`-filene og
trenger ingen endringer — kolonnenavn og -rekkefølge er identiske med
R-output (hemato 12/5 kolonner, solide 13/5 kolonner).

Kontrollspørsmål: stemmer «Antall» og «Andel innen frist» med tallene
fra rapporten du pleier å levere?

---

## 7. Daglig drift — Task Scheduler

Lag `LVMS-STAT_AUTO.cmd` i repo-roten:

```cmd
@echo off
set LVMS_STATISTICS_ROOT=K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk
cd /d C:\Users\molpa\Documents\LVMS-STAT
python -m lvms_stat auto --config config.json >> "%LOCALAPPDATA%\LVMS-STAT\auto-log.txt" 2>&1
```

Registrer en daglig jobb (kjør i et cmd-vindu):

```cmd
schtasks /Create /TN "LVMS-STAT auto" /SC DAILY /ST 06:30 ^
  /TR "C:\Users\molpa\Documents\LVMS-STAT\LVMS-STAT_AUTO.cmd" /F
```

- **06:30** er et forslag — velg et tidspunkt før statistikkmøter, etter
  at gårsdagens resultater er godkjent i LVMS.
- Jobben krever at PC-en er på og logget inn (Edge-automatisering trenger
  en interaktiv økt). Står maskinen av, kjøres ingenting — neste kjøring
  henter alt som har blitt av manifestet, med 3 dagers overlapp.
- Loggen havner i `%LOCALAPPDATA%\LVMS-STAT\auto-log.txt`.

---

## 8. Appen (valgfritt, til daglig bruk)

```cmd
python -m lvms_stat app --config config.json
```

Sidemeny til venstre, status per enhet, «Hent nå»-knapp og loggside.
Samme pipeline, samme manifest — appen og den nattlige jobben kan brukes
om hverandre.

---

## 9. Feilsøking

| Symptom | Løsning |
|---|---|
| `Klarte ikke lese oppsettet` | `units.json`/`config.json` mangler ved siden av config-path — se kap. 2 |
| Henting stopper ved innlogging | Logg inn i LVMS manuelt i Edge én gang; profilen husker det |
| `prosessering feilet: Analyse_lookup.xlsx ikke funnet` | Kap. 4 — sjekk at filen ligger der |
| Rader mangler mot tabellen i kap. 5 | Sjekk at hele datovinduet ble hentet (`auto-log.txt`); kjør `auto` på nytt |
| PBIX viser gammelt | Sjekk at `prosessert\*.csv` har oppdatert tidsstempel; oppdater PBIX |
| Alt annet | Rådata er alltid trygt arkivert under `raa\` — ingenting kan ødelegges ved å kjøre på nytt |

---

## 10. Hva du IKKE skal gjøre

- **Ikke** slett eller rediger filer under `raa\` — det er rådataene.
- **Ikke** rediger `manifest.sqlite` for hånd.
- **Ikke** endre rapport-ID-er i `units.json` uten å vite hva manifestet
  har logget (ny rapport-ID = nytt datovindu fra 01.01.2024).
- **Ikke** flytt PBIX-filene uten å oppdatere datakildene i dem.
