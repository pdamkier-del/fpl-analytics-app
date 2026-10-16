# Klubspecifik og dynamisk match importance: historisk kandidatstudie

Dato: 2026-10-16. PR #8, `research-role-injury-club-audit-20261016`.

## Beslutning

Behold den eksisterende kontrolmodel og produktions-MM. **Ingen importance-kandidat har dokumenteret en robust samlet forbedring af rotation og individuel spilleranvendelse.** Historisk brug af normale startere er en nyttig indikator; det er ikke tilstrækkelig dokumentation for en generel importance-komponent i MM.

Den dynamiske kandidat forbedrer ét defineret respons med objektive roller: andelen af de historiske normale startere i XI. Gevinsten holder ikke med eksisterende rolleprofiler og oversættes ikke til bedre individuelle startchancer. Klubspecifik historik giver heller ikke en robust marginal gevinst. Det er et forskningsresultat, ikke en produktionsgodkendelse.

**Fuld MM-simulation er ikke kørt.** PM, TS, FPL-point og chips er ikke kørt eller ændret. `locked_model_active=false`. Alle eksporterede importance-prognoser har `deadline_correct=false` og afvises af den strikte MM-featurelæser.

## 1. Fortsættelse fra eksisterende forskning og datagrænser

Reference: `docs/research/2026-10-16-mm-match-importance-results.md`, commit `b97d7c1`. Det tidligere inventar indeholder 35.735 spillerobservationer, 1.840 holdkampe og 1.743 komplette XI'er. Den tidligere XI-MAE 1,550→1,472 var en separat rotationsanalyse, ikke forbedring af MM.

Dette forsøg genbruger den stabile 2024/25-del: **19.600 spillerobservationer og 1.033 komplette hold-XI'er**. Der dannes 898 analyserbare holdkampe pr. rolledefinition efter minimum tre tidligere PL-kampe og mindst 11 tidligere kendte spillerprofiler. 398 ligger før januar 2025; 500 i senere evaluering. Samme 500 holdkampe bruges af alle kandidater og begge rolledefinitioner. Der er 5.500 evalueringsrækker med tidligere definerede normale spillere pr. rolledefinition.

2025/26 er **ikke** en ny sammenlignelig multi-competition-validering: FA Cup mangler, 40 europæiske source keys er i karantæne, europæiske XI'er mangler stabile ID'er, og nogle kickoff-/returkampversioner er fejlbehæftede. De 760 komplette PL-XI'er udfylder ikke de manglende tværturneringshistorikker. Vi hævder derfor ingen nye klubprioriteter eller modelresultater for 2025/26. Den eksisterende 280-rækkers dækningsmatrix bevares.

2024-kilderne har kickoff + fire timer som publiceringsproxy; faktisk publicering og historiske program-/faseversioner er ikke verificeret. Fase, normalroller og standings behandles derfor som **diagnostiske pre-kickoff/pre-deadline-konstruktioner**, ikke certificerede historiske forecasts. FPL-deadline bruges, hvor den eksisterende historiske MM har den; ellers markeres cutoff som pre-kickoff-diagnostik.

## 2. Hvad måler prioritet?

Der bruges ingen håndvalgt stjernespillerliste. En normalspillerkurv er de 11 spillere med størst **tidligere startchance × tidligere betinget startervarighed** blandt historisk kendte PL-spillere i klubben. Kurven beskriver et brugshierarki, ikke talent, den stærkeste lovlige XI eller en opstillingsprognose.

To rolledefinitioner testes separat:

1. **Objektiv historisk rolle:** starter-/bænkselektion i tidligere PL-kampe og kendte starterminutter. Eksisterende forskningspriors genbruges: startprior 0,65, eksponering 8, startervarighedsprior 77 minutter, eksponering 5, tids-halvering 180 dage. Ukendte bænkminutter udfyldes ikke. Fravær uden dokumenteret kampdagsselektion tilføjer hverken en start eller en taktisk bænkobservation.
2. **Eksisterende rolle:** den tidligere MM's bevarede normale startchance og startervarighed, kun når deres as-of er før cutoff. Manglende eksisterende profiler falder tilbage til den objektive profil; fallback-dækning vises nedenfor. Der findes ikke en yderligere verificeret historisk stjerneetiket, som vi kan indsætte uden at opfinde den.

Aktuel opstilling/minutter indgår **kun som labels**. Objektiv normalrolle bygger primært på PL for at undgå, at bevidst brug af cupreserver i sig selv gør dem til normale PL-startere. Historisk, eksplicit navngiven bænk bruges som tidligere kampdagsselektion; det er ikke en klinisk helbredsattest.

Aktuel tilgængelighed kommer kun fra kildekontrollerede, fixture-/deadline-matchede FPL-observationer. Gammel AVAILABLE videreføres aldrig til en cupkamp. Ukendt fravær, skader, suspensioner og transfers blandes ikke sammen som bevidst hvile. Normalrollen bevares under fravær; dokumenteret utilgængelighed er en separat kontrol. Historiske registreringer/transferdatoer er ikke fuldt verificerede, så `transfer_registration_verified=false`.

Responsvariable:

- `normal_share`: andelen af den før kampen fastlagte 11-spillerkurv, der starter. Ukendt fravær kan påvirke responsen; det er en **observeret selektionsintensitet**, ikke ren bevidst prioritet.
- `xi_changes`: ændringer fra forrige registrerede XI, forskelligt fra indskiftninger under kampen.
- `normal_minute_share`: normale spilleres andel af registrerede holdminutter. Ukendte minutter og manglende events betyder, at dette ikke er verificeret komplet minutsallokering.
- Individuel startindikator for de 11 før kampen valgte spillere, rapporteret både samlet og særskilt for eksplicit pre-deadline AVAILABLE. Ukendt tilgængelighed rapporteres separat.

Rolledefinitionerne har forskellige spillerkurve og dermed forskellige starterandel-/startchance-targets. Sammenlign kandidater **inden for** hver definition. XI-skift er samme fælles respons på tværs af begge.

| Rolledefinition | Analysekampe | Gns. andel eksisterende profiler | Ukendt tilgængelighed blandt normalspillere |
| --- | --- | --- | --- |
| existing | 898 | 0.86829 | 0.27182 |
| objective | 898 | 0.00000 | 0.27182 |


## 3. Objektive forhold, historisk adfærd og dynamik

De ønskede A/B/C/D-metoder implementeres med isolerede delmodeller:

| Variant | Informationslag |
| --- | --- |
| control | Klub, tidligere XI-stabilitet, tidligere rollehierarki, hvile, registrerede holdminutter 7/14 dage, særskilt kendt/ukendt tilgængelighed |
| A_objective | control + turnering, registreret fase/runde, sæsontid, historisk PL-placering/point pr. kamp, afstand til top/bund og modstanderens tidligere PL-point pr. kamp |
| B_global_history | control + fælles turneringseffekt og tidligere normalspillerbrug på tværs af klubber i turneringen |
| B_club_history | B_global + klubbens egen turneringshistorik og regulariseret klub×turnering-effekt |
| C_combined | A + B_club |
| D_dynamic | C + seneste tre kendte turneringsobservationer, forskel til klubbens PL-brug, ændring fra lang historik og en regulariseret klub×turnering×sæsontid-effekt |
| D_individual | D + normale spilleres belastning/hvile, rollevariation og profildækning som yderligere holdkontroller |

Alle individuelle startmodeller har derudover den konkrete spillers tidligere rolle, startervarighed, registrerede 7/14-døgnsminutter og hvile. Dermed sammenlignes importance-lagene med en kontrol, der allerede kender individuel rolle/belastning. D_individual tester den ekstra **fordeling af belastningen i normalspillerkurven**, ikke blot om vi husker at give kontrolmodellen spillerdata.

PL-stillingen rekonstrueres kun fra tidligere PL-resultater, der passerer +4t-proxyen; ved lige point bruges målforskel og scorede mål, og helt lige hold har samme provisoriske placering. Dette er almindelige ligapoint, **ingen FPL-pointberegning**. Klubbens ambitioner, kampens sande avancementsandsynlighed og trænerintention tilskrives ikke. Uverificerede samlede duelstillinger, næste kendte kamp, fremtidige sportslige udfald og fremtidige opstillinger indsættes ikke.

A er derfor en **tilgængelig sportslig proxy**, ikke en fuldt verificeret objektiv importance-sandhed. D er en dynamisk adfærdsmodel på de tilgængelige tidligere kampe, ikke en fuld optimering af et verificeret fremtidigt turneringsprogram.

## 4. Matematik, identifikation og usikkerhed

For et holdrespons bruges en penaliseret lineær model:

\[
y_m=b+a_c+\alpha_t+u_{ct}+\beta^\top X_m+\gamma^\top H_{ct,<m}+v_{ct}s_m+\epsilon_m.
\]

Kun de led, der hører til den pågældende variant, medtages. Klub-/turneringsinteraktioner regulariseres mod nul og dermed mod den fælles turneringseffekt. Estimation minimerer kvadreret fejl plus `alpha × sum(coef²)`; dette kan fortolkes som et hierarkisk Gaussian-prior/MAP-lag med fælles regularisering. Det er ikke en fuld empirisk Bayes-model med estimeret separat varians for hver klub. Få cupkampe giver ikke en fri, uregulariseret klubparameter.

En logistisk model med de samme informationslag bruges til den individuelle startindikator. Numeriske variable centreres og skaleres; sjældne kategorier bliver ikke opskaleret til samme varians som hyppige kategorier. Alpha vælges blandt 1/10/100 på december-data separat for hvert respons. Logistik vælges på Brier; kontinuerte responser på MAE. Ingen spiller-/klubspecifik manuel importance-vægt. Rollepriorernes 0,65 er en genbrugt starterprior, ikke en importance-score.

Rapporteret importance er en veldefineret **prognosekontrast i procentpoint**:

\[
I_m=100\{\hat y_m(\text{aktuel turnering/historik})-\hat y_m(\text{samme klub, PL-reference})\}.
\]

PL sættes dermed til nul inden for hver klub. Det er en rå lineær modelkontrast, ikke en kausal effekt og ikke en absolut psykologisk skala. **−20 betyder 20 procentpoint lavere modelestimeret normalstarterandel relativt til PL-referencen; det er ikke 20 % mindre vilje til at vinde.** Ingen subjektiv 0–100-skala bruges. Alle normale responsprognoser klippes til deres gyldige interval ved scoring; kontrasten vises i rå modelenheder.

Forskelle i evalueringsfejl får 1.000-draw cirkulær fireugers blok-bootstrap, der holder alle klubber/spillere i samme uge samlet. Prioritetsintervaller er et uge-cluster-sandwich omkring den penaliserede model, betinget på valgte features/alpha. Klubgennemsnittets kontrast får sin egen kovariansberegning; vi tager ikke blot et gennemsnit af enkeltkampenes standardfejl. Disse intervaller omfatter ikke ukendt kildekvalitet, alle modelvalg eller klinisk tilgængelighed. Hvis klub/turnering ikke findes i træning, beholdes det regulariserede prognosepunkt, men intervallet er **Not Available** frem for falsk sikkerhed om et uset effektled.

Conference League har kun Chelsea i disse PL-klubdata. En fri Chelsea-effekt kan ikke adskilles empirisk fra en fælles Conference-effekt dér; regularisering fastlægger en priorbaseret fordeling, ikke en identificeret klub-/turneringsårsag.

## 5. Kronologisk validering og faktiske resultater

Træning før 1. december 2024; alpha-valg i december; refit før 1. januar 2025; evaluering derefter. Historiske features opdateres med tidligere tilgængelige observationer, mens koefficienter fastholdes fra refit. Ingen aktuelle/fremtidige resultater kan indgå i egen featurehistorik.

Sæsonen er tidligere anvendt i forskning. De første kørsler i denne opgave fandt tab ved fælles alpha på tværs af responser; den endelige kørsel vælger derfor alpha separat pr. respons og retter numerisk centrering for logistisk konvergens. Det gør ikke senere data til et nyt uberørt holdout. Tallene er **genbrugt kronologisk forsknings-/evalueringsbevis**, ikke uafhængig produktionsvalidering. Der er ikke tunet særparametre til Chelsea, City eller andre klubber.


### Rolledefinition: objective

| Model | Normalandel MAE | Normalandel RMSE | XI MAE | XI RMSE | Minutandel MAE | Start-Brier alle | Start-Brier kendt AVAILABLE | Start-log-loss kendt AVAILABLE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control | 0.11868 | 0.15022 | 1.73575 | 2.23928 | 0.10836 | 0.15086 | 0.12633 | 0.41481 |
| A_objective | 0.11976 | 0.14807 | 1.91193 | 2.57188 | 0.11010 | 0.15094 | 0.12881 | 0.42196 |
| B_global_history | 0.11608 | 0.14641 | 2.14584 | 2.79611 | 0.10742 | 0.15243 | 0.13440 | 0.43564 |
| B_club_history | 0.11496 | 0.14571 | 2.06275 | 2.68874 | 0.10772 | 0.15309 | 0.13498 | 0.43727 |
| C_combined | 0.11387 | 0.14162 | 1.92761 | 2.56440 | 0.10535 | 0.15128 | 0.13538 | 0.43892 |
| D_dynamic | 0.10868 | 0.13743 | 1.90035 | 2.54379 | 0.10406 | 0.15853 | 0.14911 | 0.47269 |
| D_individual | 0.10903 | 0.13774 | 1.83077 | 2.43138 | 0.10450 | 0.14992 | 0.13356 | 0.43413 |


Marginal værdi for normalstarterandel, negativ forskel er bedre:

| Reference | Kandidat | MAE-forskel | 95% lav | 95% høj |
| --- | --- | --- | --- | --- |
| control | A_objective | 0.00109 | -0.00290 | 0.00532 |
| control | B_global_history | -0.00259 | -0.00805 | 0.00186 |
| B_global_history | B_club_history | -0.00112 | -0.00296 | 0.00069 |
| A_objective | C_combined | -0.00589 | -0.01244 | 0.00066 |
| B_club_history | C_combined | -0.00109 | -0.00342 | 0.00134 |
| C_combined | D_dynamic | -0.00519 | -0.00720 | -0.00310 |
| D_dynamic | D_individual | 0.00035 | -0.00004 | 0.00092 |


### Rolledefinition: existing

| Model | Normalandel MAE | Normalandel RMSE | XI MAE | XI RMSE | Minutandel MAE | Start-Brier alle | Start-Brier kendt AVAILABLE | Start-log-loss kendt AVAILABLE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control | 0.11048 | 0.14696 | 1.74279 | 2.23798 | 0.10001 | 0.15147 | 0.12828 | 0.42114 |
| A_objective | 0.11901 | 0.15150 | 1.85317 | 2.50397 | 0.10893 | 0.15220 | 0.13397 | 0.43698 |
| B_global_history | 0.11388 | 0.14847 | 2.12482 | 2.76636 | 0.10407 | 0.15188 | 0.13348 | 0.43520 |
| B_club_history | 0.11793 | 0.15681 | 2.03405 | 2.65600 | 0.10783 | 0.15221 | 0.13461 | 0.43803 |
| C_combined | 0.11096 | 0.14536 | 1.89275 | 2.51844 | 0.10179 | 0.15093 | 0.13682 | 0.44375 |
| D_dynamic | 0.11171 | 0.14623 | 1.88271 | 2.51203 | 0.10146 | 0.15227 | 0.13946 | 0.45068 |
| D_individual | 0.11695 | 0.14884 | 1.78402 | 2.36122 | 0.10480 | 0.14976 | 0.13475 | 0.43914 |


Marginal værdi for normalstarterandel, negativ forskel er bedre:

| Reference | Kandidat | MAE-forskel | 95% lav | 95% høj |
| --- | --- | --- | --- | --- |
| control | A_objective | 0.00853 | -0.00235 | 0.02141 |
| control | B_global_history | 0.00340 | -0.00272 | 0.01241 |
| B_global_history | B_club_history | 0.00405 | 0.00079 | 0.00673 |
| A_objective | C_combined | -0.00804 | -0.02039 | 0.00316 |
| B_club_history | C_combined | -0.00697 | -0.01233 | -0.00161 |
| C_combined | D_dynamic | 0.00074 | 0.00008 | 0.00137 |
| D_dynamic | D_individual | 0.00524 | 0.00112 | 0.01064 |


Samtlige numeriske responser, bias, RMSE, Brier/log-loss og parrede kontraster findes i `validation_metrics.csv`. Brier-kontraster er også beregnet særskilt for eksplicit AVAILABLE. `validation_predictions.csv.gz` giver alle 98.000 enkeltprognoser med observeret respons, model og cutoff, og `hyperparameter_selection.csv` alle før-evaluering-valg.

Den tidligere 1,550→1,472-XI-test har andre kontrolfeatures, responsspecifik modeludvælgelse og to flere evalueringskampe. Den må ikke bruges som direkte før/efter-resultat for dette forsøg.

### Kalibrering af individuelle startchancer


Direkte D_dynamic mod kontrol (negativ forskel er bedre; starterandel bruger MAE, startchance bruger Brier):

| Roller | Respons | Forskel | 95% lav | 95% høj |
| --- | --- | --- | --- | --- |
| existing | normal_player_started | 0.01118 | 0.00777 | 0.01541 |
| existing | normal_share | 0.00123 | -0.00554 | 0.00869 |
| objective | normal_player_started | 0.02278 | 0.01505 | 0.03083 |
| objective | normal_share | -0.01000 | -0.01550 | -0.00417 |

| Roller | Model | ECE, 10 faste bins | Spillerkampe |
| --- | --- | --- | --- |
| existing | A_objective | 0.05804 | 5500 |
| existing | B_club_history | 0.05655 | 5500 |
| existing | B_global_history | 0.05403 | 5500 |
| existing | C_combined | 0.05902 | 5500 |
| existing | D_dynamic | 0.06449 | 5500 |
| existing | D_individual | 0.05518 | 5500 |
| existing | control | 0.02965 | 5500 |
| objective | A_objective | 0.05254 | 5500 |
| objective | B_club_history | 0.05832 | 5500 |
| objective | B_global_history | 0.06129 | 5500 |
| objective | C_combined | 0.04158 | 5500 |
| objective | D_dynamic | 0.07332 | 5500 |
| objective | D_individual | 0.04122 | 5500 |
| objective | control | 0.02583 | 5500 |


ECE er en bin-afhængig kalibreringsdiagnostik, ikke en proper scoring rule. Brier/log-loss vægtes højere ved vurderingen. `calibration.csv` viser antal, gennemsnitlig prognose og faktisk startrate for hvert bin. Udvalget er tidligere normale spillere, ikke alle klubbens reserver; der påstås ingen fuld MM- eller reservekalibrering.

## 6. Klubvis prioritet og observeret adfærd

Tabellen viser D_dynamic med objektive roller som **eksperimentel beskrivelse**, fordi netop denne variant gav den tydeligste normalstarterandel-gevinst. Den er ikke udvalgt som universel vinder. Tidligere normale spillere er defineret før hver kamp. Alle turneringer med rå observationer er med; manglende evaluering bliver Not Available.

Observeret normalandel/minutandel og XI-skift er hele det modellerbare historiske udvalg. Modelkontrast og interval gælder den senere evaluering. De forskellige perioder må ikke forveksles. De rå kampantal og manglende warm-up fremgår af `sample_coverage.csv`.

| Klub | Turnering | Rå kampe | Model-eval kampe | Observeret normalandel | Registreret normalminutandel | XI-skift | Relativ prioritet pp | Betinget 95% lav | Betinget 95% høj | Træningskampe klub/turnering |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Arsenal | Champions League | 14 | 8.00000 | 0.68182 | 0.65887 | 3.35714 | 5.14342 | -1.38258 | 11.66942 | 6.00000 |
| Arsenal | FA Cup | 1 | 1.00000 | 0.63636 | 0.67197 | 3.00000 | -8.94633 | Not Available | Not Available | 0.00000 |
| Arsenal | League Cup | 5 | 2.00000 | 0.47273 | 0.47495 | 5.80000 | -23.30886 | -28.51368 | -18.10403 | 3.00000 |
| Arsenal | Premier League | 38 | 19.00000 | 0.69091 | 0.68879 | 3.42857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Aston Villa | Champions League | 12 | 6.00000 | 0.75000 | 0.71035 | 3.41667 | 6.47560 | 0.04328 | 12.90791 | 6.00000 |
| Aston Villa | FA Cup | 5 | 5.00000 | 0.65455 | 0.62586 | 3.00000 | -7.94518 | Not Available | Not Available | 0.00000 |
| Aston Villa | League Cup | 2 | Not Available | 0.13636 | 0.11667 | 10.00000 | Not Available | Not Available | Not Available | Not Available |
| Aston Villa | Premier League | 38 | 19.00000 | 0.73766 | 0.70804 | 3.11429 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Bournemouth | FA Cup | 4 | 4.00000 | 0.56818 | 0.56761 | 3.75000 | -10.84741 | Not Available | Not Available | 0.00000 |
| Bournemouth | League Cup | 1 | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available |
| Bournemouth | Premier League | 38 | 19.00000 | 0.71688 | 0.70311 | 2.17143 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Brentford | FA Cup | 1 | 1.00000 | 0.18182 | 0.25556 | 6.00000 | -4.77944 | Not Available | Not Available | 0.00000 |
| Brentford | League Cup | 4 | Not Available | 0.48485 | 0.47071 | 6.00000 | Not Available | Not Available | Not Available | Not Available |
| Brentford | Premier League | 38 | 19.00000 | 0.81558 | 0.79129 | 1.62857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Brighton | FA Cup | 4 | 4.00000 | 0.63636 | 0.60284 | 2.50000 | -6.11649 | Not Available | Not Available | 0.00000 |
| Brighton | League Cup | 3 | Not Available | 0.13636 | 0.18535 | 8.00000 | Not Available | Not Available | Not Available | Not Available |
| Brighton | Premier League | 38 | 19.00000 | 0.62338 | 0.62113 | 2.82857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Chelsea | Conference League | 13 | 7.00000 | 0.21678 | 0.21289 | 8.46154 | -31.34618 | -38.40599 | -24.28638 | 6.00000 |
| Chelsea | Conference qualification | 2 | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available |
| Chelsea | FA Cup | 2 | 2.00000 | 0.27273 | 0.35707 | 8.00000 | -18.33307 | Not Available | Not Available | 0.00000 |
| Chelsea | League Cup | 2 | Not Available | 0.13636 | 0.13030 | 11.00000 | Not Available | Not Available | Not Available | Not Available |
| Chelsea | Premier League | 38 | 19.00000 | 0.73247 | 0.71906 | 5.94286 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Crystal Palace | FA Cup | 6 | 6.00000 | 0.69697 | 0.65808 | 2.83333 | -10.07755 | Not Available | Not Available | 0.00000 |
| Crystal Palace | League Cup | 4 | Not Available | 0.75758 | 0.67205 | 2.33333 | Not Available | Not Available | Not Available | Not Available |
| Crystal Palace | Premier League | 38 | 19.00000 | 0.75844 | 0.72617 | 2.02857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Everton | FA Cup | 2 | 2.00000 | 0.54545 | 0.53838 | 3.50000 | -8.63677 | Not Available | Not Available | 0.00000 |
| Everton | League Cup | 2 | Not Available | 0.18182 | 0.24949 | 8.00000 | Not Available | Not Available | Not Available | Not Available |
| Everton | Premier League | 38 | 20.00000 | 0.70390 | 0.68907 | 1.85714 | 0.00000 | 0.00000 | 0.00000 | 15.00000 |
| Fulham | FA Cup | 4 | 4.00000 | 0.50000 | 0.50246 | 5.50000 | -12.45035 | Not Available | Not Available | 0.00000 |
| Fulham | League Cup | 2 | Not Available | 0.18182 | 0.20808 | 11.00000 | Not Available | Not Available | Not Available | Not Available |
| Fulham | Premier League | 38 | 19.00000 | 0.76104 | 0.73359 | 2.68571 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Ipswich | FA Cup | 3 | 3.00000 | 0.24242 | 0.26776 | 9.66667 | -16.60447 | Not Available | Not Available | 0.00000 |
| Ipswich | League Cup | 1 | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available |
| Ipswich | Premier League | 38 | 19.00000 | 0.69091 | 0.66827 | 3.37143 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Leicester | FA Cup | 2 | 2.00000 | 0.63636 | 0.59394 | 3.50000 | -4.54386 | Not Available | Not Available | 0.00000 |
| Leicester | League Cup | 3 | Not Available | 0.18182 | 0.21061 | 9.50000 | Not Available | Not Available | Not Available | Not Available |
| Leicester | Premier League | 38 | 19.00000 | 0.65195 | 0.62615 | 2.42857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Liverpool | Champions League | 10 | 4.00000 | 0.68182 | 0.65945 | 3.10000 | -2.90596 | -8.86979 | 3.05788 | 6.00000 |
| Liverpool | FA Cup | 2 | 2.00000 | 0.13636 | 0.09848 | 9.00000 | -17.11121 | Not Available | Not Available | 0.00000 |
| Liverpool | League Cup | 6 | 3.00000 | 0.42424 | 0.42306 | 5.83333 | -25.89709 | -30.56349 | -21.23068 | 3.00000 |
| Liverpool | Premier League | 38 | 20.00000 | 0.77922 | 0.75014 | 3.71429 | 0.00000 | 0.00000 | 0.00000 | 15.00000 |
| Man City | Champions League | 10 | 4.00000 | 0.67273 | 0.66061 | 3.80000 | 4.47234 | -0.68927 | 9.63396 | 6.00000 |
| Man City | FA Cup | 6 | 6.00000 | 0.42424 | 0.44630 | 7.00000 | -10.55898 | Not Available | Not Available | 0.00000 |
| Man City | League Cup | 2 | Not Available | 0.27273 | 0.28232 | 7.50000 | Not Available | Not Available | Not Available | Not Available |
| Man City | Premier League | 38 | 19.00000 | 0.66234 | 0.65858 | 4.02857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Man Utd | Europa League | 15 | 9.00000 | 0.61818 | 0.60884 | 3.80000 | 0.68879 | -6.94239 | 8.31997 | 6.00000 |
| Man Utd | FA Cup | 3 | 3.00000 | 0.69697 | 0.64486 | 2.00000 | -8.09504 | Not Available | Not Available | 0.00000 |
| Man Utd | League Cup | 3 | Not Available | 0.42424 | 0.43906 | 5.66667 | Not Available | Not Available | Not Available | Not Available |
| Man Utd | Premier League | 38 | 19.00000 | 0.65195 | 0.63565 | 3.97143 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Newcastle | FA Cup | 3 | 3.00000 | 0.39394 | 0.43434 | 8.00000 | -19.65823 | Not Available | Not Available | 0.00000 |
| Newcastle | League Cup | 7 | 3.00000 | 0.69697 | 0.67963 | 2.66667 | -14.54210 | -23.44527 | -5.63893 | 3.00000 |
| Newcastle | Premier League | 38 | 19.00000 | 0.80000 | 0.77253 | 2.00000 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Nott'm Forest | FA Cup | 5 | 5.00000 | 0.41818 | 0.48702 | 6.40000 | -17.88202 | Not Available | Not Available | 0.00000 |
| Nott'm Forest | League Cup | 1 | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available | Not Available |
| Nott'm Forest | Premier League | 38 | 19.00000 | 0.79221 | 0.76322 | 2.48571 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Southampton | FA Cup | 2 | 2.00000 | 0.54545 | 0.54495 | 3.00000 | -8.96582 | Not Available | Not Available | 0.00000 |
| Southampton | League Cup | 4 | Not Available | 0.42424 | 0.42088 | 6.33333 | Not Available | Not Available | Not Available | Not Available |
| Southampton | Premier League | 38 | 19.00000 | 0.60779 | 0.58699 | 3.14286 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Spurs | Europa League | 15 | 9.00000 | 0.49697 | 0.50793 | 5.33333 | -0.97006 | -8.38096 | 6.44083 | 6.00000 |
| Spurs | FA Cup | 2 | 2.00000 | 0.36364 | 0.38561 | 5.00000 | -11.06858 | Not Available | Not Available | 0.00000 |
| Spurs | League Cup | 5 | 2.00000 | 0.43636 | 0.43939 | 4.20000 | -13.42401 | -22.13151 | -4.71651 | 3.00000 |
| Spurs | Premier League | 38 | 19.00000 | 0.57922 | 0.56753 | 4.54286 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| West Ham | FA Cup | 1 | 1.00000 | 0.72727 | 0.71717 | 3.00000 | -6.53392 | Not Available | Not Available | 0.00000 |
| West Ham | League Cup | 2 | Not Available | 0.27273 | 0.32480 | 7.00000 | Not Available | Not Available | Not Available | Not Available |
| West Ham | Premier League | 38 | 19.00000 | 0.70649 | 0.67983 | 2.42857 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |
| Wolves | FA Cup | 3 | 3.00000 | 0.48485 | 0.48035 | 4.00000 | -9.54813 | Not Available | Not Available | 0.00000 |
| Wolves | League Cup | 2 | Not Available | 0.18182 | 0.23535 | 10.00000 | Not Available | Not Available | Not Available | Not Available |
| Wolves | Premier League | 38 | 19.00000 | 0.71688 | 0.69545 | 2.37143 | 0.00000 | 0.00000 | 0.00000 | 16.00000 |


### Chelsea, Manchester City, Arsenal, Liverpool, Aston Villa og Tottenham

Alle månedstal findes i `monthly_priorities.csv`. Nedenfor er de seks ønskede klubbers faktiske månedlige estimerede kontraster og observerede starterandele. Celler med få kampe er ikke en kausal ændringsanalyse. FA Cup findes først i den senere del af dette udvalg og har ofte ingen pre-januar-træning; intervaller mangler derfor med vilje. League Cup-kampe fra efteråret uden senere deltagelse giver ingen evalueret slutprioritet.


#### Chelsea

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Conference League | 2025-03 | 2 | -34.88169 | 0.36364 |
| Conference League | 2025-04 | 2 | -28.27071 | 0.27273 |
| Conference League | 2025-05 | 3 | -31.03950 | 0.36364 |
| FA Cup | 2025-01 | 1 | -9.06338 | 0.00000 |
| FA Cup | 2025-02 | 1 | -27.60276 | 0.54545 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.75000 |
| Premier League | 2025-02 | 4 | 0.00000 | 0.61364 |
| Premier League | 2025-03 | 2 | 0.00000 | 0.63636 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.74545 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.81818 |


#### Man City

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Champions League | 2025-01 | 2 | 4.44641 | 0.77273 |
| Champions League | 2025-02 | 2 | 4.49828 | 0.59091 |
| FA Cup | 2025-01 | 1 | -6.06261 | 0.27273 |
| FA Cup | 2025-02 | 1 | -19.62095 | 0.36364 |
| FA Cup | 2025-03 | 2 | -14.06330 | 0.45455 |
| FA Cup | 2025-04 | 1 | -4.97024 | 0.45455 |
| FA Cup | 2025-05 | 1 | -4.57347 | 0.54545 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.70455 |
| Premier League | 2025-02 | 4 | 0.00000 | 0.61364 |
| Premier League | 2025-03 | 2 | 0.00000 | 0.63636 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.52727 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.72727 |


#### Arsenal

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Champions League | 2025-01 | 2 | 6.20852 | 0.45455 |
| Champions League | 2025-03 | 2 | 1.51451 | 0.50000 |
| Champions League | 2025-04 | 3 | 5.75413 | 0.72727 |
| Champions League | 2025-05 | 1 | 8.43892 | 0.72727 |
| FA Cup | 2025-01 | 1 | -8.94633 | 0.63636 |
| League Cup | 2025-01 | 1 | -26.00698 | 0.81818 |
| League Cup | 2025-02 | 1 | -20.61073 | 0.81818 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.63636 |
| Premier League | 2025-02 | 4 | 0.00000 | 0.72727 |
| Premier League | 2025-03 | 2 | 0.00000 | 0.77273 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.58182 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.61364 |


#### Liverpool

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Champions League | 2025-01 | 2 | -2.95724 | 0.36364 |
| Champions League | 2025-03 | 2 | -2.85467 | 0.90909 |
| FA Cup | 2025-01 | 1 | -6.16277 | 0.18182 |
| FA Cup | 2025-02 | 1 | -28.05965 | 0.09091 |
| League Cup | 2025-01 | 1 | -29.51683 | 0.54545 |
| League Cup | 2025-02 | 1 | -28.18287 | 0.63636 |
| League Cup | 2025-03 | 1 | -19.99156 | 0.72727 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.95455 |
| Premier League | 2025-02 | 6 | 0.00000 | 0.89394 |
| Premier League | 2025-03 | 1 | 0.00000 | 0.72727 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.76364 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.65909 |


#### Aston Villa

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Champions League | 2025-01 | 2 | 3.43060 | 0.72727 |
| Champions League | 2025-03 | 2 | 6.84625 | 0.72727 |
| Champions League | 2025-04 | 2 | 9.14994 | 0.81818 |
| FA Cup | 2025-01 | 1 | -8.57356 | 0.54545 |
| FA Cup | 2025-02 | 2 | -10.12113 | 0.59091 |
| FA Cup | 2025-03 | 1 | -7.39011 | 0.63636 |
| FA Cup | 2025-04 | 1 | -3.51995 | 0.90909 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.75000 |
| Premier League | 2025-02 | 5 | 0.00000 | 0.67273 |
| Premier League | 2025-03 | 1 | 0.00000 | 0.63636 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.63636 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.77273 |


#### Spurs

| Turnering | Måned | Kampe | Estimeret relativ prioritet pp | Observeret normalstarterandel |
| --- | --- | --- | --- | --- |
| Europa League | 2025-01 | 2 | -4.09977 | 0.36364 |
| Europa League | 2025-03 | 2 | -6.21810 | 0.54545 |
| Europa League | 2025-04 | 2 | -1.53220 | 0.72727 |
| Europa League | 2025-05 | 3 | 4.98986 | 0.57576 |
| FA Cup | 2025-01 | 1 | -9.08680 | 0.27273 |
| FA Cup | 2025-02 | 1 | -13.05036 | 0.45455 |
| League Cup | 2025-01 | 1 | -16.73997 | 0.54545 |
| League Cup | 2025-02 | 1 | -10.10805 | 0.36364 |
| Premier League | 2025-01 | 4 | 0.00000 | 0.40909 |
| Premier League | 2025-02 | 4 | 0.00000 | 0.50000 |
| Premier League | 2025-03 | 2 | 0.00000 | 0.54545 |
| Premier League | 2025-04 | 5 | 0.00000 | 0.50909 |
| Premier League | 2025-05 | 4 | 0.00000 | 0.47727 |


Dette er historisk anvendelse, ikke et bevis for, hvor meget en træner subjektivt går op i en turnering. Cupmodstanderes niveau, uobserverede skader og truppens bredde kan påvirke tallene. Betydningen af store føringer for nøglespilleres udskiftning kan ikke identificeres uden verificerede tidsbestemte kampstillinger og udskiftningshændelser. Der er ikke opfundet sådan en effekt.

## 7. Ren integrationsoverflade til næste MM-runde

`pre_match_features.csv.gz` indeholder kun prædiktorer, før-kamp-modellens estimat/standardfejl og metadata. Aktuel normalstarterandel, faktiske XI-skift og faktiske minutter er **fjernet**. Den deskriptive klubgennemsnits-standardfejl, der bruger evalueringsperiodens featurefordeling, er også fjernet fra før-kamp-output. Individuelle features er separat i `individual_pre_match_features.csv.gz`; aktuelle start-/minutlabels findes kun i forskningsfilen `individual_role_samples.csv.gz`.

Kontrakten indeholder klub-ID, turnerings-ID, kamp-ID, cutoff/cutofftype, model/rolledefinition, importance-estimat og usikkerhed, historiske rolle-/belastningsfeatures, kildereference, publiceringsfelt, sidste historisk kendte tidspunkt og deadline-indikator. Individuelle rækker indeholder kilden/tidspunktet for eventuel verificeret FPL-tilgængelighed.

`require_deadline_features()` afviser responskolonner, falsk deadline-indikator, manglende eller fremtidig verificeret publicering og fremtidig historik. **Ingen række passerer nu**: publicering/programversioner er ufuldstændige, så alle er diagnostiske. Der er ikke lavet en bagdør til den låste MM.

## 8. Svar på de afsluttende spørgsmål

- **Prioriterer klubber turneringer forskelligt?** Observeret normalspillerbrug og rotation varierer mellem klubber/turneringer. Det er ikke en isoleret kausal trænerprioritet. Frie klubspecifikke effekter har ikke robust marginal prognoseværdi her; få cupkampe og enkeltklub-Conference begrænser identifikation.
- **Ændrer prioriteringen sig?** Observeret brug og de dynamiske modelkontraster ændrer sig gennem sæsonen. Den dynamiske model hjælper objektivt defineret normalstarterandel, men ikke stabilt på tværs af rolledefinitioner og individuelle startchancer. Det er ikke generelt valideret importance-dynamik.
- **Giver egen klubhistorik ekstra værdi?** Ikke robust: det lille objektive starterandel-estimat omfatter nul i intervallet, og eksisterende roller forværres. Ingen begrundelse for en fri klubparameter pr. turnering i produktion.
- **Giver individuelle roller og belastning ekstra forbedring?** De er allerede med i kontrol/startmodellerne. D_individual giver enkelte gevinster, men ingen samlet robust forbedring af alle mål eller kendt tilgængelige spilleres startchancer.
- **Er data tilstrækkelige til troværdig fuld MM-simulation?** Ikke til en deadline-certificeret tværsæson/all-competition-test. 2025-hullerne, historiske publicerings-/programversioner, tie states, ukendte registreringer og tilgængelighed består. Ingen fuld MM er kørt i denne opgave.
- **Hvilken variant anbefales?** Behold kontrolmodellen med eksisterende rolle-/tilgængelighedslag som reference. Bevar D_dynamic med objektive roller som en isoleret sekundær kandidat til en fremtidig kildeafgrænset MM-ablation, ikke som ny produktionsmodel. Kræv især forbedring af individuel startkalibrering og korrekt tilgængelighed, før integration overvejes.

## 9. Tests og reproduktion

61 fokuserede MM-/datatests består lokalt, herunder ni nye tests for at den aktuelle XI/minutter/resultat ikke lækker ind i egne features, ukendt fravær ikke bliver verificeret hvile, fremtidig pooled historik afvises, ukendte bænkminutter ikke opfindes, PL-ankeret er præcist nul, og den strikte læser fejler lukket. Klassifikatorer, der ikke konvergerer, får hele kørslen til at fejle.

```bash
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py
python scripts/restore_2024_25_data_checkpoint.py
python scripts/archive_role_injury_mm.py --restore work/priority-mm-source
cp work/priority-mm-source/results/predictions.npz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/experimental_club_match_importance.py
python scripts/report_club_match_importance.py
PYTHONPATH=src:scripts:. python -m pytest tests/test_club_match_importance.py tests/test_mm_competition_rotation.py tests/test_mm_all_clubs.py tests/test_mm_probability_robustness.py tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
```

Kildemanifest og indholdschecksums findes sammen med resultaterne. Gzip-indhold sammenlignes efter dekomprimering. Workflow `mm-club-importance.yml` gendanner samme arkiver, kører de faktiske kandidater og sikrer uændret produktions-`src` og frossen MM-prognosechecksum. Produktionsparametre, 2.125-point-benchmark og `locked_model_active=false` er bevaret.


### Verificeret Actions og genkørsel

[Actions 38961530083](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38961530083) er bestået med alle 61 tests, modelkørsler, produktionsdiff og frossen MM-checksum. Kode `e7422b1`, resultatcommit `9fae5f8`. Artifact 12073510644 er downloadet og ZIP-SHA-256-verificeret; alle 13 manifestførte filer og gzip-streams er valideret.

En separat lokal genkørsel matcher 6/13 filindhold byte-for-byte. De øvrige matcher rækker, labels, missingness, modelvalg og tal med højst 1.55e-08 absolut numerisk forskel (kontrolleret tolerance 1e−6). De syv regressions-/klassifikationsfiler påstås ikke at være byteidentiske. Det fulde bevis findes i `docs/checkpoints/2026-10-16-club-importance-reproduction.json`. `docs/research/data/2026-10-16-importance-overall-contrasts.csv` dannes reproducerbart af rapportscriptet fra de verificerede enkeltprognoser; det er ikke en ny modelkørsel.
