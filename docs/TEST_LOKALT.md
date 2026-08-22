# Test lokalt uten K:\

Alt kan testes på denne PC-en før vi kobler oss på statistikk-området.
Skriptet under simulerer K-strukturen under
`%LOCALAPPDATA%\LVMS-STAT\statistikk-test` og kjører hele kjøren:
merge → prosessering → Power BI-filer.

## Kjør ende-til-ende-test

```cmd
python scripts\local_pipeline_test.py
```

Forventet resultat:

```
merged files      : 3
resultater rows   : 45300
antall rows       : 70117
resultater.csv: 45300 rows, 12 columns, BOM=True
antall.csv: 70117 rows, 5 columns, BOM=True
resultater: vs R-output -> ... cell mismatches: 6
antall: vs R-output -> ... cell mismatches: 0
```

De 6 celleavvikene er en kjent, dokumentert forskjell: R-scriptets
ekstraksjonsmatching er ikke deterministisk når to kandidater har nesten
samme ferdig-tid. Python-porten velger riktig (seneste ferdig-tid).

## Kjøre hele pipeline mot K: senere

1. Kopier `config.example.json` til `config.json` og fyll inn LVMS-verdiene.
2. Sett statistikk-roten (velg én):
   - `LVMS_STATISTICS_ROOT=K:\Sensitivt\...\Statistikk` som miljøvariabel, eller
   - `statistics_root` i `units.json`
3. Legg `Analyse_lookup.xlsx` ved config-filen ELLER på statistikk-roten
   (finnes automatisk i begge steder, samt i Downloads/Statistikk).
4. Test henting + prosessering manuelt:

```cmd
python -m lvms_stat auto --config config.json
```

5. Når det fungerer: planlegg med Windows Task Scheduler:

```cmd
schtasks /create /tn "LVMS-STAT auto" /sc daily /st 07:00 /tr ^
  "python -m lvms_stat auto --config C:\Users\%USERNAME%\Documents\LVMS-STAT\config.json"
```

## Hva som skjer automatisk etter hver henting

1. Nye CSV-er arkiveres (`raa/<rapport-id>/...`) og logges i manifest.sqlite
2. Alle arkiverte filer per rapport slås sammen med dedup (`merged/*.csv`)
3. Python-porten av R-logikken skriver `prosessert/antall.csv` +
   `prosessert/resultater.csv` — samme format som før, PBIX refresher
   uten endringer

Prosessering feiler aldri en henting: er noe galt (f.eks. manglende
lookup), arkiveres rådata trygt likevel, og feilen logges.
