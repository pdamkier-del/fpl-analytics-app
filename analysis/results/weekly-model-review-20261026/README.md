# Sæsonens model- og holdopfølgning

## Hvad der er ændret

B-appen får **Ugens modelrapport** i den eksisterende desktopnavigation og et link på dashboardet. Rapporten opdateres automatisk hver tirsdag kl. 08 UTC samt ved B-publiceringer. Tider vises i Europe/Copenhagen. En manuelt startet kørsel af samme ugentlige workflow er gennemført.

- **Offentlig MM/PM-evaluering:** fejl på minutter, starter/0/60+/90-minutters sandsynligheder, point og bias pr. GW og samlet. Positionsopdeling og kalibreringsdata bevares. Alle arkiverede spillere, også ikke-spillende, tæller med. Minutfejlen er mod FPLs registrerede minutter, ikke en fælles fysisk kampklokke.
- **Spillernes sæsonkurve:** søg/vælg spiller eller følg link fra spillerkortet. Tabellen viser xMin/minutter, P(start) pr. kamp/faktiske starter, xP/point og fejl pr. GW. Spillerens fejl og bias er pr. GW; DGW-kampe summeres, mens den offentlige kalibrering fortsat scorer pr. spillerkamp. Datotidsbinding forhindrer blanding af forskellige rapportversioner.
- **Hold pr. GW:** brugerens egne historiske nettopoint, det lokalt gemte modelforslags forventede og realiserede nettopoint, bedste XI fra samme 15 og ligaens topscorer-XI. Klik på GW viser de gamle hold. Oplysninger, der ikke findes, erstattes ikke med det aktuelle hold eller en ny modelberegning.

## Fire forskellige sammenligninger

1. **Faktisk FPL-hold:** importeret officiel entry-historik, med points minus event_transfers_cost, chip, oprindelige picks og kaptajn/vice. Import og backup bliver i browseren og ændrer aldrig manager-state, købspriser eller aktiv transferplan. `scripts/export_fpl_team_history.py` kan hente den offentlige entry-historik til en privat importfil; der kræves ikke login.
2. **Model før deadline:** den færdige B-transferplan arkiveres lokalt, når transfersiden åbnes før deadline, og når forecast/state/hash/GW matcher. Senere planer kan ikke omskrive den gamle deadline. Der gemmes valgt WC/FH-kandidat frem for alternativet uden chip; BB forventningsscore inkluderer den eksisterende BB-gevinst. Manuelle TC-forslag arkiveres endnu ikke automatisk, da et bekræftet mål mangler. Browserens lokale klokke er ikke uafhængig attestering, og private arkiver indgår ikke i den offentlige MM/PM-måling.
3. **Bedste XI fra den daværende trup:** præcis de samme 15 spillere, samme chip og hits, men XI/kaptajn valgt efter resultaterne. Scoringen håndterer normal formation, GK-bænk, prioritetsrækkefølge for markspillerudskiftninger, vicekaptajn, negative kaptajnpoint, BB, TC og hits. Det er et hindsight-benchmark, ikke en forudsigelse.
4. **Ligaens topscorer-XI:** en separat eksakt heltalsoptimering på endelige historiske spillerpoint: 11 spillere, 1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD, højst tre pr. klub og normal dobbelt kaptajn. **Ingen budget-, transfer-, bænk- eller chipbegrænsning.** Det er ikke et gennemførligt alternativt sæsonhold. Kun en bevist optimal løsning offentliggøres.

Private importer er transaktionelle. En defekt backup afvises, og den gamle historik gendannes. Den nuværende trup og plan ændres ikke. Historikken kan eksporteres til privat backup; browserlager kan ikke observere eller arkivere nye planer, når browseren er lukket.

## Ærlige tidsstempler og GW8

Den almindelige kilde er `prospective-ledger`, som gemmer reelle før-deadline-prognoser. Der vælges én offentlig prognose pr. origin-GW, og kun den første forecast-GW tæller. Forecastets datotid, oprindelig offentlig registrering, publicering og kampkickoff skal være korrekt ordnet. Færdige og FPL-kontrollerede runder kræves; uafsluttede eller manglende labels er aldrig fejl på nul.

Det nye ledger-format er yngre end de første offentlige B-prognoser. Derfor genfindes også komplette, checksum- og seal-verificerede forecast/MM/katalog-filer fra deres **oprindelige offentlige Git-commit før deadline**. Prognoserne genberegnes ikke. Kvitteringen mærkes `original_public_forecast_snapshot`, og den nye recovery-tid adskilles fra den oprindelige publicering.

- GW8-kilde: `e0afd754ec1dd8776b325a00f69a0bd08591fd2a`, publiceret **23. oktober 2026 kl. 16.29.56 UTC**, før deadline kl. 17.30 UTC. Prognosedata er fra kl. 16.11.01 UTC. Alle 668 spillerkampe er scoret mod endelige FPL-data.
- Første måling: minut-MAE **12,31899**, minutbias **−0,52145**, start-Brier **0,0870554**, xP-MAE **1,08173** og xP-bias **−0,05203**. Én runde er ikke et bevis for sæsonlang præcision eller en bestemt modelændrings effekt.
- GW1–7 mangler verificerbare før-deadline-B-prognoser i dette offentlige arkiv. GW9 har en rettidigt gemt prognose og afventer kampresultater.
- FPLs endelige event-live-data kan dokumentere ægte nul minutter/starter/point. En manglende spiller-/historikrække bruges ikke som et opdigtet nul. Spillede kampe matches via fixture, kickoff, klub og stabilt FPL-spillerkode. Labels og deres kildetype/URL gemmes i `outcomes.json`, som er bundet til rapporten med SHA256.

## Hvad der stadig kræver brugerdata

Brugerens link `/en/my-team` er loginbeskyttet og identificerer ikke en offentlig entry. Derfor er de gamle faktiske ejerhold ikke hentet eller opfundet. Offentligt `/entry/<id>/event/...`-link eller en historikimport kræves for at udfylde dem. Gamle private TS-forslag fra før denne arkivering kan heller ikke genskabes ærligt med dagens model. Den offentlige modelmåling fungerer uden disse private data.

## Test og release

1.039 Python-regressioner består på den endelige funktionelle kilde. Dertil kommer JS-kontroller af autosubs, kaptajn/vice, BB/TC/hits, historikfrysning og uændret manager-state. Hindsight-MILP sammenlignes med en uafhængig fuld enumerering i test. Browserprøver bruger tydeligt syntetiske private hold og scorer ikke brugerens faktiske hold.

Den publicerede app er kontrolleret på desktop og mobil med normal TLS-verifikation, herunder spillersøgning, gamle hold, import/eksport og fejlsikker gendannelse. Alle 88 produktionsfiler og de tre numeriske B-forecastfiler er byteidentiske med de bevarede referencefiler. Den numeriske B-kilde er fortsat `03d5c4d4777b44bc1d37884a1cf4dde106b45cab`; publiceringerne genbruger den validerede kørsel `40326621197`. Der er ingen ændring af MM/PM/TS-matematik, modeltræning eller produktionens modelfiler.


### Endelig verifikation

- Funktionel kilde: `c483fd07512279fc33ca7dc16e308956aaad487e`.
- B-publicering: [40406129273](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40406129273), bestået; CI: 1039 tests, 37,42 s. Lokal fuld suite: 1039 tests, 83,42 s.
- Automatisk rapportworkflow: [40405831779](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/40405831779), bestået. Model- og produktionsfiler uændrede.
- [Publiceret rapport](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/weekly-review.html).
- Faktiske spillerresultater fra GW1–8 vises også uden en arkiveret prognose; manglende prognoser for GW1–7 vises som manglende og indgår ikke i fejlmålene. Sæsonen bindes til det checksum-verificerede fixturearkiv, hvis kataloget mangler sæson; startårsstrengen `2026` normaliseres til `2026-27`.
- Autosubs følger FPLs definition af deltagelse: en optræden på banen eller et gult/rødt kort. Derfor tæller et kort ved nul minutter som deltagelse ved holdscoring, uden at ændre MM's minutlabels. Hindsight-kaptajnvalget er også testet med udelukkende negative resultater.
- Private modelarkiver gemmer hele den præcise input-state, state-hash, forecast-seal og kildekodeversion.
- De vedlagte JSON-beviser dokumenterer offentlige browserkontroller, integritet, officielle scoringsregler og to uafhængige kontroller mod offentlige FPL-resultater. Kontrolholdet er ikke brugerens hold.
