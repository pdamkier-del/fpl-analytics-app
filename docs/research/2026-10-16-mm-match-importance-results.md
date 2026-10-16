# Match importance og kampbelastning: observeret rotation og MM-kildegrænser

Dato: 2026-10-16. PR #8; research-role-injury-club-audit-20261016.

## Konklusion

Den faktiske rotations- og belastningsanalyse er kørt, og den frosne MM-reference A er reproduceret på alle 40 klub-sæsoner. En kontrolleret, kronologisk opdelt analyse finder ekstra forklaringsværdi i turnering/fase for **antal XI-skift** i 2024/25. Det er ikke en test af spilleres forventede minutter og ikke dokumentation for en kausal match-importance-effekt.

**Ingen ny B/C/D-MM-kandidat er simuleret eller produktionsgodkendt.** De krævede deadline-korrekte input er utilstrækkelige. Behold den eksisterende model; integrér ikke de nye kategorier som importance-vægte endnu. `locked_model_active=false`. PM, TS, FPL-point og chips er hverken kørt eller ændret.

## 1. Hentede artifacts og rettelser til den gamle dækningskontrol

Begge beståede inventarkørsler er downloadet, og ZIP-bytes er SHA-256-kontrolleret:

| Actions-run | Artifact-ID | ZIP SHA-256 |
| --- | --- | --- |
| [38935549983](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38935549983) | 12061071746 | fb331f934a747fe6c0eef7e3a9523c20e5b46f4f486a27b39de6e9184b1c71b6 |
| [38937294291](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38937294291) | 12060963430 | abd90223836cb70a32562b09a050d493b7d11cbb7c931887d618d4961b145acd |

ZIP-filerne er bevaret tabsfrit som base64 i `checkpoints/mm_competition_inventory_20261016/`, inklusive manifest. Det gamle inventar var ikke en rotationstest. Dets XI-kontrol brugte spillernavne som fallback for manglende ID'er og klassificerede `-prem-` som ukendt turnering. Derfor var de 874 angiveligt komplette XI'er ikke dokumentation for 874 komplette XI'er med stabile spilleridentiteter. Det gamle 2024-inventar var desuden kørt uden at gendanne det allerede eksisterende 2024-datacheckpoint.

Den nye analyse bruger stabile provider-ID'er, eksakte PL-kamp-/spillerjoins til Core og sæsonbestemte klubidentiteter. Ingen fuzzy navnemapping. 2025-råfilerne verificeres mod Git-blob-SHA i kildemanifestet, pinnet til `olbauday/FPL-Core-Insights` commit `bfcc14deaaa924157eee1d60f33a898cbd64404e`. De eksisterende 40 karantæner respekteres.

## 2. Dækning og observerede indskiftninger

En holdkamp er én klubs deltagelse i én kamp; en kamp mellem to PL-klubber giver to holdkampe. En indskiftning tælles som en identificeret ikke-starter med positive minutter. Tallene er **registrerede nedre grænser**, ikke bevis for komplet hændelsesdækning. XI-skift er `11 − |XI_n ∩ XI_(n−1)|`, kun når begge registrerede opstillinger har 11 identificerede startere.


| Sæson | Turnering | Holdkampe | Komplet XI | Registrerede indskiftninger/kamp | XI-skift fra forrige registrerede kamp | Andel startere præcis 90 min | Andel mindst 90 min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | Champions League | 46 | 46 | 4.109 | 3.413 | 0.621 | 0.636 |
| 2024-25 | Conference League | 13 | 13 | 4.154 | 8.462 | 0.615 | 0.615 |
| 2024-25 | Conference qualification | 2 | 2 | 4.500 | 8.500 | 0.591 | 0.591 |
| 2024-25 | Europa League | 30 | 30 | 4.167 | 4.567 | 0.603 | 0.627 |
| 2024-25 | FA Cup | 61 | 61 | 4.443 | 4.918 | 0.495 | 0.630 |
| 2024-25 | League Cup | 61 | 61 | 4.508 | 6.557 | 0.590 | 0.590 |
| 2024-25 | Premier League | 760 | 760 | 4.220 | 3.046 | 0.613 | 0.613 |
| 2025-26 | Champions League | 42 | 0 | Not Available | Not Available | Not Available | Not Available |
| 2025-26 | Europa League | 13 | 0 | Not Available | Not Available | Not Available | Not Available |
| 2025-26 | League Cup | 52 | 10 | 3.800 | 7.100 | 0.600 | 0.600 |
| 2025-26 | Premier League | 760 | 760 | 4.108 | 2.230 | 0.646 | 0.646 |


Samlet: **35.735 spillerobservationer, 1.840 holdkampe, 1.743 komplette XI'er**. 2024/25 har 1.033 komplette XI'er; 2025/26 har 760 komplette PL-XI'er og 10 komplette League Cup-XI'er, dvs. **770**. Ingen af de europæiske 2025/26-XI'er består kravet om 11 stabile ID'er efter kildefiltreringen. Komplet XI siger ikke, at hele kampprogrammet er komplet.

2025/26: FA Cup mangler helt. Råarkivet har 64 CL-, 28 EL-, 13 Conference- og 40 League Cup-kampenøgler. Henholdsvis 16, 14, 7 og 3 mangler kickoff; henholdsvis 20, 12, 8 og 0 er karantæner (overlappende kategorier). Nogle europæiske nøgler er datoløse klubpar med risiko for overskrevne returkampe. Den eksisterende uafhængige CL-kontrol fandt otte manglende kampe og tidsanker-konflikter. Der er 3.188 rå lineup-rækker uden numerisk spiller-ID i det samlede indlæste arkiv; det er et andet scope end de 924 starterrækker i det gamle artifact. Conference-oplysninger efter filtrering kan ikke danne en pålidelig holdopstilling. Fravær af en pålidelig observation er **ikke** nul deltagelse.

De tidligere genskabte syv predeadline-kildeholdkampe/104 spillerobservationer bevares som evidens; de udfylder ikke sæsonhullerne. 2024-data har kickoff + fire timer som proxy, ingen verificerede historiske publiceringstidspunkter, og `strict_forecast_eligible=false`.

### Alle klubber: observerede komplette XI'er og indskiftninger

`Komplet/observeret` vises for andre turneringer. Tom dækning er Not Available, ikke en påstand om ingen deltagelse. PL-rotation er fra den seneste registrerede kamp i enhver turnering. Den fulde 280-rækkers klub/turnering/sæson-matrix er i `all_club_competition_coverage.csv`; alle turneringsspecifikke klubmål findes i `club_competition_summary.csv`.


#### 2024-25

| Klub | PL-holdkampe | PL indskiftninger | PL XI-skift | Andre turneringer, komplet/observeret |
| --- | --- | --- | --- | --- |
| Arsenal | 38 | 3.737 | 3.297 | Champions League: 14/14; FA Cup: 1/1; League Cup: 5/5 |
| Aston Villa | 38 | 4.474 | 2.973 | Champions League: 12/12; FA Cup: 5/5; League Cup: 2/2 |
| Bournemouth | 38 | 4.263 | 2.405 | FA Cup: 4/4; League Cup: 1/1 |
| Brentford | 38 | 3.737 | 1.784 | FA Cup: 1/1; League Cup: 4/4 |
| Brighton | 38 | 4.842 | 2.946 | FA Cup: 4/4; League Cup: 3/3 |
| Chelsea | 38 | 3.684 | 6.108 | Conference League: 13/13; Conference qualification: 2/2; FA Cup: 2/2; League Cup: 2/2 |
| Crystal Palace | 38 | 3.895 | 2.054 | FA Cup: 6/6; League Cup: 4/4 |
| Everton | 38 | 3.421 | 1.892 | FA Cup: 2/2; League Cup: 2/2 |
| Fulham | 38 | 4.711 | 2.838 | FA Cup: 4/4; League Cup: 2/2 |
| Ipswich | 38 | 4.684 | 3.514 | FA Cup: 3/3; League Cup: 1/1 |
| Leicester | 38 | 4.421 | 2.432 | FA Cup: 2/2; League Cup: 3/3 |
| Liverpool | 38 | 4.342 | 3.541 | Champions League: 10/10; FA Cup: 2/2; League Cup: 6/6 |
| Man City | 38 | 3.447 | 3.838 | Champions League: 10/10; FA Cup: 6/6; League Cup: 2/2 |
| Man Utd | 38 | 4.237 | 3.838 | Europa League: 15/15; FA Cup: 3/3; League Cup: 3/3 |
| Newcastle | 38 | 4.289 | 2.081 | FA Cup: 3/3; League Cup: 7/7 |
| Nott'm Forest | 38 | 4.395 | 2.676 | FA Cup: 5/5; League Cup: 1/1 |
| Southampton | 38 | 4.737 | 3.270 | FA Cup: 2/2; League Cup: 4/4 |
| Spurs | 38 | 4.158 | 4.432 | Europa League: 15/15; FA Cup: 2/2; League Cup: 5/5 |
| West Ham | 38 | 4.526 | 2.486 | FA Cup: 1/1; League Cup: 2/2 |
| Wolves | 38 | 4.395 | 2.514 | FA Cup: 3/3; League Cup: 2/2 |


#### 2025-26

| Klub | PL-holdkampe | PL indskiftninger | PL XI-skift | Andre turneringer, komplet/observeret |
| --- | --- | --- | --- | --- |
| Arsenal | 38 | 4.395 | 2.640 | Champions League: 0/7; League Cup: 0/5 |
| Aston Villa | 38 | 4.605 | 3.241 | Europa League: 0/7; League Cup: 0/1 |
| Bournemouth | 38 | 4.553 | 1.972 | League Cup: 0/1 |
| Brentford | 38 | 3.579 | 1.971 | League Cup: 1/4 |
| Brighton | 38 | 4.684 | 2.265 | League Cup: 0/3 |
| Burnley | 38 | 4.553 | 2.057 | League Cup: 0/2 |
| Chelsea | 38 | 4.158 | 3.417 | Champions League: 0/8; League Cup: 0/5 |
| Crystal Palace | 38 | 3.579 | 2.176 | League Cup: 0/3 |
| Everton | 38 | 3.368 | 1.600 | League Cup: 0/2 |
| Fulham | 38 | 4.605 | 1.818 | League Cup: 0/4 |
| Leeds | 38 | 4.237 | 1.946 | League Cup: 1/1 |
| Liverpool | 38 | 3.974 | 2.107 | Champions League: 0/7; League Cup: 0/2 |
| Man City | 38 | 3.868 | 3.133 | Champions League: 0/6; League Cup: 4/5 |
| Man Utd | 38 | 3.842 | 1.861 | League Cup: 0/1 |
| Newcastle | 38 | 4.474 | 3.074 | Champions League: 0/7; League Cup: 2/5 |
| Nott'm Forest | 38 | 4.079 | 1.867 | Europa League: 0/6; League Cup: 0/1 |
| Spurs | 38 | 4.342 | 2.714 | Champions League: 0/7; League Cup: 0/2 |
| Sunderland | 38 | 3.605 | 1.694 | League Cup: 0/1 |
| West Ham | 38 | 3.526 | 1.730 | League Cup: 1/1 |
| Wolves | 38 | 4.132 | 2.371 | League Cup: 1/3 |


### Udskiftningshændelser og minutter

Antal **udskiftninger ud** og universelle udskiftningstidspunkter er **Not Available**. En starters 20 eller 60 minutter beviser ikke en udskiftning; rødt kort eller skade kan være årsagen. Core har ikke udfyldte sub-on/off-sekunder. Mange 2025-intervaller siger 0–1 trods 90 spillede minutter og afvises.

Kun 42 holdkampe har helholdsintervaller, der stemmer med spilleminutter og præcis 11 startere: 39 PL og tre League Cup. Blandt kampene med registrerede indskiftninger er gennemsnittet af holdkampenes kildebaserede entry-minut **70,636** i PL (38 holdkampe) og **76,633** i League Cup (tre). Det er interval-afledte indskiftningstider, ikke verificerede universelle eventtider eller udskiftningstider ud. Den 39. PL-holdkamp har ingen positiv registreret indskiftning. Ingen troværdig turneringsrangering kan bygges på dette lille udvalg.

Præcis 90 og mindst 90 minutter vises separat, fordi nogle pokalkampe har forlænget spilletid. Vi udleder ikke automatisk, at 90 minutter er en fuld kamp. Startervarighed, hvile før/efter og ukendte minutrækker findes pr. holdkamp.

## 3. PL før/efter cup og Europa

Nedenfor er 2024/25 PL-kampe grupperet efter den seneste **registrerede** turnering. Store ændringer efter cupkampe kan være et roteret cuphold, der skifter tilbage til normal PL-XI; det er ikke nødvendigvis PL-spillere, der hviles på grund af Europa.

| Forrige registrerede turnering | PL-kampe | XI-skift | Observerede hviledage |
| --- | --- | --- | --- |
| Champions League | 44 | 3.273 | 3.688 |
| Conference League | 12 | 9.083 | 2.825 |
| Conference qualification | 2 | 9.000 | 2.750 |
| Europa League | 30 | 5.100 | 2.958 |
| FA Cup | 58 | 4.690 | 5.038 |
| League Cup | 54 | 6.481 | 4.021 |
| Premier League | 540 | 2.237 | 7.048 |


`pl_before_after_recorded_competitions.csv` indeholder begge sæsoner, alle klubber, næste/forrige registrerede turnering og hvilebånd ≤3, 3–6 og >6 dage. `team_match_rotation.csv` giver samtlige underliggende kampe. Efterfølgende kamp og hvile efter kampen er **retrospektive beskrivelser**; de er ikke udgivet som oplysninger kendt ved historiske deadlines. 2025-tabellerne kan have uobserverede cupkampe mellem to registrerede kampe og må ikke læses som et komplet kampprogram.

Individuel kampbelastning er beregnet for hver identificeret observation i `individual_recorded_workload.csv.gz`: registrerede minutter de foregående 7/14 døgn, observerede kampe, rækker med ukendte minutter og hvile til tidligere/næste registrerede positive optræden. En registreret sum på nul betyder ikke dokumenteret nul belastning. Feltet med ukendte minutrækker tæller ikke helt manglende kampe. Spillerens sommer-/klubskiftehistorik kædes ikke sammen med gæt; belastningsserierne grupperes pr. sæson/klub/provider-ID.

## 4. Kontrolleret analyse af turnering/fase

Dette er en reel, reproducerbar kronologisk test af **XI-turnover**, ikke MM-simulation. Kun 2024/25 bruges, hvor hele de observerede XI'er består identitetskravet. Målet er antal ændringer fra forrige registrerede XI.

Kontrolmodellen indeholder klub, hvile, registrerede holdminutter seneste 7/14 døgn, tidligere XI-skift og forrige XI's empiriske starterandel over de seneste fem kampe. Dette sidste er en rolleproxy, ikke en fuldt verificeret normalrolle eller skadesjustering. Udvidelsen tilføjer kategorier for turnering og registreret fase/runde. Ingen håndvalgte importance-vægte.

Ridge-regression med standardiserede numeriske variable og LSQR-tolerance 1e−12; alpha blandt 0,1/1/10/100 vælges med træning før december 2024 og validering i december. Begge vælger alpha=10. Refit før januar 2025 (411 rækker), evaluering fra januar (502). Sæsonen er tidligere brugt til forskning og er **ikke et uberørt holdout**. Historiske kampe bruger +4t-proxy; den aktuelle kampfase har ikke verificeret historisk publicering. Derfor er dette retrospektiv association, ikke deadline-certificeret forecasting.

| Variant | XI-skift MAE | XI-skift RMSE |
| --- | --- | --- |
| load_team_role_controls | 1.550 | 2.067 |
| plus_competition_stage_categories | 1.472 | 1.939 |


Paired MAE-forskel: **-0.078145 XI-skift**, 95 % interval **[-0.150850; -0.008496]**. Intervallet bruger 1.000 cirkulære fireugers blok-bootstraptræk, der holder alle klubber/kampe i samme uge samlet. Det beskriver evalueringsusikkerhed givet tilpassede modeller; ikke usikkerhed fra modelvalg eller alle alternative hypoteser.


| Klub | Evalueringskampe | Kontrol MAE | + turnering/fase MAE | Forskel |
| --- | --- | --- | --- | --- |
| Brentford | 21 | 1.156 | 0.653 | -0.503 |
| Chelsea | 28 | 2.094 | 1.732 | -0.362 |
| Ipswich | 22 | 2.312 | 2.000 | -0.312 |
| Nott'm Forest | 24 | 2.003 | 1.698 | -0.305 |
| Crystal Palace | 25 | 1.114 | 0.850 | -0.265 |
| Man City | 29 | 1.814 | 1.585 | -0.229 |
| Bournemouth | 23 | 1.267 | 1.052 | -0.215 |
| Brighton | 23 | 1.236 | 1.064 | -0.172 |
| Fulham | 23 | 1.745 | 1.625 | -0.120 |
| Southampton | 21 | 1.280 | 1.181 | -0.098 |
| Leicester | 21 | 1.561 | 1.482 | -0.079 |
| Newcastle | 25 | 1.861 | 1.803 | -0.058 |
| Wolves | 22 | 1.659 | 1.631 | -0.028 |
| Man Utd | 31 | 1.525 | 1.577 | 0.052 |
| Everton | 22 | 1.016 | 1.068 | 0.052 |
| Liverpool | 29 | 1.713 | 1.776 | 0.063 |
| Spurs | 32 | 1.823 | 1.944 | 0.121 |
| West Ham | 20 | 1.325 | 1.459 | 0.134 |
| Aston Villa | 30 | 1.156 | 1.311 | 0.155 |
| Arsenal | 31 | 1.182 | 1.524 | 0.342 |


Forbedringen er ikke universel: bl.a. Brentford, Chelsea og Man City forbedres i denne turnover-analyse, mens Arsenal, Aston Villa og Spurs forværres. Klubudsnittene er små og selekterede; de er ikke klubspecifikke importance-parametre. Sammenlignelige effekter for individuelle spillerroller er **Not Available**, fordi dette respons er en holdoptælling, ikke individuelle start-/minutfejl.

Data identificerer ikke, om forskellene *primært* skyldes hvile, tidligere minutter eller kampbetydning. Kontroller reducerer nogle forskelle, men turnering, modstander, trupvalg og sportslige mål er korrelerede. Holdminutter er et groft mål for belastningsfordeling. Koefficienter kan ikke læses som kausale importance-effekter. Ingen verificeret trænerårsag er tilskrevet observerede forskelle.

## 5. MM A/B/C/D: faktisk status

A genberegnes fra de frosne individuelle prognoser på identiske tidligere evalueringsrækker: 39.264 spillerkampe, 501 fixtures, 40 klub-sæsoner. Hver klub-MAE matches mod den eksisterende reference med tolerance 1e−12. Det er replay af den eksisterende MM-kandidat, ikke en ny træning.

| A-mål | Værdi |
| --- | --- |
| minute_mae | 10.521 |
| minute_rmse | 20.417 |
| start_brier | 0.070 |
| start_log_loss | 0.231 |
| starter_duration_mae | 8.065 |
| minute_bias | -0.378 |


Evalueringsscope: 2024/25 GW22–38 og 2025/26 GW6–38. De tidligere anvendte historiske perioder er genbrugte forsknings-/evalueringsperioder. `mm_ablation_availability_all40clubs.csv` indeholder A's komplette klubmål. Rotations-/rolleudsnit for A findes i de tidligere MM-resultater; nye B/C/D-felter er tomme og eksplicit Not Available.

| Arm | Status | Konkret hindring |
| --- | --- | --- |
| A eksisterende kandidat | Reproduceret, MAE 10,521392 | Frossen reference; ingen ny ændring |
| B A + alle turneringers belastning | Ikke kørt; Not Available | 2024-publicering kun proxy; 2025 FA Cup mangler, karantæner, manglende kamp-/spillerversioner og kickoff |
| C B + importance | Ikke kørt; Not Available | B plus manglende deadline-versioner af fase, fremtidig terminliste, tie state, modstanderstyrke og sportslige mål |
| D importance kun startchance | Ikke kørt; Not Available | Samme importance-inputgrænser; ingen opdigtede vægte |
| D importance kun startervarighed | Ikke kørt; Not Available | Samme grænser; utilstrækkelige verificerede udskiftningshændelser |

Det er ikke et negativt statistisk resultat for B/C/D; de kunne ikke testes troværdigt. Vi har derfor heller ikke dokumenteret bedre minut-MAE, start-Brier eller startervarighed via match importance.

### Deadline-korrekt importance: hvad kan og kan ikke beskrives?

| Input | Observeret kilde | Før-deadline-begrænsning |
| --- | --- | --- |
| Turnering/fase/knockout | 2024 postmatch-ledger; ufuldstændigt 2025-arkiv | Historiske offentliggjorte fase-/terminlisteversioner mangler |
| Duelstilling før returkamp | Ikke fuldt forbundet/tidsverificeret | Datoløse returkampnøgler og karantæner; ikke udledt af senere slutresultat |
| Ligaplacering/sportsligt mål | Ikke indført som nyt featurelag | Kræver datidig stilling, tidskorrekte kampe og kalibreret definition; ingen subjektiv importance-score |
| Modstanderstyrke | Nogle Elo-kolonner findes | Deres as-of-status er ikke verificeret til dette forsøg |
| Programtæthed/tidligere minutter | Beregnet som observerede nedre grænser | Ikke komplet kalender eller verificeret publicering |
| Tid til næste kendte kamp | Retrospektivt næste registrerede kickoff | Kræver predeadline-programversion; slutkalender må ikke bruges som kendt program |

Eksisterende importance-/restitutionsmekanismer og låste parametre ændres ikke. Den nye analyse erstatter dem ikke med en selvvalgt numerisk importance-skala.

## 6. Reproduktion, tests og anbefaling

Implementering: `scripts/analyze_mm_competition_rotation.py`. Kildenormalisering, rotationsmål, dokumenterede kildeafvisninger, kronologisk ridge-test, blokintervaller og frossen A-replay er implementeret og kørt. Resultater findes som CSV/JSON plus komprimeret individuel workload, ikke kun workflow-kode.

`rotation_manifest.json` indeholder kodehash, inputchecksums og artifact-ID'er. `rotation_content_manifest.json` indeholder SHA-256 af alle ti numeriske resultatfilers indhold; gzip sammenlignes efter dekomprimering.

```bash
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py
python scripts/restore_2024_25_data_checkpoint.py
python scripts/archive_role_injury_mm.py --restore work/rotation-mm-source
cp work/rotation-mm-source/results/predictions.npz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/analyze_mm_competition_rotation.py
PYTHONPATH=src:scripts:. python -m pytest tests/test_mm_competition_rotation.py tests/test_mm_all_clubs.py tests/test_mm_probability_robustness.py tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
```

**52 tests består lokalt.** De nye regressioner kontrollerer bl.a. forskellen på XI-skift og indskiftninger, afvisning af 0–1-intervaller, ukendt årsag til tidlig exit, ID-krav, dubletter og at fremtidige minutter ikke påvirker tidligere workload. Actions gentager de samme tests og analysen og kontrollerer frosne prognosers checksum og uændret `src` mod produktionsreferencen.

Anbefaling: behold eksisterende MM. Prioritér verificerede predeadline-kalendere og spiller-/eventhistorik i de konkrete manglende turneringer, før nye belastnings-/importance-MM-arme køres. Den observerede turneringseffekt er værd at undersøge videre, men den dokumenterer ikke en produktionsklar forbedring.

### Verificeret GitHub-kørsel og lokal/CI-sammenligning

[Actions 38941461600](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38941461600) består alle trin: 52 MM-/kilderegressioner, gendannelse af arkiver, faktisk analyse og frossen A-replay, uændret produktions-`src`, checksum og resultatpublicering. Implementering `31b736a`; strammet solvertolerance `74645ce`; resultater `915bfea`.

Syv af ti numeriske resultatfilers indhold er byteidentisk lokalt/CI, inklusive observationer, workload, alle klubtabeller og A-reference. De tre filer med regressionsoutput er numerisk kontrolleret med tolerance 1e−9: største forskel i en prognose er **5,05e−12 XI-skift**, største forskel i JSON-tal **1,09e−12**. Strenge, nøgler og rækker matches; forskellen er numerisk afrunding på tværs af runtime. Disse tre filer påstås ikke at være byteidentiske. Det tilhørende `reproduction.json` bevarer målene.
