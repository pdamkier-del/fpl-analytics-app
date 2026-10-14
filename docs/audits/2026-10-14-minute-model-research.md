# Minutmodellen: komponentaudit og tidsopdelte forsøg

Fortsættelse af [PR #3](https://github.com/pdamkier-del/fpl-analytics-app/pull/3). Alle forsøg er isolerede. Den låste produktionskode, originale koefficienter, MM/PM/TS/chipstrategier og historiske referencefiler er bevaret. `locked_model_active=false`. Ingen private managerdata indgår.

## Datagrundlag og hvad testen kan bevise

Core-checkpointet er checksum-verificeret. De arkiverede 2025/26-MM-prognoser indeholder 26.159 spiller/kamp-rækker; den uændrede 2024/25-adapter genskaber 24.072. Identiteter, startere og minutter er sammenholdt med Core uden nulimputation. For begge sæsoner ligger target-kickoff efter cutoff; kompositionen matcher de arkiverede xMins med maksimal afvigelse omkring 2e-14.

Nye historiske features udvælger konsekvent `outcome_known_at < cutoff` efter tidspunkt, ikke GW-nummer. Den gamle 2024-adapters GW-sortering er en sårbarhed, men en særskilt kontrol fandt **nul** tidligere-GW-rækker med udfald efter cutoff i den konkrete kørsel. Det er ikke dokumentation for generel sikkerhed ved fremtidige udskudte kampe.

Der bruges fortsat kickoff+4h i 2024 og +3h i 2025 som dokumenterede tilgængelighedsproxies. Det er ikke de faktisk observerede historiske publiceringstidspunkter. Final-season-rosters og 2024's formation-/nyheds-/penalty-proxies er ikke fuldt certificerede. Den låste baseline blev tidligere udviklet med disse sæsoner. Der er derfor en streng tidsmæssig fit/feature-adskillelse i kandidaterne, men **ikke** et pristine, uafhængigt holdout for hele den låste model eller en kildecertificering.

Core har ingen udfyldte historiske `absence_reason`, `sub_off_second` eller `matchday_squad` i de fire tilgængelige sæsoner. 2025/26 har dog separate cutoff-kontrollerede Team News-stater, inklusive 668 `RETURNED_AVAILABLE`-rækker i evalueringskohorten. De rapporteres særskilt; et langt spillerhul bliver aldrig omdøbt til en dokumenteret skade. PL-baserede restitutionsfeatures må heller ikke forveksles med komplet workload fra alle turneringer.

## 1. Additiv fejlattribution

Den låste model komponerer

\[
\hat M=pS+(1-p)qC.
\]

Her er p startchance, S minutter betinget på start, q indskiftningschance betinget på ikke at starte og C minutter ved indskiftning. Lad y være faktisk start og z en faktisk indskiftning. Den observerede fejl har den eksakte identitet

\[
\hat M-M=(p-y)(S-qC)+y(S-M)+(1-y)(q-z)C+(1-y)z(C-M).
\]

De fire led er henholdsvis startvalg, startvarighed, indskiftningsvalg og indskiftningsvarighed. Rapporten viser signed bias, isoleret absolut størrelse, kovariansfordeling af MSE og en Shapley-fordeling af MAE. MAE-Shapley er gennemsnittet af hvert leds marginale bidrag over alle 24 indsættelsesrækkefølger og summerer præcis til den samlede MAE. Fortegn og modgående fejl respekteres: komponentbidrag kan være negative.

| MAE-attribution, hele GW6–38-kohorten | 2024/25 | 2025/26 |
| --- | ---: | ---: |
| Startvalg | 73,74 % | 69,96 % |
| Startvarighed | 12,90 % | 14,78 % |
| Indskiftningsvalg | 8,07 % | 9,32 % |
| Indskiftningsvarighed | 5,28 % | 5,94 % |

Dette er **deskriptiv attribution, ikke kausal forklaring**. 70 % betyder ikke, at en startmodel kan fjerne 70 % af fejlen. Selv korrekt kalibrerede startchancer giver store fejl på enkelte uventede fravær/starter.

Faste startere defineres før cutoff som mindst seks registrerede tidligere fixtures, alle seks seneste startet. I 2025/26 er deres gennemsnitlige forecast-startchance 87,74 %, mens 87,93 % faktisk starter; der er ikke belæg for generelt at tvinge dem til 100 %. Rotationsspillere har langt større minut-MAE end reserver. Høj tidligere mål/assist-produktion er en eksplicit observationsbaseret analysegruppe, ikke en manuelt tildelt stjernerolle eller en særjustering.

## 2. Haaland: eksakt matematisk forklaring

Snapshot-cutoff: **2026-10-12T10:45:27.093744+00:00**. Seks PL-starter, minutter `[90,90,90,90,90,79]`, i alt 529.

Den låste varighedshalveringstid er **0,321926 kampe**. Normaliserede startervægte er ca. `[0,000019;0,000161;0,001384;0,011918;0,102637;0,883881]`. Den seneste 79-minutters kamp bærer således **88,39 %** af varighedsvægten og giver S=80,277304.

\[
\hat M=0,8382304242\cdot80,2773039531
 +(1-0,8382304242)\cdot0,4207609277\cdot14,8523640260
 =67,290878548+1,010945715=68,301824263.
\]

Afstanden fra 90 minutter fordeles algebraisk på 13,5483 minutter fra ikke-startgrenen og 8,1499 fra startervarigheden. Det er igen en identitet, ikke en kausal diagnose af den sidste udskiftning.

En eksakt genfitning med uændrede funktioner genskaber følgende trin:

| Startchance-trin | Haaland |
| --- | ---: |
| Oprindeligt normaliseret v2-prior | 91,6029 % |
| Rolle/workload-model, rå | 79,6864 % |
| Rolle/workload efter holdnormalisering | 85,2729 % |
| Performance-residual, normaliseret | 82,8966 % |
| Tilgængelighedsprojektion | 83,3892 % |
| Endelig XI-residual og projektion | 83,8230 % |

Koefficientbidragene til XI-residualens logit ligger i `live_trace.json`. Sekventielle forskelle må ikke kaldes isolerede kausale effekter. Der er ingen verificeret årsagsmærkat for Haalands udskiftning; slutscore alene er ikke kampstillingen, da han gik ud.

MM-input, original PM-input og original forecast deler snapshot. PM's clipped/rounded Normal-sampler har et andet forventet minutgennemsnit end den rå MM-komposition; det er en transformationsforskel, ikke i sig selv et andet cutoff. Appens MM vNext er et særskilt preview og var allerede dokumenteret som **ikke** minutkilden til original PM/TS. Preview-tal må ikke udlægges som en ny sammenhængende MM→PM-kæde.

## 3. Afprøvede kandidater

Udvikling/valg: **2024/25 GW11–21**, med fit kun på udfald strengt kendt før hver origin. Senere evaluering: **2024/25 GW22–38** og **2025/26 GW6–38**. Ved en 2025-origin er afsluttet 2024-historik lovlig træningshistorik; konfigurationerne vælges ikke igen på 2025-resultaterne. Usikkerhedsintervaller anvender fixture-blok-bootstrap.

1. **Partition-only kontrol:** samme p-rangering, én forventet GK og ti forventede markspillere. Hard endpoints og dokumenterede Team News-caps respekteres. Det separerer en del af konsistensrettelsen fra lærte features. Marginalsummer garanterer ikke en realiseret XI i den oprindelige uafhængige PM-sampler.
2. **Varighedshalveringstid 3 og 6:** samme tidligere startminutter og samme øvrige komponenter. Ingen spillerpatch.
3. **Regulariseret logistisk startmodel**, C=0,1 eller 1: baseline-logit, tidligere starter, streak, kendt PL-belastning/rest og startvarighed, position samt holdprojektion.
4. **Hierarkisk startkandidat**, C=0,1 eller 1: desuden L2-regulariserede spiller- og holdintercepts. Det er en partial-pooling/MAP-lignende kandidat, ikke en fuldt estimeret Bayesian varianshierarki. Ukendte spillere/hold får ingen opdigtet individuel effekt.
5. **Empirisk survival**, 21/42 dages halveringstid og priorstyrke 2/8: startere, som fuldfører 90, er censureret ved horisonten; tidligere kortere starter er all-cause exits. De individuelle, recency-vægtede minute hazards shrinkes mod den cutoff-kendte positionspopulation:

\[
h_{i,t}=\frac{d_{i,t}+\tau h_{\mathrm{pos},t}}{r_{i,t}+\tau},\qquad
E[\min(T,90)]=\sum_{t=0}^{89}\prod_{u=0}^{t}(1-h_{i,u}).
\]

Startkandidaten vælges på udviklingsperiodens log-loss; varighedskandidaten på starter-RMSE. Det giver **logistic_1.0** og **survival_42.0_2.0**. Alle fravalgte konfigurationer bevares i resultaterne. Ingen testvinder er automatisk promoveret.

| MM-test | Original MAE / RMSE | Valgt startmodel | Valgt survival | Kombination |
| --- | --- | --- | --- | --- |
| 2024/25 GW22–38 | 12,6531 / 22,3047 | 12,3278 / 22,1002 | 12,9999 / 22,0998 | 12,6830 / 21,9992 |
| 2025/26 GW6–38 | 10,5331 / 20,4945 | 10,5736 / 20,3902 | 10,8313 / 20,2730 | 10,8936 / 20,2403 |

Survival forbedrer starter-RMSE fra 14,7600→11,8991 i 2024 og 14,6848→11,7979 i 2025, men gør samlet MAE dårligere. Kombinationens 2025-MAE-delta er +0,3605 med fixture-interval ca. `[+0,3056;+0,4144]`. Et lavere starter-RMSE er således utilstrækkeligt som acceptkriterium.

Haaland i samme cutoff: start-only 67,6480 xMins, survival-only 71,3927 og kombination 70,7063. Kombinationens startchance er 82,94 %, ikke en tvungen 100 %. Saka får ca. 78,3319 xMins i kombinationen. Disse er shadow-komponenttal, ikke publicerede anbefalinger eller genberegnede aktuelle xP.

## 4. Kampstillings- og fordelingsforsøg

Et dybere kildecheck fandt 380 komplette Premier League-målhændelsesforløb i 2024/25's arkiverede FotMob JSON. Alle afstemmer med slutscore; de verificerede mapping-regler dækker 7.260 starterrækker i GW6–38 og 121.634 femminutters risk-rækker. Der er 760 observerede træner-sider og 38 træneridentiteter. De aktuelle kamptrænere er ikke uden videre pre-cutoff forecast-inputs.

2025's `start_min`/`finish_min` er ikke en erstatning: 12.461 af 12.754 PL-statistikrækker har begge felter, men 8.362 af dem stemmer ikke med `minutes_played`, og 2.850 har ugyldige intervaller. De bliver afvist som ukritisk exit-kilde; ingen timestamps repareres ved gæt.

Den nye hazardtest bruger tidsbins, tidligere rolle/startvarighed/rest og føring/underleg, inklusive sen-kamp-interaktioner. Historiske målforløb bruges kun ved fit på afsluttede, cutoff-kendte kampe. Ved forecast genereres delte Poisson-score-scenarier fra den oprindelige pre-cutoff holdmålprognose. Den faktiske target-stilling, slutscore og target-lineup læses aldrig som forecast-features. Equal-minute goal ordering er ukendt og udelades konservativt fra pre-bin stillingen. Effekter af føring er observationelle, ikke bevist kausale.

Separat føres den empiriske survival-fordeling direkte til en opt-in minut-sampler. Dette tester masse ved 90 og tidlige exits frem for alene at ændre gennemsnittet i originalens Normal-sampler. Original sampler genskabes også efter exceptions. Benchgrenen og alle oprindelige pointregler bevares.

**De fulde PM- og kampstillingsresultater tilføjes efter afsluttede kørsler. Dette checkpoint er ikke en godkendelse.**

## 5. PM, TS og produktionskrav

PM-testen genbygger de oprindelige minutafhængige GA-/DefCon-/own-goal-komponenter efter hver kandidat; den udskifter ikke blot et minutlabel. Original pointmodel, koefficienter, målintensiteter og 400-draw seeds er uændrede. Originale outputs skal matche de frosne referencer eksakt. Pointkomponenterne skal summere til xP. Simulationsgrenene forbruger RNG forskelligt, så fixture-bootstrap dækker ikke al Monte Carlo-usikkerhed.

Benchmark **2.125 point, 44 transfers og 28 hitpoint** bevares. Det eksisterende historiske forecastarkiv mangler de komplette fremtidige seks-GW-celler; der konstrueres ingen falske celler og intet kandidat-TS-total. En fuld MM→PM→TS-promovering er blokeret af dette samt uafhængig kilde-/testvalidering.

Foreløbig beslutning: **ingen udskiftning af produktionen**. MAE, RMSE, proper start/substate scores, kalibrering, spillergrupper og PM skal vurderes samlet. En glattere eller mere plausibel Haaland-prognose er ikke et acceptkriterium i sig selv.

Maskinlæsbare rapporter og CI-artifacts indeholder alle ablationer, inputs/checksums, feature/fit cutoffs og gruppeanalyser. Ingen manager-state eller købspriser er publiceret.

Metodereferencer: [scikit-learn logistic regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression), [ukendte kategorier](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html), [right-censored survival](https://www.statsmodels.org/stable/duration.html). Hazardtestens konkrete matematik og begrænsninger fremgår ovenfor og i koden; referencerne er ikke ekstern validering af FPL-resultaterne.
