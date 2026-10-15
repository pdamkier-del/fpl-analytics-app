# Mål- og assistmodel: audit og isolerede forsøg

PR #3, model-audit-optimization-20261012. Produktionsbaseline og koefficienter ændres ikke; locked_model_active=false. Ingen manager-state anvendes. Dette er et løbende forskningscheckpoint; resultater mærkes først bestået efter faktiske afsluttede kørsler.

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
2. **Gamma-Poisson conversion:** theta~Gamma(tau,tau), Y|X,theta~Pois(theta*X), E(theta|history)=(Y+tau)/(X+tau). Det er en effektiv kalibreringskorrektion på all-xG, ikke identificeret NPG-finishing.8mål/5xG vedtau50 bliver1.0545, ikke1.6.
3. **Assist conversion:** samme struktur med FPL-assists/xA. Den identificerer ikke ren kreativitet; modtageres finishing og FPL-regler er blandet i udfaldet.
4. **Hierarkisk EB:** spillerens Gamma-prior-middel shrinkes mod aktuel sæsons hold, som shrinkes mod league-conversion. Begge events testes. Der opfindes ikke en separat ligaforskel fra data om kun én liga.
5. **Total-finishing:** den relative spillerkorrektion normaliseres én gang; optionalt korrigeres ordinary-team-lambda med den forventede eksponeringsvægtede finishingfaktor. Straffekonvertering og straffemasse fastholdes. En uniform finishingfaktor2 flytter ordinary-total2x, ikke4x. Fixed-total- og changed-total-arme holdes adskilt.
6. **Joint marginal assist:** en maksimum-entropy jointfordeling med scorermarginaler og assistmarginaler, structural-zero på selvassist. IPF løser marginalerne, ingen specifik pair-evne estimeres. Infeasible aktive margener afvises og falder tilbage til oprindelig lovlig vægtning; antallet rapporteres. Den oprindelige assistcoin og målprocessen ændres ikke.

Kalenderhalveringstid90d/365d/hele tilgængelige historie og tau5/20/80 screenes. Hierarkiets team-priorstyrke20/80/320 vælges også på udviklingsdata; dette er sekventiel empirical-Bayes shrinkage, ikke en fuldt estimeret Bayesian posterior-variance-model. Hyperparametre vælges på2024/25GW6–21 med en pre-kickoff analytisk event-proxy; **target-kampens realiserede xG/minutter er aldrig forecast-input**. Proxymetoden og fuld event-time-PM holdes adskilt. Valget skrives før senere2025-targetforecasts læses. Test:2024GW22–38 og2025GW6–38.

Først måles alle PM-arme med låst MM. Derefter sammenlignes uændret PM og to prædefinerede PM-kombinationer under samme eksperimentelle start+survival-MM. Ingen forbedring tilskrives PM ved at sammenligne en fælles MM+PM-ændring alene med gammel baseline.

Fuld PM er400draws/fixture med originale seeds og exact-reference-guard. Simulatoren instrumenteres kun til eventtællinger; en regression beviser draw-for-draw identitet. Scoringslag og BPS-koefficienter ændres ikke. Binære goal/assist-sandsynligheder har eksplicit MonteCarlo-Jeffreys-smoothing; Poisson count-NLL er en særskilt diagnostic-approksimation, ikke den fulde MonteCarlo-countdistribution. Fixture-bootstrap dækker sampling af kampe, ikke al simulationsstøj. Der rapporteres MAE/RMSE/bias, eventproper-scores, kalibrering, bonus, spillede spillere og positioner.

## Status og produktionskrav

Kode og regressioner er implementeret isoleret. Numeriske resultater tilføjes efter afsluttede kørsler; ingen kandidat er valgt til produktion. Historiske fremtidige seks-GW-celler mangler stadig, så et nyt korrekt kandidat-TS-total mod2125 kan ikke opfindes. Den originale baseline bevares.

Primære metodereferencer: [StatsBomb: Quantifying finishing skill](https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/), [Biases in Expected Goals Models Confound Finishing Ability](https://arxiv.org/abs/2401.09940), [FPL scoring/assist rules](https://www.premierleague.com/en/news/2174909/), [2025/26 assist changes](https://www.premierleague.com/en/news/4362187/whats-new-in-202526-fantasy-changes-to-assists-rules). De begrunder forsøg/afgrænsning, ikke en påstået forbedring i vores model.
