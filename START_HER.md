# Start her

## Første oppsett på jobb-PC-en

1. Kopier `config.example.json` til `config.json`.
2. Kontroller `jobs.hematology-test.json`. Appen bruker denne filen direkte for
   den godkjente korte testen.
3. Fyll inn lokale LVMS-verdier i `config.json`. Den blir ikke lagt til i Git.
4. Dobbeltklikk `LVMS-STAT_INSTALLER.cmd` én gang.
5. Vent til Python FELLES viser `>>>`, trykk `Ctrl+V` og deretter `Enter`.
6. Når installasjonen er ferdig, lukk hele Python FELLES.

`config.json` trenger bare:

- LVMS landing-URL og forventet origin.
- En egen Edge-profil under Local AppData.
- En nedlastingsmappe under Local AppData.

`jobs.hematology-test.json` inneholder nøyaktig jobbene `ordered`, `answered` og
`extraction` med eksplisitte testdatoer.

## Start appen

Dobbeltklikk `LVMS-STAT_START.cmd`. Vent til Python FELLES viser `>>>`, trykk `Ctrl+V` og deretter `Enter`.

Trykk **Kjør rapporter** én gang. Appen viser rapport 1 av 3 til 3 av 3. La det synlige Edge-vinduet arbeide uten manuelle klikk under kjøringen.

Ved feil stopper kjøringen. Den starter ikke automatisk på nytt og overskriver ikke en eksisterende ferdig fil.

## Oppdater senere

Kjør `git pull`, og dobbeltklikk deretter `LVMS-STAT_INSTALLER.cmd` på nytt.
