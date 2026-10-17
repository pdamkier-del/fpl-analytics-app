# Mål- og assistmodel: audit og isolerede forsøg

PR #3, model-audit-optimization-20261012. Produktionsbaseline og koefficienter ændres ikke; locked_model_active=false. Ingen manager-state anvendes. De fire historiske hovedkørsler er afsluttet og bestået. Konklusion: ingen kandidat erstatter den låste PM; assistconversion er en afgrænset forskningskandidat til en ny uafhængig periode.

## Den faktiske låste kodevej

Den rolling-kæde, som producerer benchmark-inputs, er `run_rolling_vfinal_gw6_38.py` → `vfinal_replay_components.build_fixture_components` → `run_vfinal_integrated.make_vfinal_input` → `joint_simulator.simulate_many`. Det er ikke tilstrækkeligt at læse en ældre fit-JSON: de arkiverede primitive team-goal-parametre med xG/mål-blanding er ikke funktionen, der kaldes i denne rolling-kæde.

`fit_team_latent` fitter log(lambda)=intercept+home+attack(team)+defence(opponent) med sum-zero holdparametre, ridge0.25 og16GW-halveringstid. Målet i quasi-Poisson-likelihood er **historisk xG**, ikke faktiske mål. Fit og lambda-klip [.05,5] er uændrede. Dette forklarer, hvorfor Chelsea15mål/8.51xG ikke automatisk giver en1.76-multiplikator i GW7. GW-baseret decay skal adskilles fra kandidatens kalenderdags-decay.

Individuel xG/xA-rate shrinkes til aktuel sæsons positionsprior med låste pseudo-minutter340.37044/365.22362 og halv­eringstider14.30170/28.106997 historiske rækker. Soft-role-priorer, recent-performance og taktiske akser korrigerer raterne. Forventet eksponering indgår i normaliserede spillerandele: w_i=rate_i*E[M_i]/90*exp(beta'x_i), share_i=w_i/sum(w). `goal_mu=lambda*share_goal`, `assist_mu=lambda*rho*share_assist`. Adapteren omregner disse til on-pitch-vægte; Monte Carlo normaliserer igen blandt dem, som er aktive ved målet. Et præ-match mu-label er derfor ikke uden videre simulatorens marginale målmiddel.

Rho er den hidtidige sæsons FPL-assists/spillerkrediterede-mål-ratio begrænset til[.5,1]. Scoreren trækkes først; assistcoin og assistgiver trækkes kun ved almindelige mål, blandt aktive medspillere uden scoreren. Den eksisterende model er allerede en fælles mål→assist-begivenhedsmodel. Den indeholder ingen lærte Palmer→JoãoPedro-forbindelser. Eksklusion af scoreren betyder desuden, at tilsigtede normaliserede assistvægte ikke nødvendigvis er de marginale assistandele.

Straffespark har et separat Poisson-occurrence-/taker-/conversion-lag. Forventet straffemålsmasse trækkes fra ordinary-Poisson-budgettet. Men xG-vægtene inkluderer stadig straffexG: det er en mulig allokeringsforvridning, selv om totalens budget ikke blot fordobles. Penalty assists sættes til nul i den låste simulator. Own-goal/shared-CS-fejlen har en separat opt-in rettelse fra tidligere PR-arbejde; den er endnu ikke en produktionsændring.

Officielle FPL-assists kan komme fra rebounds, fremtvungne selvmål og vundne straffespark/frispark; den officielle2025/26-definition ændrede også kriterierne for defensive touches. Den globale all-FPL-assist-ratio, som kun anvendes på ordinary-mål, er derfor ikke en fuld model af FPL-reglerne. Vi udleder ikke manglende eventlabels fra totaler.

Mål/assists går gennem originale positionspoint og BPS-komponenter i hvert simuleringstræk. BPS-background er et separat fit af residuale actions og skaleres med minutter; nye målpoint lægges ikke manuelt oven i en gammel bonusprognose. `expected_bonus` skal genberegnes gennem hele kampen, inklusive modstanderne. Pointkomponenterne skal summere eksakt til xP.

## Kilder og afgrænsning

Core har109k+spiller/kamp-rækker over2022/23–2025/26 med xG/xA, men **ingen native npxG, shots, shots-on-target eller big-chances-created** i disse felter. Tidlige2022/23-runder førGW16 har semantiske xG/xA-placeholders0; de udelades helt fra conversion-history. Ingen manglende værdier omdannes til nul.

Klub-ID er sæsonafhængigt: ColePalmers Chelsea-team_id er6 i2024/25 og7 i2025/26. Hierarkiske holdeffekter bruger derfor `(season,team_id)`, ikke numerisk klub-ID på tværs af sæsoner. Spillere anvender eksisterende canonical UUID.

380 verificerede2024-PL-shotmaps indeholder9.883skud og ingen creator-ID ved missede/redde skud. Mål-events har undertiden assistPlayerId, men kun forbindelser ved succesfulde afslutninger identificerer ikke pass→shot→goal-sandsynligheder for alle chancer. En avanceret observeret pair-skill-model kan ikke certificeres herfra. Set-piece-state findes i Core, men er ikke det samme som verificerede chance- og receiver-links eller npxG. Alternative leverandørers penalty-xG trækkes ikke fra FPL-xG uden ækvivalensbevis.

Historisk tilgængelighed anvender fortsat de dokumenterede kickoff+3/4h-proxyer fra tidligere adaptere. Reelle publiceringstider mangler; strenge fit-masker kan ikke i sig selv ophæve denne kildebegrænsning. Sæsonerne er tidligere brugt til baselineudvikling og er ikke uberørte whole-model-holdouts.

## Kandidater og protokol

1. **Simple xG/xA:** tidligere current-season xG/xA og positionsprior med de oprindelige primitive shrinkagekonstanter; ingen performance/rolle-korrektion. Et comparator-ablation, ikke ny produktion.
2. **Gamma-Poisson conversion:** theta~Gamma(tau,tau), Y|X,theta~Pois(theta*X), E(theta|history)=(Y+tau)/(X+tau). Det er en effektiv kalibreringskorrektion på all-xG, ikke identificeret NPG-finishing.8mål/5xG vedtau50 bliver1.0545, ikke1.6. Med kalenderdecay er de vægtede sufficient-statistics en power-likelihood-tilnærmelse; de er ikke ekstra faktiske heltalsmål eller et bevis for stationær spiller-evne.
3. **Assist conversion:** samme struktur med FPL-assists/xA. Den identificerer ikke ren kreativitet; modtageres finishing og FPL-regler er blandet i udfaldet.
4. **Hierarkisk EB:** spillerens Gamma-prior-middel shrinkes mod aktuel sæsons hold, som shrinkes mod league-conversion. Begge events testes. Der opfindes ikke en separat ligaforskel fra data om kun én liga.
5. **Total-finishing:** den relative spillerkorrektion normaliseres én gang; optionalt korrigeres ordinary-team-lambda med den forventede eksponeringsvægtede finishingfaktor. Straffekonvertering og straffemasse fastholdes. En uniform finishingfaktor2 flytter ordinary-total2x, ikke4x. Fixed-total- og changed-total-arme holdes adskilt.
6. **Joint marginal assist:** en maksimum-entropy jointfordeling med scorermarginaler og assistmarginaler, structural-zero på selvassist. IPF løser marginalerne, ingen specifik pair-evne estimeres. Infeasible aktive margener afvises og falder tilbage til oprindelig lovlig vægtning; antallet rapporteres. Den oprindelige assistcoin og målprocessen ændres ikke.

Kalenderhalveringstid90d/365d/hele tilgængelige historie og tau5/20/80 screenes. Hierarkiets team-priorstyrke20/80/320 vælges også på udviklingsdata; dette er sekventiel empirical-Bayes shrinkage, ikke en fuldt estimeret Bayesian posterior-variance-model. Hyperparametre vælges på2024/25GW6–21 med en pre-kickoff analytisk event-proxy; **target-kampens realiserede xG/minutter er aldrig forecast-input**. Proxymetoden og fuld event-time-PM holdes adskilt. Valget skrives før senere2025-targetforecasts læses. Test:2024GW22–38 og2025GW6–38.

Først måles alle PM-arme med låst MM. Derefter sammenlignes uændret PM og to prædefinerede PM-kombinationer under samme eksperimentelle start+survival-MM. Ingen forbedring tilskrives PM ved at sammenligne en fælles MM+PM-ændring alene med gammel baseline.

Fuld PM er400draws/fixture med originale seeds og exact-reference-guard. Simulatoren instrumenteres kun til eventtællinger; en regression beviser draw-for-draw identitet. Scoringslag og BPS-koefficienter ændres ikke. Binære goal/assist-sandsynligheder har eksplicit MonteCarlo-Jeffreys-smoothing; Poisson count-NLL er en særskilt diagnostic-approksimation, ikke den fulde MonteCarlo-countdistribution. Fixture-bootstrap dækker sampling af kampe, ikke al simulationsstøj. Der rapporteres MAE/RMSE/bias, eventproper-scores, kalibrering, bonus, spillede spillere og positioner.

## Status og produktionskrav

Kode, regressioner og fulde numeriske replays er gennemført isoleret. Ingen kandidat er valgt til produktion. Historiske fremtidige seks-GW-celler mangler stadig, så et nyt korrekt kandidat-TS-total mod2125 kan ikke opfindes. Den originale baseline bevares.

Primære metodereferencer: [StatsBomb: Quantifying finishing skill](https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/), [Biases in Expected Goals Models Confound Finishing Ability](https://arxiv.org/abs/2401.09940), [FPL scoring/assist rules](https://www.premierleague.com/en/news/2174909/), [2025/26 assist changes](https://www.premierleague.com/en/news/4362187/whats-new-in-202526-fantasy-changes-to-assists-rules). De begrunder forsøg/afgrænsning, ikke en påstået forbedring i vores model.


## Rå npxG-kildekontrol og første afsluttede screening

Raw-shotmap-auditten finder faktisk native NP-chancer i2024:380PL-kampe,83straffeskud,69straffemål og1013øvrige krediterede mål. Alle5323spiller/kamp-kombinationer med skud mapper tilCore; ingen unmapped/missing-xG-skud. Men183rækker har >0.05xG-afvigelse mellem kilderne, maksimum0.54194, og én goal-credit-uoverensstemmelse.4778rækker stemmer inden for0.01. Derfor må FotMob-straffe-xG ikke blot trækkes fra Core/FPL-xG. Kilderne er tilstrækkelige til et separat provider-internt2024-npxG-forsøg, ikke til at påstå en verificeret fler­sæsons npxG-reparation.804mål har provider-assistlinks, stadig ingen skaber ved de øvrige skud.

Den udvidede udviklingsscreening valgte finishing med hele den tilgængelige historie/tau20, assistconversion365d/tau5 og hierarki365d/spiller-tau5/hold-tau320. Alle valg er fra2024GW6–21; testdata blev ikke brugt til valget.

Analytisk pre-match event-proxy, ikke fuld MonteCarlo-PM:

| Testperiode og event | Original Poisson NLL | Valgt playerconversion | Hierarki |
| --- | ---: | ---: | ---: |
|2024GW22–38, mål|0.1168332|0.1169068|0.1170441|
|2025GW6–38, mål|0.1089216|0.1089557|0.1090834|
|2024GW22–38, FPL-assists|0.1174993|0.1170642|0.1170301|
|2025GW6–38, FPL-assists|0.1134746|0.1134495|0.1132646|

Målkorrektionerne generaliserer således ikke bedre på denne log-score i de senere perioder. Assistresultatet er mere positivt, men forskellene er små. Vi konkluderer ikke forbedret xP fra denne proxy. De afsluttede fulde PM-replays og MM-interaktioner nedenfor bruger de oprindelige pointkoefficienter og egne baselinekontroller.


### Goal-credit-forskellen er forklaret af officiel efterfølgende kreditering

Rækken er YoaneWissa, Brentford–Ipswich26/10/2024. PremierLeague annoncerede29/10, at HarryClarkes oprindelige selvmål blev omkrediteret til Wissa, men at GW9's FPL-point **ikke** blev ændret efter rundens afslutning27/10. Dermed kan providerens to fodboldmål og FPL's ene mål være korrekte under hver deres definition og tidspunkt. En senere fysisk goal-credit må ikke indlæses i en historisk forecast26/10 med kickoff+4h-stempel. Hverken Core's FPL-goals, assists eller points er overskrevet. [Officiel redegørelse](https://www.premierleague.com/news/4159875).

Dette er en konkret evidens for både outcome-definition og publiceringskravet, ikke en begrundelse for at ændre den låste reference. De øvrige xG-afvigelser er stadig forskellige kildemålinger; de sidestilles ikke automatisk med denne forklaring.


### Eksisterende kreativitetsfeatures og yderligere databegrænsninger

Den originale allocator bruger allerede `perf_last_chances`, driblinger og afleveringspræcision på assistsiden samt xGI/SOT/goal-assist-signaler på målsiden. Disse stammer fra raw-`playermatchstats`, ikke fra de tomme Core-shotfelter. Nye rene A/xA-korrektioner skal derfor testes ud over eksisterende kreativitetssignaler, ikke beskrives som om den oprindelige model ignorerer dem.

Den eksisterende `build_perf_ledger` konverterer manglende numeriske detaljer til nul. I de38arkiverede2025-filer er der13.881spillede rækker, hvor11manglerxG,20manglerxA og21manglerafleveringspræcision før denne konvertering; SOT/chances/driblinger har ingen sådanne nulls i denne kontrol. Dette er en bekræftet inherited baseline-datakvalitetsrisiko, ikke en begrundelse for at retune/ændre den låste model under A/B. Den nye conversion-history bruger de eksplicit validerede Core-felter og udelader tidlige2022-placeholders. Parserens eksakte zero-fill-effekt på PM er endnu ikke isoleret i en særskilt ablation.

Core's set-piece-snapshots dækker2023/24 og et2026/27-snapshot, men ingen2024/25- eller2025/26-rækker. Ingen har `effective_at`; nogle har observerede rangeringer. Det er ikke tilstrækkeligt til at opfinde cutoff-korrekte dødboldsordener for testperioderne. Effekten kan delvist være i historisk xA/softrole og originalt penalty-state, men der er ikke implementeret en ny uverificeret corner/free-kick-effekt.


### Aktuelt snapshot er fortsat diagnostisk, inklusive provisionelle data

Den checksum-verificerede aktive fixtures-kilde i manifestet12/10viser Chelseas GW6 som `finished_provisional=true`, men `finished=false`, med5–1. De fem endeligt markerede kampe giver10mål; inklusive den provisionelle sjette kamp bliver det15, som spillerhistorikken også summerer til. Vi udelader ikke GW6 fra den diagnostiske shadow og påstår heller ikke, at kildens endelige status er bestået. `current_source_status.json` gemmer dette med kilde/checksum. Gamle filer i work-mappen må ikke vælges som aktuelle kilder uden manifestet. Ingen af disse snapshotanalyser er et nyt15/10-forecast.

De to af60historiske hold/sæsoner med mindst1.5G/xG i deres første seks kampe falder samlet fra19/11.33=1.677 til16/12.67=1.263 i de næste seks. Det er en meget lille, efterfølgende deskriptiv gruppe, ikke evidens for en universel fast regressionsfaktor. Realiseret senere xG bruges kun til denne beskrivelse og aldrig til forecasts eller hyperparametervalg.


## Afsluttede historiske PM-replays

Primær beregningskode: `08ff78a066b341d56e07087d9c4536a6a05fc1c2`, workflow [38717540912](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38717540912), alle seks jobs bestået. Begge sæsoner har 330 kampe fra GW6–38, 400 simuleringer pr. kamp og samme oprindelige seeds. Den låste references xP reproduceres eksakt i de to låst-MM-arme. De to eksperimentelle MM-arme har deres egen uændrede-PM-reference; rapportens `original_exact=false` dér betyder, at de ikke påstår lighed med den gamle MM-reference, ikke at en aktiveret referencekontrol fejlede. 2024/25 GW6–21 bruges til udvikling; tabellens 2024/25-resultater er udelukkende GW22–38 med 13.105 spiller/kamp-rækker. 2025/26 GW6–38 har 26.159 rækker. Rækker inkluderer også registrerede reserver, som ikke spillede. Spillede spillere og grupper rapporteres separat for at gøre denne vægtning synlig.

De fem fulde rapporter er genskabt fra kørslens artifacts uden numerisk reserialisering og kontrolleret mod deres oprindelige SHA-256; se `evidence_manifest.json`. Efterbehandling af grupper og holdkalibrering er gennemført i [38720669600](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720669600). Den ændrer ingen model, hyperparametre, predictions eller seeds.

### Samlede FPL-point: lavere er bedre

| Kandidat | 2024/25 xP-MAE | 2024/25 RMSE | 2025/26 xP-MAE | 2025/26 RMSE |
| --- | --- | --- | --- | --- |
| Låst original | 0.9477938 | 1.8481456 | 0.9291727 | 1.8807071 |
| Ren xG/xA-ablation | 0.9486965 | 1.8475191 | 0.9292097 | 1.8806551 |
| Individuel finishing | 0.9473298 | 1.8478807 | 0.9289755 | 1.8802402 |
| Assistconversion | 0.9476272 | 1.8477724 | 0.9285983 | 1.8795306 |
| Finishing + assist | 0.9471705 | 1.8475243 | 0.9284534 | 1.8792033 |
| Hierarkisk EB | 0.9469332 | 1.8470029 | 0.9285890 | 1.8800176 |
| Hierarki + joint | 0.9469365 | 1.8481713 | 0.9287732 | 1.8802049 |
| Ændret holdintensitet | 0.9510572 | 1.8525463 | 0.9289046 | 1.8792862 |

Paired ændring i point-MAE mod samme sæsons låste original, med 95 % fixture-bootstrap-interval. Negativt er bedre. Intervallerne er ikke korrigeret for de mange kandidater og metrics og er ikke et produktionsbevis i sig selv.

| Kandidat | 2024/25 ΔMAE [95 % CI] | 2025/26 ΔMAE [95 % CI] |
| --- | --- | --- |
| Ren xG/xA-ablation | +0.0009027 [-0.0002528; +0.0021220] | +0.0000371 [-0.0009089; +0.0009460] |
| Individuel finishing | -0.0004639 [-0.0010835; +0.0001543] | -0.0001972 [-0.0006748; +0.0002599] |
| Assistconversion | -0.0001665 [-0.0008321; +0.0004844] | -0.0005744 [-0.0009725; -0.0001684] |
| Finishing + assist | -0.0006232 [-0.0015578; +0.0002973] | -0.0007193 [-0.0013236; -0.0001283] |
| Hierarkisk EB | -0.0008605 [-0.0020703; +0.0003095] | -0.0005836 [-0.0013282; +0.0001603] |
| Hierarki + joint | -0.0008573 [-0.0023443; +0.0006518] | -0.0003995 [-0.0012731; +0.0004426] |
| Ændret holdintensitet | +0.0032634 [+0.0007330; +0.0058521] | -0.0002681 [-0.0019948; +0.0013462] |


Assistconversion forbedrer 2025/26 point-MAE med cirka 0,062 %, kombinationen med cirka 0,077 %. Det er små ændringer. I 2024/25 indeholder begge pointintervaller nul. Hierarkiets større kompleksitet giver ikke en sikker tværsæsons pointforbedring. Joint-varianten forbedrer assist-log-loss, men har lidt dårligere 2024/25 point-RMSE end originalen. Ændret holdintensitet forringer 2024/25 point-MAE med et interval helt over nul og afvises i denne form.

### Mål og assists evalueres særskilt

Tabellen viser binær log-loss for mindst ét mål henholdsvis mindst én officiel FPL-assist. Sandsynlighederne kommer fra de fulde simulationer med den dokumenterede smoothing. Disse scores må ikke forveksles med screeningens analytiske Poisson-proxy eller rapporternes diagnostiske count-Poisson-NLL.

| Kandidat | 2024 mål LL | 2024 assist LL | 2025 mål LL | 2025 assist LL |
| --- | --- | --- | --- | --- |
| Låst original | 0.1081195 | 0.1107051 | 0.0997605 | 0.1084564 |
| Ren xG/xA-ablation | 0.1084644 | 0.1108814 | 0.0996936 | 0.1085955 |
| Individuel finishing | 0.1081260 | 0.1106884 | 0.0997346 | 0.1084574 |
| Assistconversion | 0.1081195 | 0.1097283 | 0.0997605 | 0.1081186 |
| Finishing + assist | 0.1081260 | 0.1098054 | 0.0997346 | 0.1080674 |
| Hierarkisk EB | 0.1081351 | 0.1101504 | 0.0996647 | 0.1083008 |
| Hierarki + joint | 0.1081351 | 0.1096908 | 0.0996647 | 0.1077657 |
| Ændret holdintensitet | 0.1083148 | 0.1106929 | 0.0996784 | 0.1084765 |


| Kandidat | 2024 Δassist-LL [95 % CI] | 2025 Δassist-LL [95 % CI] |
| --- | --- | --- |
| Assistconversion | -0.0009768 [-0.0017826; -0.0001988] | -0.0003379 [-0.0007854; +0.0001366] |
| Finishing + assist | -0.0008997 [-0.0017278; -0.0000560] | -0.0003891 [-0.0008729; +0.0001045] |
| Hierarki + joint | -0.0010144 [-0.0019192; -0.0001414] | -0.0006907 [-0.0012654; -0.0001291] |


Finishing giver ikke en ensartet forbedring af mål-log-loss: lidt dårligere i 2024, lidt bedre i 2025, med usikkerhed omkring ændringen. Assistconversion har den mest konsistente enkle forbedring af assist-log-loss. A/xA identificerer stadig ikke selvstændig kreativ evne; det er en kalibrering af FPL-udfald under den eksisterende målproces. Rapporter indeholder også mål/assist-MAE, RMSE, bias, Brier, count-NLL og kalibreringsbins for hver kandidat.

Kalibreringen viser en mere konkret restsvaghed end de små samlede MAE-forskelle: i 2024-originalens målbin med 0,4–0,8 forventede mål er middelprognosen cirka 0,494, mens det observerede antal mål pr. række er cirka 0,341. Det er count-kalibrering, ikke en sammenligning mellem count og binær sandsynlighed. Kategorien er lille (126 rækker) og valgt diagnostisk; den giver ikke grundlag for manuel nedjustering af enkelte stjerner. Assistkalibreringen er også fortsat for høj i flere mellem/høje bins. Ingen af de testede korrektioner løser entydigt alle sådanne fejl.

### Bonus, BPS og spillede spillere

| Sæson | Kandidat | Spillede: point-MAE | Bonus-MAE | BPS-MAE |
| --- | --- | --- | --- | --- |
| 2024-25 | Låst original | 1.8936870 | 0.1416253 | 3.9342161 |
| 2024-25 | Assistconversion | 1.8944716 | 0.1415076 | 3.9351856 |
| 2024-25 | Finishing + assist | 1.8938642 | 0.1413010 | 3.9342898 |
| 2024-25 | Hierarkisk EB | 1.8928401 | 0.1412140 | 3.9345076 |
| 2024-25 | Hierarki + joint | 1.8934121 | 0.1410689 | 3.9373897 |
| 2025-26 | Låst original | 2.0349546 | 0.1384369 | 3.6711323 |
| 2025-26 | Assistconversion | 2.0340237 | 0.1383193 | 3.6703934 |
| 2025-26 | Finishing + assist | 2.0340556 | 0.1383316 | 3.6705262 |
| 2025-26 | Hierarkisk EB | 2.0346371 | 0.1383415 | 3.6720840 |
| 2025-26 | Hierarki + joint | 2.0355575 | 0.1382477 | 3.6726966 |

Bonus er genberegnet i den oprindelige fælles kampsimulator. Assistconversion forbedrer ikke alle metrics: 2024 point-MAE blandt spillede spillere og BPS-MAE forringes svagt. Joint-modellens BPS-MAE forringes i begge sæsoner. En bedre assist-log-loss er derfor ikke lig med en generelt bedre FPL-model.

### Holdmål og ændret intensitet

Samme senere perioder som i pointtabellen; 2024 GW22–38 og 2025 GW6–38.

| Sæson | Original MAE | Kandidat MAE | ΔMAE [95 % CI] | Original deviance | Kandidat deviance |
| --- | --- | --- | --- | --- | --- |
| 2024-25 | 0.9155566 | 0.9179234 | +0.0023668 [-0.0025782; +0.0073576] | 1.1020264 | 1.1014937 |
| 2025-26 | 0.8906496 | 0.8873940 | -0.0032555 [-0.0067197; +0.0004688] | 1.0521224 | 1.0491484 |

Begge sæsoners intervaller for holdmåls-MAE og deviance inkluderer nul. Den lille forbedring i 2025 kan ikke alene begrunde at ændre Chelseas eller andre holds totaler. De oprindelige fulde rapporters `team_goal_metrics` bruger alle GW6–38, også 2024-udviklingsperioden; til den senere 2024-periode anvendes derfor ovenstående eksplicitte efterbehandling.

### Roller og holdtyper uden fremtidslabels

Faste startere er spillere med seks seneste registrerede kampe som starter før cutoff; reserver har mindst tre kampe og startandel højst 20 %. Resten er rotation/kort historik. Høj forudgående produktion kræver mindst 0,5 historiske G+A/90 blandt de faste. Det er ikke en target-outcome-definition af stjerner.

| Sæson | Gruppe | Rækker | Original MAE | Assist MAE | Kombineret MAE | Hierarki MAE |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | regular | 1665 | 2.3415375 | 2.3424339 | 2.3415210 | 2.3389790 |
| 2024-25 | reserve | 7994 | 0.3515096 | 0.3510405 | 0.3505695 | 0.3509923 |
| 2024-25 | rotation_or_short_history | 3446 | 1.6576349 | 1.6576567 | 1.6574536 | 1.6567985 |
| 2025-26 | regular | 3148 | 2.3474754 | 2.3470862 | 2.3481051 | 2.3489462 |
| 2025-26 | reserve | 16293 | 0.3087119 | 0.3084926 | 0.3081286 | 0.3080047 |
| 2025-26 | rotation_or_short_history | 6718 | 1.7693558 | 1.7678334 | 1.7676745 | 1.7681092 |

I 2025 forringes kombinationen blandt faste startere trods forbedring samlet; assist-only har en lille forbedring i denne gruppe. Efterbehandlingsrapporten har også fulde separate mål-/assist-/bonus-/BPS-metrics for hold med forudgående G/xG over eller under 1 og for høj forudgående spillerproduktion. Holdtypen bruger krediterede spillermål, ikke verificerede selvmålsinklusive holdmål. Grupperne bruges ikke til at vælge nye parametre efter testen.

## Samspillet med den eksperimentelle MM

Samme tidligere valgte startmodel og empiriske survival-fordeling anvendes i alle tre arme. Tabellen isolerer derfor den ekstra PM-ændring.

| Sæson | PM under samme nye MM | xP-MAE | RMSE | Spillede MAE | ΔMAE [95 % CI] |
| --- | --- | --- | --- | --- | --- |
| 2024-25 | Låst original | 0.9327982 | 1.8423531 | 1.8738939 | +0.0000000 [+0.0000000; +0.0000000] |
| 2024-25 | Finishing + assist | 0.9323911 | 1.8422271 | 1.8742666 | -0.0004071 [-0.0014025; +0.0006184] |
| 2024-25 | Hierarkisk EB | 0.9325660 | 1.8422577 | 1.8742350 | -0.0002322 [-0.0013527; +0.0009579] |
| 2025-26 | Låst original | 0.9234618 | 1.8661622 | 2.0133301 | +0.0000000 [+0.0000000; +0.0000000] |
| 2025-26 | Finishing + assist | 0.9232933 | 1.8650408 | 2.0139377 | -0.0001685 [-0.0007296; +0.0004020] |
| 2025-26 | Hierarkisk EB | 0.9233943 | 1.8655801 | 2.0139334 | -0.0000675 [-0.0007922; +0.0006515] |


Den ekstra PM-forbedring er ikke sikker i nogen af de to sæsoner og forringer svagt point-MAE blandt spillede spillere. I 2025 GW22–38 bliver samlet MAE desuden 0,8893524 → 0,8894195 for kombinationen. Det er et negativt ablationsresultat og ikke grundlag for at promovere en samlet MM+PM-pakke. MM-forskningens selvstændige resultater bevares i tidligere PR-dokumentation.

## Chelsea, Haaland og Saka: samme frosne snapshot

Cutoff er **12. oktober 2026 kl. 10:45:27 UTC**, ikke dagens live-forecast. Der er otte parrede seedgentagelser à 400 træk på de tre relevante kampe. Første originale seed reproducerer det arkiverede snapshot eksakt for alle spillere. Tabellen viser gennemsnit over de otte seeds; derfor kan tallene afvige fra appens ene seed. PM-korrektioner ændrer ikke MM-inputs. Seedspredning er Monte Carlo-støj og ikke et historisk konfidensinterval for bedre præcision.

| PM-kandidat | Haaland xP | Saka xP | João Pedro xP |
| --- | --- | --- | --- |
| Låst original | 5.68156 | 5.57219 | 3.35500 |
| Individuel finishing | 5.58312 | 5.58406 | 3.30438 |
| Assistconversion | 5.72344 | 5.55063 | 3.41406 |
| Finishing + assist | 5.63031 | 5.56531 | 3.36906 |
| Hierarkisk EB | 5.62750 | 5.46656 | 3.39594 |
| Hierarki + joint | 5.73594 | 5.59938 | 3.47406 |
| Ændret holdintensitet | 5.58375 | 5.58344 | 3.42000 |


Haalands gennemsnitlige simulerede minutter er 67,6697 under låst MM, både før og efter PM-korrektionen. Under den separat valgte eksperimentelle MM bliver de 70,8497; original PM giver dér 5,66688 xP og kombineret PM 5,64125. Højere minutter garanterer ikke en tilsvarende xP-stigning, fordi den aktive eventfordeling og seedforløb også ændres. Denne PM-undersøgelse løser ikke minutmodellens start-/udskiftningskalibrering.

Haalands historiske 100 mål/99,2843 xG bliver med tau 20 til faktor 1,0060, Sakas 42/40,3405 til 1,0275. Det er ikke store afslutningseffekter. Individuelle mål kan falde trods egen faktor over 1, når de øvrige spilleres vægte stiger mere og holdtotalen er fastholdt. Haalands kombinerede ΔxP er −0,05125 med paired seed-SD 0,05999; Sakas er −0,006875 med SD 0,03479. Der er ingen dokumentation for, at Sakas prognose blot skal tvinges lavere.

### Sakas og Haalands faktiske pointkomponenter

| Komponent | Haaland original | Haaland kombineret | Saka original | Saka kombineret | Saka hierarki |
| --- | --- | --- | --- | --- | --- |
| Spilletidspoint | 1.730938 | 1.730938 | 1.927500 | 1.927500 | 1.927500 |
| Målpoint | 2.893750 | 2.818750 | 2.057812 | 2.065625 | 2.029687 |
| Assistpoint | 0.226875 | 0.268125 | 0.603750 | 0.594375 | 0.552188 |
| Clean sheet | 0.000000 | 0.000000 | 0.303125 | 0.303125 | 0.303125 |
| Redninger | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Defensive contributions | 0.006250 | 0.006250 | 0.177500 | 0.177500 | 0.177500 |
| Negative hændelser | -0.143125 | -0.143125 | -0.204062 | -0.204062 | -0.204062 |
| Indkasserede mål | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Strafferedninger | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Bonus | 0.966875 | 0.949375 | 0.706562 | 0.701250 | 0.680625 |


Alle ti komponenter summerer til den respektive xP med numerisk tolerancetjek. Sakas oprindelige målmiddel er 0,41156 og assistmiddel 0,20125, kombineret 0,41313 og 0,19813. Den største pointkomponent er målpoint, efterfulgt af appearance. Haalands målmiddel 0,72344 → 0,70469, assists 0,07563 → 0,08938. Fulde seeds og komponenter ligger i `current_conversion_report.json`.

### Chelsea: koncentration og shrinkage

15 krediterede mål fra 8,51 xG er en stor korttidsoverpræstation, men 6,19 af de 6,49 overskydende mål kommer fra tre spillerposter: João Pedro +2,23, Rogers +2,10 og Henderson +1,86. Navne/ID'er er kontrolleret mod dette snapshots checksum-verificerede bootstrap; usædvanlige rosterforhold ændres ikke ud fra hukommelse. Palmer bidrager +0,69. Det er ikke evidens for en ny fast holdfaktor.

Original holdintensitet er 1,34286882; den eksperimentelle ændrede-intensitetsarm giver 1,39585108, cirka +3,95 %. Øvrige PM-arme fastholder 1,34286882. Kandidaten multiplicerer ikke med 15/8,51; shrinkage og en eksponeringsvægtet spillerfaktor bruges én gang på ordinary-budgettet, mens straffemassen bevares. Kandidatens dårligere 2024 pointresultater gør, at denne Chelsea-stigning **ikke** anbefales til produktion. GW6 er fortsat provisionelt markeret i den frosne kilde, som beskrevet ovenfor.

## Beslutning og resterende blokeringer

**Bevar den originale PM/vFinal.** Ingen kandidat dokumenterer tilstrækkeligt robust forbedring af mål, FPL-point og MM-samspil til en erstatning. Assistconversion med 365 dages halveringstid/tau 5 er den enkleste lovende forskningskandidat; den bør først evalueres uændret på en ny uafhængig periode med verificerede publiceringstider. Det er en anbefaling til yderligere evidens, ikke en produktionsgodkendelse. Joint-varianten er matematisk lovlig, men mere kompleks uden en sikker samlet pointgevinst; 1.134 af 342.524 aktive joint-forsøg i 2024 og 613 af 317.587 i 2025 bruger eksplicit lovlig original-fallback, når ønskede margener ikke kan realiseres uden selvassist.

Før en produktionsbeslutning mangler:

- Verificerede historiske publiceringstider frem for kickoff-proxyer, samt BPS/MM-kildekravene fra tidligere audit. Disse genopfindes ikke her.
- Ensartet flerårs npxG og afstemte fodboldmål kontra låste officielle FPL-mål, inklusive efterfølgende appeals.
- Data om samtlige skaber→afslutter-chancer og cutoff-sikre dødboldsordener, hvis en mere detaljeret fælles model skal estimeres.
- En særskilt zero-fill-ablation; den gamle parser ændres ikke midt i denne referencesammenligning.
- Uafhængig ny testperiode og simulationspræcision, som er tilstrækkelig til de meget små observerede PM-forskelle. Ens seeds reducerer støj, men fjerner den ikke; ændret hold-lambda ændrer også RNG-forbruget.
- Historiske seks-GW-inputs til et ærligt MM→PM→TS-replay. Kun 33 af 183 kontrollerede origin-target-celler er dækket; 150 mangler. Det låste benchmark på **2.125 point, 44 transfers, 28 hitpoint** bevares, men er ikke en måling af disse PM-kandidater. Der rapporteres derfor ingen opdigtet kandidat-TS-total eller personlige transferanbefalinger.

Produktionskode, låste koefficienter og appdata er uændrede af PM-forsøget; ingen kandidat er importeret i produktionskæden. `locked_model_active=false`, `promotion_allowed=false`. Korrekte algebraiske invariants og beståede regressioner er nødvendige, men giver ikke alene live-certificering. Denne isolerede PM-matrix bevarer også den oprindelige uafhængige XI-fysik og manglende særlige assistregler. De tidligere separate opt-in simulatorrettelser er ikke blandet ind i sammenligningen; deres samspil med en eventuel PM-kandidat er derfor endnu en separat test før produktion.

## Kode, tests og reproduktion

- Kandidatmodul: `src/fpl_v1_1_model/experimental_pm_conversion.py`.
- Screening/replay/diagnostik: `scripts/research_pm_conversion.py`, `scripts/replay_pm_conversion.py`, `scripts/diagnose_pm_conversion.py`.
- Kildekontrol og grupper: `scripts/audit_pm_nonpenalty_sources.py`, `scripts/postprocess_pm_conversion.py`.
- Ni målrettede regressioner: `tests/test_experimental_pm_conversion.py`; **519 tests bestået** i hele Python-suiten på 21,76 sekunder lokalt. Testene dækker bl.a. målbudget, ingen dobbelt skalering, uændrede straffeparametre, selvassistforbud, infeasible joint-margener, draw-identisk instrumentering, context restoration og cutoff-sikre grupper.
- [Isolated full model audit 38720239913](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720239913) er bestået på kodecommit `7c16891`: hele regressionen, browser-state/snapshot-tests, originalreproduktion, tidligere simulator-/MM-replays og benchmark-/horizon-kontrol. Workflow-fix `9c7ecbb` ændrer kun evidenseksportens checkout-rækkefølge.
- [Primære PM-resultater 38717540912](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38717540912): alle fire sæson/MM-arme, screening og fokusdiagnostik bestået.
- [Evidenseksport og ekstra kalibrering 38720669600](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38720669600): bestået. Den tidligere eksportfejl skyldtes checkout efter download og er rettet ved checkout først; den ændrede ikke de oprindelige beregninger.

`pm-conversion-research.yml` er den reproducerbare offline-kommando/protokol: genskab checksum-kilder, vælg hyperparametre fra udviklingsperioden, hent de dokumenterede originale MM/PM-inputs, kør hver arm og gem rapporter/predictions/prepared-inputs/cache. Artifacts opbevares 90 dage, mens de fulde numeriske JSON-rapporter og deres hashes nu også versionsstyres i repositoryet. Alle data i evidensen er offentlige spiller-/kampdata; ingen privat manager-state eller tokens er inkluderet.
