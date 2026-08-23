# LVMS-STAT på jobb-PC — steg-for-steg guide

Alt er utviklet og validert hjemme mot en lokal kopi av dataene. Denne
guiden tar deg fra «ny maskin» til «kjører automatisk hver natt» på
jobb-PC-en med K:\ montert. Følg kapitlene i rekkefølge.

> **Hele oppsettet gjøres i appen** — kapittel 2–4 kan erstattes av å
> åpne `python -m lvms_stat app` → **⚙ Oppsett** → verifisere feltene →
> **Lagre oppsett**. JSON-redigering er kun reserve hvis noe henger.

> Repoet inneholder også `config.json`, `jobs.json`, `units.json` og
> tilsvarende `*.example.json`. Du trenger ikke gi noen av dem nytt navn.
> GUI-et bruker de brukerspesifikke filene under `%LOCALAPPDATA%\LVMS-STAT`.

> **Kort versjon** (hvis alt allerede er satt opp fra før):
> ```cmd
> python -m lvms_stat auto --config "%LOCALAPPDATA%\LVMS-STAT\settings.json"
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

**Sjekk at du har siste versjon før du begynner** (gammel kode ga
«ingen endringer»-forvirring og feil rapport-ID ved ekstraksjon):

```cmd
cd C:\Users\molpa\Documents\LVMS-STAT
git pull
python -m lvms_stat --version
```

Versjonen skal være **2.0.0** eller nyere. Er den det, har du alle
fiksene (bl.a. at ekstraksjon kjører RESULTATER-rapporten men lagres
som EKSTRAKSJON-fil). Stemmer ikke: `git log --oneline -1` og se om
du står på `main` med de nyeste commitene.

---

## 2. Sett opp alt i appen (engang)

```cmd
cd C:\Users\molpa\Documents\LVMS-STAT
python -m lvms_stat app
```

Åpne **⚙ Oppsett** i sidemenyen. Alle felt er forhåndsfylt med kjente
verdier — du trenger bare å kontrollere dem:

- **LVMS-adresse** — full HTTPS-adresse til LVMS (f.eks.
  `https://lvms.sykehus.no/clims`)
- **Statistikk-rot** — forhåndsfylt med
  `K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk`
- **Edge-profilmappe / nedlastingsmappe** — forhåndsfylt under
  `%LOCALAPPDATA%\LVMS-STAT\`
- **Enheter** — hemato (70 analysekoder) og solide (70 + 25
  ekstraksjonskoder) ligger ferdig, inkludert rapport-ID-er og profil;
  rediger kun hvis analysetilbudet endrer seg

Trykk **Lagre oppsett**. Appen validerer mot nøyaktig de samme reglene
pipelinen bruker, og skriver to filer:

```
%LOCALAPPDATA%\LVMS-STAT\
├── settings.json   (adresse, statistikk-rot, mapper)
└── units.json      (enheter, rapporter, analysekoder)
```

**Merk:** miljøvariabelen `LVMS_STATISTICS_ROOT` overstyrer fortsatt
statistikkgrotten fra settings.json hvis den er satt (nyttig for test).

---

## 3. Kopier oppslagsfilene (engang)

Pipeline trenger to lookup-filer:

```cmd
copy "%USERPROFILE%\Downloads\Statistikk\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Analyse_lookup.xlsx"
copy "%USERPROFILE%\Downloads\Statistikk\Solide\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Solide\Analyse_lookup.xlsx"
```

(Finn de riktige kilde-mappene hvis lookup-filene ligger et annet sted —
pipeline leter i denne rekkefølgen: `K:\...\Statistikk\<enhet>\`,
config-mappen, statistikk-roten, repo-roten, Downloads.)

## 4. Kopier oppslagsfilene (engang)

Pipeline trenger to lookup-filer:

```cmd
copy "%USERPROFILE%\Downloads\Statistikk\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Analyse_lookup.xlsx"
copy "%USERPROFILE%\Downloads\Statistikk\Solide\Analyse_lookup.xlsx" "K:\Sensitivt\Klinikk\Sensitiv_mappe_MolPat\Hemato\Statistikk\Solide\Analyse_lookup.xlsx"
```

(Finn de riktige kilde-mappene hvis lookup-filene ligger et annet sted —
pipeline leter i denne rekkefølgen: `K:\...\Statistikk\<enhet>\` for
enhets-egen lookup, config-mappen, statistikk-roten, repo-roten, Downloads.)

---

## 4. Første kjøring — manuelt, med øynene åpne

Første kjøring har ingen historikk i manifestet, så den henter **ett
vindu 01.01.2024 → i dag** per rapport. Dette tar noen minutter.

```cmd
cd C:\Users\molpa\Documents\LVMS-STAT
python -m lvms_stat auto --config "%LOCALAPPDATA%\LVMS-STAT\settings.json"
```

Alternativt: trykk **Hent nå** per enhet i appens dashbord — det kjører
nøyaktig samme flyt.

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

## 5. Sjekk Power BI

Åpne `Hemato_Statistikk.pbix` og `Solide_Statistikk.pbix` og trykk
**Oppdater**. PBIX-filene peker allerede på `Prosessert\*.csv`-filene og
trenger ingen endringer — kolonnenavn og -rekkefølge er identiske med
R-output (hemato 12/5 kolonner, solide 13/5 kolonner).

Kontrollspørsmål: stemmer «Antall» og «Andel innen frist» med tallene
fra rapporten du pleier å levere?

---

## 6. Daglig drift — Task Scheduler

Lag `LVMS-STAT_AUTO.cmd` i repo-roten:

```cmd
@echo off
cd /d C:\Users\molpa\Documents\LVMS-STAT
python -m lvms_stat auto --config "%LOCALAPPDATA%\LVMS-STAT\settings.json" >> "%LOCALAPPDATA%\LVMS-STAT\auto-log.txt" 2>&1
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

## 7. Appen (daglig bruk)

```cmd
python -m lvms_stat app
```

Sidemeny til venstre: **Dashbord** (status per enhet + «Hent nå»),
**Logg** og **Oppsett** (alle innstillinger). Appen leser samme
settings/units-filer som den nattlige jobben — de kan brukes om
hverandre.

---

## 8. Feilsøking

| Symptom | Løsning |
|---|---|
| `Klarte ikke lese oppsettet` | Åpne **⚙ Oppsett** i appen og lagre på nytt |
| Henting stopper ved innlogging | Logg inn i LVMS manuelt i Edge én gang; profilen husker det |
| `Analyse_lookup.xlsx ikke funnet` | Kap. 3 — sjekk at filene ligger der |
| Rader mangler mot tabellen i kap. 4 | Sjekk at hele datovinduet ble hentet (`auto-log.txt`); kjør `auto` på nytt |
| PBIX viser gammelt | Sjekk at `prosessert\*.csv` har oppdatert tidsstempel; oppdater PBIX |
| Alt annet | Rådata er alltid trygt arkivert under `raa\` — ingenting kan ødelegges ved å kjøre på nytt |

---

## 9. Hva du IKKE skal gjøre

- **Ikke** slett eller rediger filer under `raa\` — det er rådataene.
- **Ikke** rediger `manifest.sqlite` for hånd.
- **Ikke** endre rapport-ID-er (i Oppsett-siden) uten å vite hva
  manifestet har logget (ny rapport-ID = nytt datovindu fra 01.01.2024).
- **Ikke** flytt PBIX-filene uten å oppdatere datakildene i dem.
