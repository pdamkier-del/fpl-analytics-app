# Minutmodellen: komponentaudit og tidsopdelte forsøg

Fortsættelse af [PR #3](https://github.com/pdamkier-del/fpl-analytics-app/pull/3). Alle forsøg er isolerede. Den låste produktionskode, originale koefficienter, MM/PM/TS/chipstrategier og historiske referencefiler er bevaret. `locked_model_active=false`. Ingen private managerdata indgår.

## Datagrundlag og hvad testen kan bevise

Core-checkpointet er checksum-verificeret. De arkiverede 2025/26-MM-prognoser indeholder 26.159 spiller/kamp-rækker; den uændrede 2024/25-adapter genskaber 24.072. Identiteter, startere og minutter er sammenholdt med Core uden nulimputation. For begge sæsoner ligger target-kickoff efter cutoff; kompositionen matcher de arkiverede xMins med maksimal afvigelse omkring 2e-14.

Nye historiske features udvælger konsekvent `outcome_known_at < cutoff` efter tidspunkt, ikke GW-nummer. Den gamle 2024-adapters GW-sortering er en sårbarhed, men en særskilt kontrol fandt **nul** tidligere-GW-rækker med udfald efter cutoff i den konkrete kørsel. Det er ikke dokumentation for generel sikkerhed ved fremtidige udskudte kampe.

Der bruges fortsat kickoff+4h i 2024 og +3h i 2025 som dokumenterede tilgængelighedsproxies. Det er ikke de faktisk observerede historiske publiceringstidspunkter. Final-season-rosters og 2024's formation-/nyheds-/penalty-proxies er ikke fuldt certificerede. Den låste baseline blev tidligere udviklet med disse sæsoner. Der er derfor en streng tidsmæssig fit/feature-adskillelse i kandidaterne, men **ikke** et pristine, uafhængigt holdout for hele den låste model eller en kildecertificering.

Core har ingen udfyldte historiske `absence_reason`, `sub_off_second` eller `matchday_squad` i de fire tilgængelige sæsoner. 2025/26 har dog separate cutoff-kontrollerede Team News-stater, inklusive 668 `RETURNED_AVAILABLE`-rækker i evalueringskohorten. De rapporteres særskilt; et langt spillerhul bliver aldrig omdøbt til en dokumenteret skade. PL-baserede restitutionsfeatures må heller ikke forveksles med komplet workload fra alle turneringer. Kampvigtighed og præ-kickoff træneridentitet er ikke tildelt hjemmelavede labels; der mangler et tilstrækkeligt verificeret historisk grundlag for disse features.

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

### Observationstidspunkt og restitution

Et yderligere inputcheck viser, at Haalands observerede `work_player_rest_days`/`work_team_rest_days` er ca. 0,8024 på cutoff og gentages over GW7–12. Ved GW7-kickoff er der ca. 5,9375 dage siden seneste observerede PL-kickoff. Features beskriver dermed observationstilstanden, ikke nødvendigvis restitutionsforholdene på hver fremtidig kampdag. Observationstilstanden er i sig selv et legitimt input, men fortolkning og seks-GW-fremskrivning skal holdes adskilt. Vi har ikke bevist, at denne forskel alene skaber Haalands startchance. Et simpelt skift til target-kickoff løser heller ikke kendte/ukendte mellemliggende kampe eller workload i andre turneringer; sådanne data må ikke opdigtet antages fraværende.

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

Haaland i samme cutoff: start-only 67,6480 xMins, survival-only 71,3927 og kombination 70,7063. Kombinationens startchance er 82,94 %, ikke en tvungen 100 %. Saka får ca. 78,3319 xMins i kombinationen. Disse er raw shadow-komponenttal. Den separate fulde PM-shadow i afsnit 7 anvender samme frosne cutoff; ingen af delene er publicerede anbefalinger eller et nyt live-forecast.

## 4. Kampstillings- og fordelingsforsøg

Et dybere kildecheck fandt 380 komplette Premier League-målhændelsesforløb i 2024/25's arkiverede FotMob JSON. Alle afstemmer med slutscore; de verificerede mapping-regler dækker 7.260 starterrækker i GW6–38 og 121.634 femminutters risk-rækker. Der er 760 observerede træner-sider og 38 træneridentiteter. De aktuelle kamptrænere er ikke uden videre pre-cutoff forecast-inputs.

2025's `start_min`/`finish_min` er ikke en erstatning: 12.461 af 12.754 PL-statistikrækker har begge felter, men 8.362 af dem stemmer ikke med `minutes_played`, og 2.850 har ugyldige intervaller. De bliver afvist som ukritisk exit-kilde; ingen timestamps repareres ved gæt.

Den nye hazardtest bruger tidsbins, tidligere rolle/startvarighed/rest og føring/underleg, inklusive sen-kamp-interaktioner. Historiske målforløb bruges kun ved fit på afsluttede, cutoff-kendte kampe. Ved forecast genereres delte Poisson-score-scenarier fra den oprindelige pre-cutoff holdmålprognose. Den faktiske target-stilling, slutscore og target-lineup læses aldrig som forecast-features. Equal-minute goal ordering er ukendt og udelades konservativt fra pre-bin stillingen. Effekter af føring er observationelle, ikke bevist kausale.

Separat føres den empiriske survival-fordeling direkte til en opt-in minut-sampler. Dette tester masse ved 90 og tidlige exits frem for alene at ændre gennemsnittet i originalens Normal-sampler. Original sampler genskabes også efter exceptions. Benchgrenen og alle oprindelige pointregler bevares.

Den udviklingsvalgte kampstillingsmodel er `context_1.0`. Dens faktiske raw-MM-resultat er:

| Testperiode | Original MAE / RMSE | Score-context MAE / RMSE |
| --- | --- | --- |
| 2024/25 GW22–38 | 12,653130 / 22,304667 | 12,973982 / 22,118263 |
| 2025/26 GW6–38 | 10,533125 / 20,494545 | 10,810297 / 20,286332 |

RMSE forbedres, men MAE forringes i begge perioder. Kandidaten anbefales derfor ikke som en dokumenteret samlet minutforbedring. 2025-forecastet opdaterer spillerfeatures og præ-kickoff målprognoser, men hazard-fit kan kun bruge de verificerede 2024-scoreforløb. Forecast integrerer 128 score-scenarier med femminutters bins/midtpunktstilnærmelse. Det er ikke en komplet fælles mål-/exit-simulator og dokumenterer ikke taktisk årsag eller en træners kausale effekt. PM/TS for netop score-context-kandidaten er endnu **Not Available**; dens minuttest må ikke markedsføres som en forbedret fuld kæde.

## 5. Afsluttede fulde PM A/B-tests

[CI-kørsel 38565961308](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38565961308) afsluttede begge sæsoner og score-context med **success** ved commit `892fad16311ca206e19e2c2ed314bef575a578d7`. Begge PM-kørsler dækker 330 fixtures, 400 simuleringer per fixture/mode, og eksakt genskabelse af originalens frosne xP. Alle ti pointkomponenter summerer til xP. Samme modelkomponenter, scoringregler, fixtures, sandhedsdata og seeds anvendes på begge sider.

| PM-kandidat | 2024/25 GW22–38 xP-MAE / RMSE | 2025/26 GW6–38 xP-MAE / RMSE |
| --- | --- | --- |
| Låst original | 0,947794 / 1,848146 | 0,929173 / 1,880707 |
| Valgt startmodel | 0,935537 / 1,848219 | 0,926031 / 1,875504 |
| Survival-gennemsnit, original Normal-sampler | 0,960428 / 1,846284 | 0,938204 / 1,873622 |
| Start + survival-gennemsnit, original Normal | 0,946319 / 1,845841 | 0,935981 / 1,870678 |
| Survival-fordeling, oprindelig startmodel | 0,946722 / 1,845837 | 0,926274 / 1,868705 |
| **Start + fuld survival-fordeling** | **0,932798 / 1,842353** | **0,923462 / 1,866162** |
| Hard-availability-ablation | 0,947794 / 1,848146 | 0,918891 / 1,880508 |

For start + fuld survival-fordeling er det parrede xP-MAE-delta:

- 2024/25: **−0,014996**, fixture-bootstrap 95 % interval **[−0,018565;−0,011477]**, relativt ca. 1,58 %.
- 2025/26: **−0,005711**, interval **[−0,008661;−0,002788]**, relativt ca. 0,61 %.
- Den sene 2025-del GW22–38 alene: −0,003136, interval **[−0,006820;+0,000760]**; her inkluderer intervallet nul. En samlet forbedring er ikke ensbetydende med sikker gevinst i hver delperiode.

Fordelingsformen er vigtig: den valgte hazard har masse ved 90 og tidlige exits. Hvis kun dens gennemsnit sendes til den gamle Normal-sampler, genskabes den ikke. Appearance- og clean-sheet-point har minutgrænser, og GA/DC-komponenter afhænger også af eksponering; samme forventede minutlabel er derfor ikke samme pointfordeling. Dette er en dokumenteret mekanismeforskel, ikke bevis for, at enhver mere kompleks survivalmodel er bedre.

### Spillede spillere, bias og komponenter

Start + fuld fordeling forbedrer også xP-MAE og RMSE blandt spillere med faktiske minutter:

| Faktisk spillede spillere | Original xP-MAE / RMSE | Kandidat xP-MAE / RMSE |
| --- | --- | --- |
| 2024/25 GW22–38, 5.219 rækker | 1,893687 / 2,800329 | 1,873894 / 2,782990 |
| 2025/26 GW6–38, 9.969 rækker | 2,034955 / 2,924622 | 2,013330 / 2,897552 |

Samlet xP-bias ændres +0,012400→+0,007450 i 2024 og +0,019572→+0,018067 i 2025. Blandt faktisk spillede spillere er 2025-bias dog −0,351870→−0,362458: let større underprognose. Gruppen vælges efter udfald og er en diagnostik, ikke et forecast-filter.

Den simulerede minuts-MAE bliver 13,002977→12,695661 i 2024 og 10,912478→10,892507 i 2025. Dette må **ikke** forveksles med raw-MM-kompositionens MAE i afsnit 3: raw-MM-kombinationen forringer fortsat 2025-minut-MAE 10,533125→10,893571. En bedre PM via en anden fordelingsform gør ikke den analytiske minutmiddelværdi bedre på alle mål.

2025 gennemsnitlige pointkomponenter per evalueret spiller/kamp:

| Komponent | Original | Start + fuld fordeling |
| --- | ---: | ---: |
| Appearance | 0,627312 | 0,632257 |
| Mål | 0,167546 | 0,167985 |
| Assist | 0,091053 | 0,091175 |
| Clean sheet | 0,175742 | 0,169391 |
| Saves | 0,013252 | 0,014150 |
| DefCon | 0,099247 | 0,100983 |
| Negative events | −0,044452 | −0,044334 |
| Goals conceded | −0,054440 | −0,057892 |
| Strafferedning | 0,002017 | 0,002109 |
| Bonus | 0,080640 | 0,080589 |

Detaljerede positionsgrupper, xP-kalibreringsbins og bias er bevaret i `2024-25_pm_report.json` og `2025-26_pm_report.json`. Alle rapporter er hentet fra afsluttede CI-artifacts; `evidence_manifest.json` kontrollerer de oprindelige filers SHA256. Ingen tal er tilpasset Haaland eller tidligere kontrolværdier.

### Sandsynlighedskalibrering

Den valgte startmodels Brier/log-loss/ECE10:

| Periode | Original Brier / log-loss / ECE | Startkandidat |
| --- | --- | --- |
| 2024/25 GW22–38 | 0,081052 / 0,265987 / 0,013978 | 0,080122 / 0,259891 / 0,004959 |
| 2025/26 GW6–38 | 0,069635 / 0,228875 / 0,008707 | 0,069420 / 0,228468 / 0,007557 |

Brier og log-loss er proper scores. ECE er en bin-afhængig kalibreringsdiagnostik. Lighed mellem samlet gennemsnitlig p og faktisk startrate følger delvist af holdets sumkrav og beviser ikke individuel kalibrering. Partition-only-kontrollen forbedrer allerede 2025 Brier til ca. 0,069455 og log-loss til 0,228194: den lærte startmodel har ikke en ubetinget gevinst på alle mål relativt til den kontrol.

## 6. Tilgængelighedsfejl og kildekonflikter

I den arkiverede MM har 135 `SUSPENDED`-rækker p=0, men positiv q og **6,358 forventede minutter i gennemsnit**, mens alle har faktisk nul. Det er en konkret sammensætningsfejl: ikke-start er ikke det samme som dokumenteret utilgængelig. Hard-availability-ablationen sætter både p og q til nul for kendte OUT/SUSPENDED-stater, uden en ny fitted tærskel.

2025 raw-MM-MAE bliver 10,533125→10,354842 og RMSE 20,494545→20,443038. PM-MAE bliver 0,929173→0,918891, men forbedringen er stærkt koncentreret i nulminutsrækker: blandt faktisk spillede spillere forringes point-MAE 2,034955→2,038763 og RMSE 2,924622→2,926938. Den samlede tre-state log-loss forringes også en smule: 0,430807→0,430939, selv om Brier forbedres 0,227248→0,220545.

Der er **19 OUT-rækker med faktiske minutter** i sandhedsdata; samtlige rækker med identitet, GW, cutoff og nyhedskilde er gemt i `out_state_actual_minutes.csv` og genverificeret mod Core 15. oktober. Det kan skyldes forældede nyheder eller mapping-/sandhedsproblemer; de må ikke omdøbes til sikre fravær ved hjælp af efterfølgende viden. Den bedste all-row-MAE er derfor ikke automatisk den mest forsvarlige model. 2024 har ikke verificeret Team News-dækning til at validere denne medicinske ablation. Den publicerede live-PM har desuden en særskilt hard-eligibility gate: arkivfejlen er ikke bevis for, at enhver aktuel appsti har samme fejl.

For 668 cutoff-dokumenterede RETURNED_AVAILABLE-rækker undervurderer originalen minutter med ca. 15,08 i gennemsnit. Det peger på en særskilt retur-/rollehypotese; det beviser ikke, at alle skal have samme logit-boost. Ingen ikke-gemte eller uafsluttede returmodelresultater indgår som godkendt evidens i denne rapport.

## 7. Haaland, Saka og Chelsea gennem fulde aktuelle PM-komponenter

[Den ekstra fokus-kørsel](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38712316437) bestod ved `3838f836171c3c0f691e3338b24069f8395f734a`. Dette er **det frosne 12. oktober-snapshot**, ikke en ny prognose med et senere cutoff. Tre komplette klubfixtures genbygges gennem den originale GA/DC/own-goal-builder og original live-assembler med samme penalty-/BPS-historik, 2026/27-pointregler og målintensiteter. Samtlige inputkomponenter på originalens side matcher inden for 1e-10; den publicerede originale seeds xP matcher **eksakt for alle spillere i de tre fixtures**. Nye regres­sioner beskytter identiteter og minutaliaser efter adapterfejl fundet under denne test.

Der anvendes otte faste, parrede 400-draw seeds: `93000000 + fixture-offset i alle 60 frosne fixtures + repeat*100000`. Ingen seed vælges efter resultat. Den første seed genskaber den publicerede reference; gennemsnittet over otte er et andet estimat end et enkelt publiceret draw-budget eller et tidligere seed-grid.

| GW7, gennemsnit over otte seeds | Original P(start) | Kandidat P(start) | Original sim-minutter | Kandidat sim-minutter | Original xP | Kandidat xP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Haaland | 83,8230 % | 82,9398 % | 67,6697 | 70,8497 | 5,68156 | 5,66687 |
| Saka | 95,4422 % | 93,4392 % | 81,7978 | 79,1303 | 5,57219 | 5,44594 |

Kandidat er her valgt startmodel + **fuld survival-fordeling**. Raw-MM-forventningen for Haaland er fortsat 68,3018→70,7063, mens tabellen viser realiseret Monte Carlo-gennemsnit. Haalands seed-xP-standardafvigelse er 0,2911 for originalen og 0,2068 for kandidaten. Sakas er 0,2931 og 0,1436. Dette er simulationsvariation, ikke et interval for faktisk kampudfald eller bevis for prognosepræcision. En højere forventet spilletid giver ikke automatisk en højere xP i én kamp, når hele målallokeringen og pointfordelingen genberegnes.

Sakas originale xP-komponenter i dette seed-grid er appearance 1,92750, mål 2,05781, assists 0,60375, clean sheet 0,30313, DefCon 0,17750, negative events −0,20406 og bonus 0,70656 (øvrige nul). Kandidaten giver henholdsvis 1,88125, 2,05000, 0,55688, 0,30094, 0,16750, −0,19281 og 0,68219. Dermed kan forskellen spores til faktiske beregnede pointkomponenter; der er ingen manuel Saka-justering.

Chelseas totale GW7-målintensitet forbliver **1,342868819888325** på begge sider. Denne MM-test ændrer hverken holdmålmodellen eller dens låste shrinkageparametre. At tildele Chelsea flere mål her ville sammenblande to forskellige hypoteser.

Fuld per-seed-rapport og input er bevaret i `mm-current-pm-focus`-artifactet; den præcist loggede oversigt med provenance ligger i `current_pm_focus_summary.json`. Dette er ikke en managerberegning, en officiel transferanbefaling eller en kandidat-TS-backtest.

## 8. PM, TS og produktionskrav

PM-testen genbygger de oprindelige minutafhængige GA-/DefCon-/own-goal-komponenter efter hver kandidat; den udskifter ikke blot et minutlabel. Original pointmodel, koefficienter, målintensiteter og 400-draw seeds er uændrede. Originale outputs skal matche de frosne referencer eksakt. Pointkomponenterne skal summere til xP. Simulationsgrenene forbruger RNG forskelligt, så fixture-bootstrap dækker ikke al Monte Carlo-usikkerhed.

Benchmark **2.125 point, 44 transfers og 28 hitpoint** bevares. Det eksisterende historiske forecastarkiv mangler de komplette fremtidige seks-GW-celler; der konstrueres ingen falske celler og intet kandidat-TS-total. En fuld MM→PM→TS-promovering er blokeret af dette samt uafhængig kilde-/testvalidering.

Beslutning: **ingen udskiftning af produktionen**. Den mest lovende fulde PM-forsøgskandidat er den udviklingsvalgte logistiske startmodel sammen med den empiriske survival-fordeling, fordi både samlet og played-player xP-MAE/RMSE forbedres i begge sæsoner. Den er en kandidat til ny, uafhængig validering, ikke en færdiggodkendt minutmodel. Fordelingsforsøget blev valgt som en opfølgende hypotese efter at gennemsnitsforsøget slog fejl; det er en adaptiv forskningsproces, ikke et uberørt confirmatory holdout. MAE, RMSE, proper start/substate scores, kalibrering, spillergrupper og PM skal vurderes samlet. En glattere eller mere plausibel Haaland-prognose er ikke et acceptkriterium i sig selv.

Maskinlæsbare rapporter og CI-artifacts indeholder alle ablationer, inputs/checksums, feature/fit cutoffs og gruppeanalyser. Ingen manager-state eller købspriser er publiceret.

Metodereferencer: [scikit-learn logistic regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression), [ukendte kategorier](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html), [right-censored survival](https://www.statsmodels.org/stable/duration.html). Hazardtestens konkrete matematik og begrænsninger fremgår ovenfor og i koden; referencerne er ikke ekstern validering af FPL-resultaterne.


## 9. Validering og resterende godkendelseskrav

- 15. oktober: **510 lokale Python-regressioner bestod** efter de sidste adapterrettelser, inklusive atomisk CSV-lagring, konsistente aktuelle minutaliaser/identiteter og nested-dataclass-komponentkontrol med eksplicit tolerance. Classic Manager, spillerprofil-snapshot og forecast/deadline-JavaScript-checks bestod.
- [Fuld audit ved den beregnede modelkode](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38565961258) og [hele MM/PM/context-kørslen](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38565961308) bestod. Rapporter er gendannet med original checksum efter forbindelsesbruddet; de dyre tests er ikke erstattet med genfortalte kontroltal.
- Forsøgenes kandidat-/PM-CSV- og JSONL-gzip-checkpoints skrives til midlertidig fil, trailer-valideres, fsync'es og omdøbes atomisk; ved fejlet serialisering bevares sidste komplette fil. Dette ændrer ikke modelmatematikken.
- Kræver stadig: uafhængig ny testperiode, verificerede historiske publiceringstider/rosters/medicinske labels, komplet workload, validering af 2025 exit-/scorekilder samt fulde historiske fremtidige seks-GW-celler.
- De separate own-goal/exact-XI-rettelser og MM-fordelingskandidaten er endnu ikke samlet i én accepteret simulator. Eksakte marginalsummer alene certificerer hverken realiserede 11 startere eller kontinuerlig 990-minutters dækning.
- Den låste original, TS-benchmark og alle produktionsstrategier er bevaret; intet deploy, ingen officielle transfers og ingen live-certificering. `locked_model_active=false`.
