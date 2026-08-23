# Integrer LVMS-STAT i eMolPat

Denne filen kan gis direkte til kodechatten som arbeider med eMolPat.

## Oppdrag

Legg **LVMS-STAT 2.0.0** inn som en femte applikasjon i eMolPat. Arbeidet skal
baseres på branchen
[`codex/portal-stabilization`](https://github.com/Christian-Bjornstad/eMolPat/tree/codex/portal-stabilization),
verifisert på commit `4239d943b87477578c405a9af86ec5194a471d8b`. Behold branchens nye
prosessmanager, portal som forblir åpen og gruppering med `ModuleUnit`.

LVMS-STAT skal vises i gruppen **Statistikk** (`unit: "stat"`). eMolPat skal
bare installere, verifisere og starte applikasjonen. All LVMS-innlogging,
rapporthenting, Local AppData-konfigurasjon og lesing/skriving på K-disken skal
fortsatt eies av LVMS-STAT.

## LVMS-STAT-kontrakt

- Repository: `https://github.com/Christian-Bjornstad/LVMS-STAT.git`
- Distribution: `lvms-stat`
- Importnavn: `lvms_stat`
- Versjon: `2.0.0`
- Null-arguments startpunkt: `lvms_stat.portal:main`
- Testkommando: `python -m pytest -q`
- Runtime: Python `>=3.11`, PyQt6 og `websocket-client`
- Ingen argumenter eller JSON-filer skal sendes inn ved oppstart.
- Aktiv konfigurasjon ligger i
  `%LOCALAPPDATA%\LVMS-STAT\settings.json` og `units.json`.

Pin den nyeste LVMS-STAT-commiten som inneholder `lvms_stat.portal:main`, ikke
en flytende branch. Ikke pin den eldre `2c61127`, siden portaladapteren kom
etter denne.

## Endringer i eMolPat

1. Legg en ren LVMS-STAT-checkout under `eMolPat-components/LVMS-STAT` og pin
   eksakt commit i `release/components.json`, omtrent slik:

   ```json
   {
     "id": "lvms-stat",
     "repository": "https://github.com/Christian-Bjornstad/LVMS-STAT.git",
     "commit": "<EKSAKT_LVMS_STAT_COMMIT>",
     "distribution": "lvms-stat",
     "import_name": "lvms_stat",
     "entry_point": "lvms_stat.portal:main",
     "test_command": "python -m pytest -q"
   }
   ```

2. Legg `lvms-stat` i `APPROVED_MODULE_IDS` og alle andre eksplisitte
   allowlister/manifestvalidatorer.
3. Legg komponentmappen og distributionen til i byggescriptets allowlister.
4. Legg til et kort i `suite-manifest.json` med:
   - ID `lvms-stat`
   - navn `LVMS Statistikk`
   - versjon `2.0.0`
   - unit `stat`
   - startpunkt `lvms_stat.portal:main`
   - korte norske og engelske beskrivelser
   - et ikon som følger portalens eksisterende ressursmønster
5. Oppdater forventet leveranse fra fire til fem applikasjoner og fra fem til
   seks wheels totalt (portal + fem komponenter).
6. Oppdater tester, dokumentasjon og release-sjekklister som hardkoder de gamle
   antallene.
7. Bruk eMolPat-versjon `1.1.0`, siden dette er en ny brukerrettet modul.

`websocket-client` finnes allerede i branchens Python 3.14-wheelhouse. Ikke
legg pasientdata, rårapporter, Local AppData-filer eller K-diskinnhold i
eMolPat-pakken.

## Akseptansekriterier

- Portalens manifest- og konsistensvalidering godtar fem moduler.
- Offlinebygget inneholder seks korrekte wheels og ingen uvedkommende pakker.
- `LVMS Statistikk` vises kun under **Statistikk**.
- Klikk starter én separat LVMS-STAT-prosess via den eksisterende
  `ApplicationProcessManager`; eMolPat-portalen forblir åpen.
- Gjentatte klikk følger portalens eksisterende beskyttelse mot duplikate
  prosesser.
- Når LVMS-STAT lukkes, registrerer portalen avslutningen uten å krasje.
- LVMS-STAT åpner med tidligere lagret Oppsett fra Local AppData og krever
  ingen omdøping av `config.json`, `jobs.json` eller `units.json`.
- Eksisterende fire applikasjoner starter fortsatt som før.
- Hele testpakken, manifestverifikasjonen og offline release-byggingen passerer.
- En sluttkontroll gjennomføres på Python FELLES/Citrix med tilgang til LVMS og
  K-disken.

## Viktig avgrensning

Ikke flytt LVMS-STAT-logikk inn i portalprosjektet. eMolPat skal ikke kjenne
rapport-ID-er, analysekoder, mapper for rådata/prosesserte data eller detaljer
om Citrix/LVMS. Integrasjonen er kun pakking, presentasjon og prosessoppstart.
