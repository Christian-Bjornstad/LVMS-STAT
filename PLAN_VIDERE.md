# Plan videre

## 1. Bekreft tre rapporter på jobb-PC-en

- Kjør én kort dato-periode.
- Bekreft at `ordered`, `answered` og `extraction` lastes ned og får riktige filnavn.
- Juster bare de konkrete LVMS-feltene som eventuelt ikke gjenkjennes.

## 2. Historisk uthenting

- Del perioden fra 2024 til i dag i håndterbare intervaller.
- Lag en lokal kjørelogg basert på jobb, fra-dato og til-dato.
- Hopp over intervaller som allerede er fullført, uten å lese pasientinnholdet.

## 3. Daglig og ukentlig kjøring

- Legg til valgene **Siste døgn**, **Siste uke** og **Egendefinert periode**.
- Kjør automatisk bare når jobb-PC-miljøet og LVMS-økten er tilgjengelig.
- Vis siste vellykkede kjøring og neste planlagte kjøring i appen.

## 4. Datasett og Power BI

- Kartlegg kolonnene lokalt på jobb-PC-en.
- Fjern eller erstatt pasientidentifikatorer før videre behandling.
- Slå sammen rapportperioder og fjern duplikater etter en dokumentert nøkkel.
- Lag ett godkjent, Power BI-klart datasett og en kontrollert oppdateringsrutine.
