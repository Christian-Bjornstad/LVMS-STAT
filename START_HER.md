# Start her

## Første oppsett på jobb-PC-en

1. Hent siste kode med `git pull`.
2. Dobbeltklikk `LVMS-STAT_INSTALLER.cmd` én gang.
3. Vent til Python FELLES viser `>>>`, trykk `Ctrl+V` og deretter `Enter`.
4. Når installasjonen er ferdig, lukk hele Python FELLES.
5. Dobbeltklikk `LVMS-STAT_START.cmd` og lim inn startkommandoen på samme måte.
6. Åpne **Oppsett** i appen, kontroller verdiene og trykk **Lagre oppsett**.

Du skal ikke kopiere eller gi nytt navn til JSON-filer for å starte GUI-et.
Appen lagrer aktivt oppsett her:

```text
%LOCALAPPDATA%\LVMS-STAT\
├── settings.json
└── units.json
```

Repoet har også `config.json`, `jobs.json` og `units.json`, med parallelle
`*.example.json`-filer. Disse er trygge standard-/demofiler for eksplisitte
CLI-kjøringer og dokumentasjon. De inneholder ikke personlig innlogging.
`jobs.json` brukes ikke av GUI-et.

## Start appen

Dobbeltklikk `LVMS-STAT_START.cmd`, eller kjør:

```cmd
python -m lvms_stat app
```

Trykk **Hent nå** for ønsket enhet. La det synlige Edge-vinduet arbeide uten
manuelle klikk mens rapportene hentes.

## Oppdater senere

Kjør `git pull`, og dobbeltklikk deretter `LVMS-STAT_INSTALLER.cmd` på nytt.
Oppsettet under Local AppData blir ikke overskrevet.
