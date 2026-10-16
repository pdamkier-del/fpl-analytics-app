# MM-opfølgning: sandsynligheder, tidsafhængighed og statusudløb

16. oktober 2026. PR #8. Kun læsning af de allerede frosne MM-forudsigelser. Ingen ny modeltilpasning, ingen ændrede forecasts, ingen PM/FPL-point/TS/chips. `locked_model_active=false`.

## Hvad kontrollen ændrer i vores vurdering

Den GW-specifikke FPL-chance som fremmødeloft forbedrer fortsat minut-MAE, selv når usikkerheden beregnes på hele gameweeks i sammenhængende blokke. Samlet spille-Brier forbedres, men den negative spillechance-bias bliver større; lavere gennemsnitsfejl betyder altså ikke perfekt kalibrering. Men 2025/26-gevinsten er ujævnt fordelt over sæsonen, og FPL-statusser har dokumenterede modstridende kampudfald. Dermed er der stadig ikke grundlag for en produktionsgodkendelse eller en påstand om perfekt tilgængelighed.

Den lille ekstra gevinst fra bevarede startminutter er robust i 2025/26, men ikke dokumenteret i 2024/25. Det er en fordel ved betinget startvarighed, ikke et bevis for, at en raskmeldt spiller automatisk skal have sin gamle startchance.

## Protokol og begrænsninger

- Samme historiske cohorts som hovedrapporten: 2024/25 GW22–38 (17 GWs) og 2025/26 GW6–38 (33 GWs). Disse perioder er allerede genbrugt i forskning, ikke nye holdouts.
- Kontrolleret input-SHA256: `9c5caadd41b105456a484d9f718f8a7547fb78afdee1d17830eef90cbbe4f5fa`.
- Parrede 2.000 bootstrap-træk med hele GW-rækker som enhed og sammenhængende blokke på 1, 2 og 4 GWs. Cirkulær moving-block-bootstrap med fast seed; ombrydning er alene et resamplingvalg, aldrig et forecastinput.
- Fire-GW-blokke efterlader få effektive tidsblokke (især de 17 GWs i 2024/25). Intervallerne er følsomhedsanalyser, ikke præcise uafhængige bekræftelser. Ingen korrektion for mange tests eller modelvalg; ukendt kildefejl dækkes ikke af intervallerne.
- Startchance er p; samlet spillechance er p+(1-p)q. Brier, log-loss, bias og reliability beregnes separat. Ti faste reliability-bins; ECE er et deskriptivt, bin-afhængigt mål, ikke et proper scoring rule.
- Betingede smågrupper og tidlige/sene delperioder er post hoc-diagnostik. Der vælges ingen nye vægte eller parametre ud fra dem.

## 2024-25

| MM-arm | Minut-MAE | Start-Brier | Start-logloss | Spille-Brier | Spille-logloss | Spillechance-bias | Modstridende hårde endepunkter |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original | 12.6531 | 0.0811 | 0.2660 | 0.0945 | 0.3166 | -0.0097 | 0 |
| role | 12.3090 | 0.0800 | 0.2598 | 0.0941 | 0.3172 | -0.0124 | 0 |
| role_news_projected | 11.2721 | 0.0750 | 0.2481 | 0.0855 | 0.3137 | -0.0248 | 16 |
| role_source_chance | 11.1603 | 0.0737 | 0.2440 | 0.0833 | 0.3054 | -0.0268 | 16 |
| role_return_carry | 11.3287 | 0.0754 | 0.2488 | 0.0839 | 0.3082 | -0.0221 | 16 |
| role_return_duration | 11.2677 | 0.0750 | 0.2481 | 0.0855 | 0.3137 | -0.0248 | 16 |
| role_chance_return_duration | 11.1563 | 0.0737 | 0.2440 | 0.0833 | 0.3054 | -0.0268 | 16 |

### Parrede MAE-forskelle med fire-GW-blokke

| Sammenligning | MAE-delta [95% interval] | Spille-Brier-delta [95% interval] |
| --- | --- | --- |
| role_source_chance vs role_news_projected | -0.1118 [-0.1367, -0.0872] | -0.0022 [-0.0026, -0.0019] |
| role_return_carry vs role_news_projected | 0.0566 [0.0143, 0.1006] | -0.0016 [-0.0029, -0.0006] |
| role_return_duration vs role_news_projected | -0.0044 [-0.0190, 0.0063] | 0.0000 [0.0000, 0.0000] |
| role_chance_return_duration vs role_source_chance | -0.0040 [-0.0187, 0.0066] | 0.0000 [0.0000, 0.0000] |
| role_source_chance vs original | -1.4928 [-1.6298, -1.3672] | -0.0112 [-0.0128, -0.0095] |

### FPL-kildens chancegrupper

| FPL-procent | N | Faktisk start | Faktisk kampdeltagelse | Ingen minutter |
| --- | --- | --- | --- | --- |
| 0 | 3919 | 0.0010 | 0.0041 | 3903 |
| 25 | 128 | 0.0156 | 0.0547 | 121 |
| 50 | 117 | 0.1026 | 0.3419 | 77 |
| 75 | 229 | 0.2751 | 0.5153 | 111 |
| 100 | 5381 | 0.5573 | 0.7506 | 1342 |
| Ukendt | 3289 | 0.2074 | 0.3022 | 2295 |

100% i FPL er ikke en garanti for valg til XI eller kampdeltagelse. Kildeprocenten kan afspejle sundhed/availability og må ikke identificeres med en ubetinget start-/spillechance. Den testes her alene som loft over MM-marginalen. Strataene er ikke lægeligt verificerede tilgængelighedslabels.

### Stabilitet over evalueringsperioden og kildekonflikter

| Diagnostisk delmængde | N | News-MAE | Chance-MAE | Fuld før-skade-carry MAE | Kun startvarighed MAE |
| --- | --- | --- | --- | --- | --- |
| earlier_evaluation_slice | 6800 | 11.1448 | 11.0491 | 11.1628 | 11.1353 |
| later_evaluation_slice | 6305 | 11.4094 | 11.2802 | 11.5076 | 11.4106 |
| source_medical_selection_returns | 174 | 22.6467 | 22.6068 | 25.4579 | 22.3166 |
| source_out_but_actual_appearance | 10 | 27.9000 | 27.9000 | 27.9000 | 27.9000 |
| source_unknown | 42 | 5.1087 | 5.2099 | 4.9000 | 5.1087 |

## 2025-26

| MM-arm | Minut-MAE | Start-Brier | Start-logloss | Spille-Brier | Spille-logloss | Spillechance-bias | Modstridende hårde endepunkter |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original | 10.5331 | 0.0696 | 0.2289 | 0.0793 | 0.2675 | -0.0095 | 0 |
| role | 10.3871 | 0.0694 | 0.2284 | 0.0758 | 0.2731 | -0.0183 | 19 |
| role_news_projected | 10.3871 | 0.0694 | 0.2284 | 0.0758 | 0.2731 | -0.0183 | 19 |
| role_source_chance | 10.2119 | 0.0683 | 0.2250 | 0.0735 | 0.2642 | -0.0209 | 19 |
| role_return_carry | 10.4083 | 0.0696 | 0.2286 | 0.0742 | 0.2682 | -0.0164 | 19 |
| role_return_duration | 10.3786 | 0.0694 | 0.2284 | 0.0758 | 0.2731 | -0.0183 | 19 |
| role_chance_return_duration | 10.2033 | 0.0683 | 0.2250 | 0.0735 | 0.2642 | -0.0209 | 19 |

### Parrede MAE-forskelle med fire-GW-blokke

| Sammenligning | MAE-delta [95% interval] | Spille-Brier-delta [95% interval] |
| --- | --- | --- |
| role_source_chance vs role_news_projected | -0.1752 [-0.4256, -0.0358] | -0.0023 [-0.0048, -0.0009] |
| role_return_carry vs role_news_projected | 0.0212 [-0.0216, 0.0695] | -0.0016 [-0.0024, -0.0008] |
| role_return_duration vs role_news_projected | -0.0085 [-0.0148, -0.0025] | 0.0000 [0.0000, 0.0000] |
| role_chance_return_duration vs role_source_chance | -0.0086 [-0.0149, -0.0025] | 0.0000 [0.0000, 0.0000] |
| role_source_chance vs original | -0.3212 [-0.5690, -0.1740] | -0.0058 [-0.0088, -0.0040] |

### FPL-kildens chancegrupper

| FPL-procent | N | Faktisk start | Faktisk kampdeltagelse | Ingen minutter |
| --- | --- | --- | --- | --- |
| 0 | 8280 | 0.0005 | 0.0023 | 8261 |
| 25 | 280 | 0.0071 | 0.0464 | 267 |
| 50 | 173 | 0.1098 | 0.2543 | 129 |
| 75 | 488 | 0.3135 | 0.4959 | 246 |
| 100 | 7840 | 0.5491 | 0.7481 | 1975 |
| Ukendt | 9013 | 0.3079 | 0.4193 | 5234 |

100% i FPL er ikke en garanti for valg til XI eller kampdeltagelse. Kildeprocenten kan afspejle sundhed/availability og må ikke identificeres med en ubetinget start-/spillechance. Den testes her alene som loft over MM-marginalen. Strataene er ikke lægeligt verificerede tilgængelighedslabels.

### Stabilitet over evalueringsperioden og kildekonflikter

| Diagnostisk delmængde | N | News-MAE | Chance-MAE | Fuld før-skade-carry MAE | Kun startvarighed MAE |
| --- | --- | --- | --- | --- | --- |
| earlier_evaluation_slice | 12971 | 10.4216 | 10.1129 | 10.4321 | 10.4205 |
| later_evaluation_slice | 13188 | 10.3531 | 10.3093 | 10.3849 | 10.3373 |
| source_medical_selection_returns | 271 | 22.7956 | 22.6225 | 23.5630 | 21.9741 |
| source_out_but_actual_appearance | 16 | 30.8750 | 30.8750 | 30.8750 | 30.8750 |
| source_unknown | 85 | 6.8320 | 6.9186 | 6.8232 | 6.8320 |

## Konkrete fejl i GW-bred statusbehandling

Der er i alt **35** evaluerede spillerkampe, hvor news-/rollearmen gav præcis nul spillechance, men spilleren faktisk deltog (16 i 2024/25, 19 i 2025/26). De inkluderer skade-, karantæne- og andre unavailable-statusser; det er ikke 35 verificerede medicinske fejl. Alle gemmes med kanoniske ID’er, kilde-URL/commit, råtekst, deadline, kickoff og minutter i `endpoint_conflicts.csv`. Udfaldene bruges ikke til at omskrive forecasts eller tilgængelighedslabels.

Tre konkrete karantænetilfælde viser et problem ved at videreføre samme hårde GW-status til begge kampe i en dobbelt-GW:

| Spiller | GW | Kildetekst ved cutoff | Senere kamp | Faktiske minutter |
| --- | --- | --- | --- | --- |
| Curtis Jones | 2024/25 GW25 | Suspended until 19 Feb | 19. februar 2025 | 90 |
| Eddie Nketiah | 2024/25 GW32 | Suspended until 16 Apr | 16. april 2025 | 34 |
| Marc Guéhi | 2024/25 GW32 | Suspended until 16 Apr | 16. april 2025 | 90 |

Kildens dag/måned matcher den senere kamp. Det beviser, at en GW-bred nulstatus er for grov i disse tilfælde; det genskaber ikke i sig selv et juridisk/medicinsk fuldt udløbstidspunkt. Vi opfinder ikke år, klokkeslæt, kampantal eller en raskmelding. Før en generel rettelse aktiveres, skal karantæner scoped til de konkrete kampe via verificerede disciplinære oplysninger. En kildes forventede skadesretur kan heller ikke bruges som sikker slutdato.

Andre nulstatus-konflikter omfatter blandt andet Tuanzebe, Sels og Stach med 90 faktiske minutter samt stale loan/unavailable-tekst. Arkivversion og klokke er verificeret; årsagen til fejlen i den officielle status er ikke dermed verificeret. Fravær og præcis kampklarhed kan ikke udledes sikkert af FPL-status alene.

**Sandsynlighedskonsekvens:** et nulendepunkt med positivt udfald har teoretisk uendelig log-loss. Rapportens finite log-loss bruger det eksplicitte numeriske klip 1e−12, som i hovedanalysen; det fjerner ikke denne modelbegrænsning. Et lille generisk epsilon-loft er ikke indført som uvalideret ny modelparameter.

## Anbefaling og næste datakrav

1. Bevar den låste produktions-MM. Chance-loftet er fortsat en forskningskandidat; det er ikke en kalibreret medicinsk posterior.
2. Prioritér verificerede, kampafgrænsede karantæneudløb og nyere team news ved lange deadlines/DGWs frem for flere manuelle spillerparametre.
3. Bevar den normale rolle separat; afvis automatisk genbrug af hele startchancen ved returnering. Undersøg startvarighed videre på nye data.
4. Indsaml nye prospektive observationer eller et dokumenteret uberørt historisk datasæt før promotion. Ingen af de ekstra delperioder må omdøbes til et nyt holdout.

## Reproduktion

38 fokuserede MM/source-regressionstests bestået lokalt (10 nye tests). Den dedikerede workflow `.github/workflows/mm-probability-robustness.yml` genskaber resultaterne fra den permanente checksum-verificerede kapsel, kontrollerer at predictions ikke ændres og at hele produktionsmappen `src` er uændret.

```sh
python scripts/archive_role_injury_mm.py --restore work/mm-probability-input
python scripts/restore_core_checkpoint.py
cp work/mm-probability-input/results/predictions.npz work/mm-probability-input/results/source_backed_news.csv.gz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/validate_mm_probability_robustness.py
```

Alle tal/reliability-bins og bloklængder findes i `analysis/results/mm-probability-robustness-20261016/report.json.gz` (JSON efter gzip-udpakning), `reliability.csv` og `endpoint_conflicts.csv`. Ingen nye forecasts eller private managerdata er publiceret.

[GitHub Actions-kørsel 38927430361](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38927430361) er bestået: 38 tests, genskabelse fra permanent kapsel, præcis JSON-/CSV-indholdsreproduktion, uændrede prediction-bytes og uændret produktionskode. Se `reproduction.json` for hashes. Den første kørsel manglede HTTP-testafhængigheden requests; det blev rettet. Den næste sammenlignede gzip-repræsentationer på tværs af codec-versioner. Den endelige kontrol sammenligner udpakket JSON byte for byte uden afrunding eller tolerancer; kompressionen er ikke en del af modelresultatet.
