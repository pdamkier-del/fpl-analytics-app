# Klubvis MM-evaluering: alle Premier League-klubber, 2024/25 og 2025/26

**Kun MM.** Ingen PM, FPL-point, TS eller chips er simuleret eller ændret. Produktionskoden er uændret; `locked_model_active=false`.

## Hovedresultat

Den eksisterende kandidat med rolle, kilde-news, spillechanceloft og bevaret startvarighed ved selection-retur sænker samlet minut-MAE. Det er et forskningsresultat på tidligere anvendte perioder, ikke en ny uafhængig godkendelse. At erstatte betinget startvarighed med den langsigtede rolleprofil for alle spillere forværrer MAE, men forbedrer RMSE. Den er derfor ikke en generel forbedring og anbefales ikke som erstatning ved det hidtidige MAE-fokus.

## Identiske cohorts og informationsgrænser

Alle 20 klubber er evalueret i hver sæson. 2024/25 GW6–21 vises separat som genbrugt udviklingsperiode; hovedsammenligningen bruger 2024/25 GW22–38 og 2025/26 GW6–38. GW1–5 mangler MM-forecasts i dette checkpoint og må ikke udgives som testet. Der er 540 klub/model/periode-kombinationer (9 arme × 60 klubperioder); de fem efterspurgte hovedarme giver 200 klub/model-kombinationer i evalueringen.

Det er en deterministisk evaluering af de frosne walk-forward-MM-forudsigelser og nye isolerede s-ablationer, ikke nye Monte Carlo-kampforløb. Betingede minutgennemsnit og sandsynligheder evalueres; ingen ny fuld survival-fordeling eller joint XI-simulation påstås. Hver frossen spillerkamp er koblet én-til-én til Core: spiller-ID, sæson, fixture, klub, GW, faktiske starter og minutter er kontrolleret. Samtlige modelarme har identiske nøgler/truth/cutoffs. Kickoff ligger efter cutoff; alle anvendte news-snapshots ligger strengt før cutoff. Klub-ID’er er sæsonafgrænsede. Historisk offentliggørelse af realiserede kampdata er stadig den nedarvede kickoff+3/4h-proxy, så fuld kildecertificering er ikke påstået.

Normalrolle og nyhedsstatus holdes adskilt. Ukendt tilgængelighed bliver ikke rask. En source-selection-return betyder første kildebekræftede AVAILABLE efter en dokumenteret FPL-medical-flagning, ikke lægelig clearance. Der er ingen verificerede træningsreturdatoer i dette lag.

## Samlet evaluering, begge sæsoner

| MM-arm | N | Minut-MAE | RMSE | Bias | Start-Brier | Spille-Brier | Falske nul-spillechancer | MAE−original [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Låst MM | 39264 | 11.241 | 21.116 | -0.083 | 0.07345 | 0.08436 | 0 | 0.000 [0.000, 0.000] |
| Individuel rolle-MM | 39264 | 11.029 | 20.931 | -0.270 | 0.07293 | 0.08191 | 19 | -0.212 [-0.257, -0.168] |
| Rolle + news | 39264 | 10.682 | 20.667 | -0.335 | 0.07126 | 0.07903 | 35 | -0.558 [-0.620, -0.502] |
| Rolle + chance-loft | 39264 | 10.528 | 20.437 | -0.397 | 0.07012 | 0.07676 | 35 | -0.712 [-0.883, -0.596] |
| Chance-loft + returvarighed | 39264 | 10.521 | 20.417 | -0.378 | 0.07012 | 0.07676 | 35 | -0.719 [-0.889, -0.604] |
| Fuld før-skade-rolle ved retur | 39264 | 10.715 | 20.661 | -0.248 | 0.07152 | 0.07744 | 35 | -0.525 [-0.597, -0.456] |
| Kun returvarighed uden chance-loft | 39264 | 10.675 | 20.646 | -0.316 | 0.07126 | 0.07903 | 35 | -0.565 [-0.629, -0.510] |
| News + rollevarighed for alle | 39264 | 11.057 | 20.512 | -0.259 | 0.07126 | 0.07903 | 35 | -0.183 [-0.264, -0.099] |
| Chance-loft + rollevarighed for alle | 39264 | 10.907 | 20.286 | -0.311 | 0.07012 | 0.07676 | 35 | -0.334 [-0.504, -0.199] |


Minut-MAE er vægtet efter antal spillerkampe, ikke et uvægtet gennemsnit af klubber/sæsoner. Kombinationsintervaller resampler sæsonerne separat. Alle nul-spillechancer med faktisk spil har teoretisk uendelig log-loss; de viste finite log-loss-tal anvender det eksplicitte numeriske klip 1e−12 og må ikke skjule denne begrænsning.

## Hvilke grupper er sværest, og hvorfor MAE/RMSE er uenige

| Gruppe | Model | N | MAE | RMSE | Bias |
| --- | --- | --- | --- | --- | --- |
| regular | Rolle + chance-loft | 4813 | 13.637 | 22.928 | 0.442 |
| regular | Chance-loft + returvarighed | 4813 | 13.637 | 22.928 | 0.442 |
| regular | Chance-loft + rollevarighed for alle | 4813 | 14.829 | 22.692 | -0.960 |
| rotation_or_short_history | Rolle + chance-loft | 10164 | 21.253 | 29.379 | -0.605 |
| rotation_or_short_history | Chance-loft + returvarighed | 10164 | 21.236 | 29.344 | -0.554 |
| rotation_or_short_history | Chance-loft + rollevarighed for alle | 10164 | 21.890 | 29.142 | -0.412 |
| reserve | Rolle + chance-loft | 24287 | 5.424 | 14.486 | -0.476 |
| reserve | Chance-loft + returvarighed | 24287 | 5.420 | 14.470 | -0.466 |
| reserve | Chance-loft + rollevarighed for alle | 24287 | 5.533 | 14.416 | -0.141 |
| prior_three_full_starts | Rolle + chance-loft | 5664 | 14.581 | 25.106 | 0.737 |
| prior_three_full_starts | Chance-loft + returvarighed | 5664 | 14.577 | 25.101 | 0.742 |
| prior_three_full_starts | Chance-loft + rollevarighed for alle | 5664 | 15.919 | 25.042 | -1.680 |
| single_short_after_three_full | Rolle + chance-loft | 508 | 19.229 | 30.658 | -9.124 |
| single_short_after_three_full | Chance-loft + returvarighed | 508 | 19.082 | 30.428 | -8.408 |
| single_short_after_three_full | Chance-loft + rollevarighed for alle | 508 | 18.868 | 28.925 | -2.335 |
| actually_played_evaluation_only | Rolle + chance-loft | 15188 | 19.781 | 27.633 | -8.463 |
| actually_played_evaluation_only | Chance-loft + returvarighed | 15188 | 19.754 | 27.583 | -8.422 |
| actually_played_evaluation_only | Chance-loft + rollevarighed for alle | 15188 | 20.341 | 27.085 | -8.660 |


Rollevarighed-for-alle giver præcis ændringen Δx=p·Δs, fordi p/q/c er uændrede. Kvadreret fejl ændres med 2·(x−minutter)·p·Δs+(p·Δs)². Den kan derfor reducere få store fejl og samtidig gøre mange moderate fejl større. Gruppen efter én kort start forbedres deskriptivt, mens gruppen med tre tidligere fulde starter forværres i MAE; dette begrunder ikke en ny efterfølgende specialregel på samme evalueringsdata.

Actually-played/started og played-return er outcome-betingede diagnostiske grupper. Deres bias kan ikke alene bevise fejlkalibrering af ubetinget startchance: hvis man kun vælger faktisk startende spillere, vil en korrekt usikker prognose ofte ligge under deres realiserede minutter. De før-cutoff definerede rollegrupper og Brier/log-loss skal læses sammen med dem.

## De første 1–3 kampe efter kildebekræftet selection-retur

| Returgruppe | Model | N | MAE | Minut-bias | Start-Brier | Spille-Brier |
| --- | --- | --- | --- | --- | --- | --- |
| scheduled_return_1 | Låst MM | 438 | 22.567 | -17.116 | 0.17949 | 0.34205 |
| scheduled_return_1 | Chance-loft + returvarighed | 438 | 21.715 | -14.833 | 0.17566 | 0.34243 |
| scheduled_return_2 | Låst MM | 420 | 22.999 | -11.987 | 0.16592 | 0.20682 |
| scheduled_return_2 | Chance-loft + returvarighed | 420 | 22.511 | -10.739 | 0.15672 | 0.19658 |
| scheduled_return_3 | Låst MM | 409 | 21.796 | -8.912 | 0.16216 | 0.13867 |
| scheduled_return_3 | Chance-loft + returvarighed | 409 | 21.330 | -7.692 | 0.15114 | 0.13308 |
| played_return_1 | Låst MM | 401 | 30.600 | -27.895 | 0.26401 | 0.56039 |
| played_return_1 | Chance-loft + returvarighed | 401 | 29.691 | -25.809 | 0.26121 | 0.56679 |
| played_return_2 | Låst MM | 366 | 29.060 | -22.378 | 0.23602 | 0.23963 |
| played_return_2 | Chance-loft + returvarighed | 366 | 27.839 | -20.311 | 0.21509 | 0.21528 |
| played_return_3 | Låst MM | 346 | 25.234 | -15.226 | 0.19712 | 0.15599 |
| played_return_3 | Chance-loft + returvarighed | 346 | 24.419 | -13.566 | 0.18039 | 0.14061 |


Klubvise parrede intervaller og alle øvrige metric findes i JSON/CSV. Første observerede source-AVAILABLE er ikke præcis lægelig raskmelding; episoder ved datasættets start kan være venstrecensurerede, og GW1–5-returer kan mangle. N for planlagte kampe og faktiske deltagelser må ikke lægges sammen.

## Usikkerhed og modelvalg

Der bruges 1.000 parrede circular moving-GW-block-bootstrap-træk med bloklængde 4 og fast seed. Alle kampe og spillere i samme GW følger samme træk; blanke klub-GWs forbliver på kalenderaksen. Under otte befolkede GWs står intervallet Not Available. Især 17 evaluerings-GWs i 2024/25 giver få effektive blokke. Intervallerne dækker ikke kildefejl, ubekræftede medicinske forhold eller gentagen modeludvælgelse; ingen multiplicitetskorrektion er foretaget. Perioderne er genbrugt forskning, ikke uberørte holdouts.

Ni arme indeholder de fem bestilte plus isolerede komponenttests: kun kildeprocent, kun retur-s, fuld før-skade-tuple, og kun s fra den eksisterende frosne rollevarighed for alle spillere. De sidste to s-arme ændrer ikke p, q eller c. Ingen ny modelparameter er fitted, og ingen klub- eller spillerjustering vælges ud fra disse tabeller. “Ny” i klubtabellen er den allerede fastlagte chance+returvarighedskandidat, ikke den bedste model valgt separat for hver klub.

## 2024-25 – alle 20 klubber

20 klubber forbedres og 0 forværres mod den oprindelige MM. Rækkefølge: størst ny minut-MAE først. Negativ delta betyder forbedring.

| Klub | Original MAE | Ny MAE | Delta [95% CI] | Største dokumenterede problem |
| --- | --- | --- | --- | --- |
| Man City | 18.663 | 16.755 | -1.908 [-2.423, -1.451] | Startudvælgelse; sværest: rotation_or_short_history (MAE 29.413); 1 falske nuller; kausal årsag ikke fastlagt |
| Ipswich | 16.565 | 15.023 | -1.542 [-1.924, -1.204] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.032); 3 falske nuller; kausal årsag ikke fastlagt |
| West Ham | 16.375 | 14.935 | -1.440 [-1.968, -0.902] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.425); kausal årsag ikke fastlagt |
| Man Utd | 16.255 | 13.777 | -2.477 [-3.252, -1.725] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.613); kausal årsag ikke fastlagt |
| Spurs | 15.882 | 13.407 | -2.475 [-3.182, -1.878] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.829); 2 falske nuller; kausal årsag ikke fastlagt |
| Liverpool | 13.542 | 12.737 | -0.804 [-1.299, -0.448] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.212); 1 falske nuller; kausal årsag ikke fastlagt |
| Fulham | 13.324 | 12.642 | -0.682 [-1.562, 0.048] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.614); kausal årsag ikke fastlagt |
| Leicester | 14.095 | 12.164 | -1.931 [-2.935, -0.949] | Startudvælgelse; sværest: regular (MAE 19.091); kausal årsag ikke fastlagt |
| Aston Villa | 13.184 | 12.148 | -1.037 [-1.705, -0.283] | Startudvælgelse; sværest: rotation_or_short_history (MAE 25.430); 1 falske nuller; kausal årsag ikke fastlagt |
| Southampton | 13.114 | 11.977 | -1.137 [-1.634, -0.660] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.723); kausal årsag ikke fastlagt |
| Arsenal | 12.343 | 11.171 | -1.172 [-1.804, -0.703] | Startudvælgelse; sværest: rotation_or_short_history (MAE 17.875); 1 falske nuller; kausal årsag ikke fastlagt |
| Nott'm Forest | 10.412 | 9.477 | -0.935 [-1.267, -0.670] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.233); kausal årsag ikke fastlagt |
| Chelsea | 10.099 | 9.416 | -0.684 [-1.004, -0.387] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.421); 1 falske nuller; kausal årsag ikke fastlagt |
| Everton | 10.967 | 9.413 | -1.554 [-2.548, -0.755] | Startudvælgelse; sværest: rotation_or_short_history (MAE 16.659); 1 falske nuller; kausal årsag ikke fastlagt |
| Crystal Palace | 10.157 | 9.253 | -0.904 [-1.624, -0.446] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.096); 3 falske nuller; kausal årsag ikke fastlagt |
| Newcastle | 11.251 | 9.245 | -2.007 [-3.252, -1.304] | Startudvælgelse; sværest: rotation_or_short_history (MAE 14.627); kausal årsag ikke fastlagt |
| Brighton | 11.225 | 8.721 | -2.504 [-3.350, -1.715] | Startudvælgelse; sværest: rotation_or_short_history (MAE 18.568); 2 falske nuller; kausal årsag ikke fastlagt |
| Wolves | 9.405 | 8.117 | -1.288 [-1.708, -0.898] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.990); kausal årsag ikke fastlagt |
| Bournemouth | 9.356 | 7.233 | -2.124 [-2.598, -1.729] | Startudvælgelse; sværest: rotation_or_short_history (MAE 16.058); kausal årsag ikke fastlagt |
| Brentford | 7.774 | 7.025 | -0.749 [-1.331, -0.258] | Startudvælgelse; sværest: rotation_or_short_history (MAE 17.117); kausal årsag ikke fastlagt |


[Fuld klubrapport med fem hovedarme, grupper, returer og ti største fejl pr. klub](2026-10-16-mm-clubs-2024-25.md). Alle ni arme og alle modelvarianters ti største fejl findes i CSV/JSON.

### Isolerede komponentændringer

| Kandidat | Reference | MAE-delta [95% CI] | Spille-Brier-delta [95% CI] |
| --- | --- | --- | --- |
| Rolle + chance-loft | Rolle + news | -0.112 [-0.137, -0.087] | -0.002 [-0.003, -0.002] |
| Kun returvarighed uden chance-loft | Rolle + news | -0.004 [-0.019, 0.006] | 0.000 [0.000, 0.000] |
| Fuld før-skade-rolle ved retur | Rolle + news | 0.057 [0.014, 0.101] | -0.002 [-0.003, -0.001] |
| Chance-loft + returvarighed | Rolle + chance-loft | -0.004 [-0.019, 0.007] | 0.000 [0.000, 0.000] |
| News + rollevarighed for alle | Rolle + news | 0.322 [0.262, 0.369] | 0.000 [0.000, 0.000] |
| Chance-loft + rollevarighed for alle | Rolle + chance-loft | 0.323 [0.263, 0.373] | 0.000 [0.000, 0.000] |


### Manchester City, Chelsea, Arsenal og Liverpool

#### Man City

Original MAE 18.663 → 16.755; ny RMSE 28.336; bias -0.029. Startudvælgelse; sværest: rotation_or_short_history (MAE 29.413); 1 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=51, MAE 23.372, bias 7.118, start-bias 0.091. Reserver: N=349, MAE 7.300, start-bias -0.013. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=150, betinget startvarigheds-MAE 2.407, varigheds-bias 2.407. Efter tre fulde starter efterfulgt af én start under 60 min: N=3, MAE 23.705, betinget varigheds-bias Not Available. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 0. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Liverpool

Original MAE 13.542 → 12.737; ny RMSE 22.616; bias -0.588. Startudvælgelse; sværest: rotation_or_short_history (MAE 25.212); 1 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=100, MAE 15.774, bias 1.647, start-bias 0.019. Reserver: N=366, MAE 6.932, start-bias 0.003. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=92, betinget startvarigheds-MAE 3.435, varigheds-bias 3.431. Efter tre fulde starter efterfulgt af én start under 60 min: N=19, MAE 2.795, betinget varigheds-bias -39.775. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 0. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Arsenal

Original MAE 12.343 → 11.171; ny RMSE 20.697; bias -0.285. Startudvælgelse; sværest: rotation_or_short_history (MAE 17.875); 1 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=70, MAE 15.423, bias 4.800, start-bias 0.041. Reserver: N=321, MAE 6.233, start-bias -0.005. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=83, betinget startvarigheds-MAE 3.294, varigheds-bias 3.292. Efter tre fulde starter efterfulgt af én start under 60 min: N=25, MAE 7.621, betinget varigheds-bias -25.883. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 4. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Chelsea

Original MAE 10.099 → 9.416; ny RMSE 19.743; bias -0.240. Startudvælgelse; sværest: rotation_or_short_history (MAE 21.421); 1 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=62, MAE 15.912, bias 0.780, start-bias 0.012. Reserver: N=512, MAE 3.681, start-bias -0.004. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=129, betinget startvarigheds-MAE 2.601, varigheds-bias 2.468. Efter tre fulde starter efterfulgt af én start under 60 min: N=16, MAE 20.717, betinget varigheds-bias -32.186. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 4. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

## 2025-26 – alle 20 klubber

20 klubber forbedres og 0 forværres mod den oprindelige MM. Rækkefølge: størst ny minut-MAE først. Negativ delta betyder forbedring.

| Klub | Original MAE | Ny MAE | Delta [95% CI] | Største dokumenterede problem |
| --- | --- | --- | --- | --- |
| Chelsea | 14.558 | 14.012 | -0.546 [-0.901, -0.251] | Startudvælgelse; sværest: rotation_or_short_history (MAE 23.843); kausal årsag ikke fastlagt |
| Fulham | 13.532 | 13.062 | -0.470 [-1.137, -0.031] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.988); 2 falske nuller; kausal årsag ikke fastlagt |
| Newcastle | 12.311 | 12.058 | -0.253 [-0.403, -0.105] | Startudvælgelse; sværest: regular (MAE 21.113); kausal årsag ikke fastlagt |
| Arsenal | 12.366 | 12.031 | -0.334 [-0.518, -0.192] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.697); 2 falske nuller; kausal årsag ikke fastlagt |
| Man City | 11.860 | 11.524 | -0.335 [-0.541, -0.139] | Startudvælgelse; sværest: rotation_or_short_history (MAE 22.656); 1 falske nuller; kausal årsag ikke fastlagt |
| Wolves | 11.614 | 11.459 | -0.155 [-0.557, 0.118] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.644); 1 falske nuller; kausal årsag ikke fastlagt |
| Aston Villa | 11.497 | 11.225 | -0.272 [-0.447, -0.095] | Startudvælgelse; sværest: rotation_or_short_history (MAE 26.003); 4 falske nuller; kausal årsag ikke fastlagt |
| Nott'm Forest | 11.015 | 10.726 | -0.289 [-0.553, -0.069] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.622); 1 falske nuller; kausal årsag ikke fastlagt |
| Leeds | 10.700 | 10.460 | -0.240 [-0.445, -0.031] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.435); 1 falske nuller; kausal årsag ikke fastlagt |
| Liverpool | 10.792 | 10.335 | -0.456 [-0.787, -0.204] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.871); kausal årsag ikke fastlagt |
| Spurs | 10.596 | 10.282 | -0.315 [-0.449, -0.201] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.562); 2 falske nuller; kausal årsag ikke fastlagt |
| West Ham | 10.164 | 9.910 | -0.254 [-0.611, 0.026] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.237); kausal årsag ikke fastlagt |
| Burnley | 9.933 | 9.787 | -0.146 [-0.413, 0.051] | Startudvælgelse; sværest: rotation_or_short_history (MAE 20.502); 1 falske nuller; kausal årsag ikke fastlagt |
| Crystal Palace | 9.738 | 9.378 | -0.360 [-0.588, -0.170] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.901); kausal årsag ikke fastlagt |
| Man Utd | 9.773 | 9.295 | -0.478 [-1.122, -0.030] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.463); kausal årsag ikke fastlagt |
| Brighton | 9.241 | 9.025 | -0.216 [-0.482, 0.024] | Startudvælgelse; sværest: rotation_or_short_history (MAE 21.652); 1 falske nuller; kausal årsag ikke fastlagt |
| Brentford | 8.963 | 8.722 | -0.242 [-0.524, -0.048] | Startudvælgelse; sværest: rotation_or_short_history (MAE 19.974); kausal årsag ikke fastlagt |
| Everton | 9.007 | 8.471 | -0.535 [-1.071, -0.094] | Startudvælgelse; sværest: rotation_or_short_history (MAE 18.613); kausal årsag ikke fastlagt |
| Bournemouth | 7.479 | 7.302 | -0.177 [-0.489, 0.062] | Startudvælgelse; sværest: rotation_or_short_history (MAE 17.789); 3 falske nuller; kausal årsag ikke fastlagt |
| Sunderland | 7.755 | 7.176 | -0.579 [-1.315, -0.135] | Startudvælgelse; sværest: rotation_or_short_history (MAE 17.469); kausal årsag ikke fastlagt |


[Fuld klubrapport med fem hovedarme, grupper, returer og ti største fejl pr. klub](2026-10-16-mm-clubs-2025-26.md). Alle ni arme og alle modelvarianters ti største fejl findes i CSV/JSON.

### Isolerede komponentændringer

| Kandidat | Reference | MAE-delta [95% CI] | Spille-Brier-delta [95% CI] |
| --- | --- | --- | --- |
| Rolle + chance-loft | Rolle + news | -0.175 [-0.415, -0.035] | -0.002 [-0.005, -0.001] |
| Kun returvarighed uden chance-loft | Rolle + news | -0.009 [-0.015, -0.002] | 0.000 [0.000, 0.000] |
| Fuld før-skade-rolle ved retur | Rolle + news | 0.021 [-0.024, 0.070] | -0.002 [-0.002, -0.001] |
| Chance-loft + returvarighed | Rolle + chance-loft | -0.009 [-0.015, -0.002] | 0.000 [0.000, 0.000] |
| News + rollevarighed for alle | Rolle + news | 0.401 [0.342, 0.457] | 0.000 [0.000, 0.000] |
| Chance-loft + rollevarighed for alle | Rolle + chance-loft | 0.406 [0.345, 0.462] | 0.000 [0.000, 0.000] |


### Manchester City, Chelsea, Arsenal og Liverpool

#### Chelsea

Original MAE 14.558 → 14.012; ny RMSE 24.777; bias -0.197. Startudvælgelse; sværest: rotation_or_short_history (MAE 23.843); kausal årsag ikke fastlagt.

Faste startere: N=111, MAE 15.715, bias 1.204, start-bias 0.016. Reserver: N=681, MAE 7.773, start-bias 0.001. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=162, betinget startvarigheds-MAE 4.131, varigheds-bias 4.126. Efter tre fulde starter efterfulgt af én start under 60 min: N=38, MAE 12.842, betinget varigheds-bias -22.771. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 8. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Arsenal

Original MAE 12.366 → 12.031; ny RMSE 21.825; bias -0.659. Startudvælgelse; sværest: rotation_or_short_history (MAE 21.697); 2 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=154, MAE 14.868, bias 0.189, start-bias -0.004. Reserver: N=694, MAE 6.792, start-bias -0.008. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=148, betinget startvarigheds-MAE 2.557, varigheds-bias 2.409. Efter tre fulde starter efterfulgt af én start under 60 min: N=11, MAE 30.624, betinget varigheds-bias -21.565. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 1. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Man City

Original MAE 11.860 → 11.524; ny RMSE 21.516; bias -0.222. Startudvælgelse; sværest: rotation_or_short_history (MAE 22.656); 1 falske nuller; kausal årsag ikke fastlagt.

Faste startere: N=177, MAE 14.513, bias -0.149, start-bias -0.018. Reserver: N=739, MAE 6.214, start-bias -0.006. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=139, betinget startvarigheds-MAE 2.730, varigheds-bias 2.726. Efter tre fulde starter efterfulgt af én start under 60 min: N=20, MAE 7.928, betinget varigheds-bias -21.873. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 4. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

#### Liverpool

Original MAE 10.792 → 10.335; ny RMSE 20.235; bias -0.413. Startudvælgelse; sværest: rotation_or_short_history (MAE 20.871); kausal årsag ikke fastlagt.

Faste startere: N=153, MAE 13.769, bias 0.210, start-bias 0.002. Reserver: N=735, MAE 4.904, start-bias 0.001. Negativ start-bias er underestimering; positiv er overestimering.

Tre tidligere kilde-AVAILABLE 90-minuttersstarter: N=175, betinget startvarigheds-MAE 2.039, varigheds-bias 2.037. Efter tre fulde starter efterfulgt af én start under 60 min: N=7, MAE 32.408, betinget varigheds-bias -24.878. Disse er diagnostiske grupper, ikke en bevist taktisk/skadesårsag eller nye parametre.

Kildeukendte rækker: 4. Verificeret træningsretur: Not Available. Kausal dokumentation for rotation, trænerskifte eller taktisk ændring: Not Available i det anvendte lag.

## Verificerede mekanismer og utestede rettelser

De 35 falske nul-spillechancer fra den tidligere news-/chancekontrol er bevaret og ikke korrigeret med fremtidsviden. De tre DGW-karantænetilfælde har nu supplerende primærkildeunderstøttelse: [Liverpool 18. februar 2025](https://www.liverpoolfc.com/news/aston-villa-v-liverpool-team-news-2) omtaler Jones’ retur fra én kamps karantæne; [Palace 16. april 2025](https://www.cpfc.co.uk/news/match-reports/live-blog-highlights-reaction-newcastle-united-crystal-palace-april-2025/) bekræfter Guéhis retur efter City-karantænen og Nketiahs deltagelse. Begge er efter de relevante GW-deadlines. De bruges derfor kun som retrospektiv fejldokumentation, aldrig som før-deadline input. Dagens HTML-hashes og denne begrænsning gemmes i `corroborating_sources.json`.

**Kampafgrænset karantænerettelse: Not Available som kildecertificeret A/B-arm.** De arkiverede FPL-noter mangler et fuldt, verificeret kamp-/tidsafgrænset udløb. At indsætte de senere artikler i en tidligere deadline ville give leakage. At gætte et år/klokkeslæt eller genindføre en spillers normale startchance efter en formodet udløbsdato er ikke gjort.

**Trænings-/medicinsk returrettelse: Not Available.** Vi har kilde-selection-returer og retrospektive kampdeltagelser, ikke uafhængigt tidsverificerede kliniske clearance- eller træningsdatoer. Der er derfor ingen sådan ekstra effektarm eller opfundet skadevarighed.

## Hvad bør beholdes eller forkastes?

- Behold rolle, midlertidig status og normal startvarighed som adskilte begreber. Behold kildesnapshots, identitets-/deadlinekontroller og falske nul-caseaudit.
- Behold chance-loftet som forskningskandidat: det forbedrer begge forskningsperioder, men FPL-procenter er ikke en kalibreret ubetinget start-/spillechance.
- Bevar retur-s som separat, begrænset hypotese: lille gevinst i 2025/26; usikkert i 2024/25. Ingen automatisk høj startchance ved AVAILABLE.
- Forkast fuld før-skade-tuple-carry som generel returløsning i denne form. Rollevarighed-for-alle forbedrer RMSE, men forværrer MAE og er derfor ikke en dokumenteret samlet erstatning; behold den oprindelige varighedsdel ved MAE-fokus.
- Ingen klubspecifikke boosts, nye fitted parametre eller promotion. Nye prospektive/uberørte data og kampafgrænsede disciplinære kilder mangler stadig.

## Data, kode og reproduktion

`scripts/validate_mm_all_clubs.py` genskaber alle tabeller fra permanente MM-kapsler og Core; `scripts/report_mm_all_clubs.py` genskaber denne rapport og de to klubrapporter. `content_manifest.json` gemmer kode-/inputhashes og eksakte indholdshashes (udpakket gzip). Den dedikerede GitHub-workflow kontrollerer 40 evaluerings-klubsæsoner, 540 klub/model/periode-rækker, 5.400 største-fejl-cases, regressionstests, frosne prediction-bytes og uændret `src`.

Resultatfiler: `club_metrics.csv`, `overall_metrics.csv`, `isolated_ablations.csv`, `group_metrics.csv.gz`, `top_errors.csv.gz`, `report.json.gz`, `summary.json`, `content_manifest.json` i `analysis/results/mm-all-clubs-20261016/`. Gzip-filer udpakkes til almindelig CSV/JSON. Der er ingen private managerdata.

## Bestået CI og eksakt reproduktion

[Workflow 38929682699](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38929682699) er bestået med 46 relevante regressionstests, alle dæknings-/hashkontroller og uændret produktion. Alle syv numeriske outputfilers indhold matcher den uafhængige lokale kørsel byte for byte (gzip udpakkes før sammenligning; ingen numerisk tolerance/afrunding). Kodecommit `297d0f4`, dataresultatcommit `bd1ee8a`; `reproduction.json` gemmer kontrollen.
