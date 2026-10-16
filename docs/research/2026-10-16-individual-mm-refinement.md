# Individuel MM: stabilitet, kalibrering, minutfordelinger og tilbagevenden

Dato: 2026-10-16. Ny branch: `research-individual-mm-refinement-20261016`. Draft PR #9, bygger videre på PR #4/#8 og commit `aca5dba`.

## Omfang og beslutningsprincip

Dette er en faktisk **MM-only, prequential historisk simulation/replay**, ikke blot implementering. Original MM, bedste eksisterende kandidat, A/B/C/D og fem på forhånd definerede kombinationer er kørt på de samme historiske spillerkampe. PM, TS, FPL-point og chips er ikke kørt. Produktions-MM og låste parametre er uændrede; `locked_model_active=false`.

Der vælges ikke automatisk den laveste minut-MAE. Den konservative forskningsscreening kræver en samlet MAE-forbedring og ikke-forværret start-Brier, hvor de parrede 95%-intervaller understøtter det, samt ingen statistisk understøttet forværring af de kritiske rolle-, retur- eller restitutionsgrupper i nogen sæson. Dette er en screen, ikke bevis for ækvivalens/non-inferiority: der er ikke opfundet en accepteret klinisk eller sportslig tolerancemargin. Sparsomme grupper med manglende interval kan ikke erklæres sikre. Intervaller er ikke multiplicitetstilpassede; screeningen er konservativ, og eventuelle fund skal bekræftes på nyt materiale.


Laveste observerede samlede MAE blandt nye kandidater: **B**. Variant, der passerer den beskrevne konservative forskningsscreen: **B**. Ingen variant er produktionsgodkendt.


## 1. Data, identiteter og kronologi

Samme frosne prognoser og kildekontroller fra PR #4/#8 genbruges. Hver referenceprognose matches mod Core på sæson, kamp, spiller, klub, GW, faktisk start og minutter. Alle target-kickoffs ligger efter cutoff. Ny rollehistorik ignorerer ukendt fravær; kendt tidligere optræden er direkte historisk selektionsevidens, men ikke en helbredsattest til næste kamp. Hard-source OUT/SUSPENDED med modstridende faktisk optræden er udeladt af normalrolle- og varighedstræning, men **forbliver i evalueringen**. De fjernes ikke for at forbedre målene.

50.231 spillerkampe har originale/beste MM-prognoser. Evaluering: **39.264 identiske spillerkampe pr. arm**, 2024/25 GW22–38 og 2025/26 GW6–38, alle 20 klubber i hver sæson. GW1–5 har ingen nye opfundne forecasts, men deres kendte kampminutter kan indgå som tidligere råhistorik. Alle nye beslutningsregler er globale, ikke spiller-/klubspecifikke boosts.

**Udvikling:** hyperparametre vælges på 2024/25 GW14–21, med modeller til hvert historisk cutoff udelukkende fittet til labels, der var kendt tidligere. B vælges på start-Brier; A/C/D på samlet minut-MAE. Kun rigtige ikke-nul kandidater søges i hver familie; den uændrede reference bevares som separat mulighed og kan vinde den afsluttende beslutning. Kombinationer er prædefinerede, ikke en efterfølgende klub-/spillergrid.

**Evaluering:** derefter GW22–38 og 2025/26 GW6–38. Kalibrerings-/residualmodeller refittes ved hver origin på tidligere kendte labels. 2024/25-resultater må indgå i senere 2025/26-træning, fordi de da er fortid. Baseline og perioder har været genbrugt i forskning; dette er **ikke uafhængige holdouts eller en ny uberørt valideringssæson**.

Outcome-tilgængelighed arver kickoff + fire timer i 2024/25 og + tre timer i 2025/26, ikke verificerede faktiske publiceringstidspunkter. Alle kendt-før-kontroller er strenge `< cutoff`; deadline-certificering er fortsat blokeret af kildeklokkernes usikkerhed.

Belastning/hvile følger spilleridentiteten på tværs af verificerede PL-klubskifter. Normalrolle og personlige varighedsprofiler forbliver klubspecifikke. Restitution er tid siden seneste kendte PL-optræden frem til cutoff, ikke en verificeret total restitutionstid ved kickoff. Cup-/Europaminutter mangler i denne kontrollerede MM-test og erstattes ikke med nul aktivitet. Fravær og langt ophold mellem kampe betegnes ikke automatisk skade.

| Træningsorigins | Alle target-rækker | Laveste tidligere labelantal | Højeste tidligere labelantal | Alle label-klokker før cutoff |
| --- | --- | --- | --- | --- |
| 66 | 50231 | 0 | 49390 | True |


## 2. Matematiske ændringer og isolation

Alle arme bruger den eksisterende identitet

$$
E[M]=p\,s+(1-p)q\,c,
$$

hvor p er startchance, s betingede starterminutter, q indskiftningschance givet ingen start og c minutter givet indskiftning. Den eksisterende source-cap og exact-11-projektion genbruges uændret: én forventet startende målmand og ti øvrige. Dette er **marginale startchancer**, ikke en ny uafhængig XI-sampler eller en påstand om simuleret lovlig joint-XI-fordeling.

### A: stabil normalrolle

Ud fra kun tidligere anvendelig rollehistorik beregnes

$$
p_{stable}=\frac{8p_{normal}+\sum_i w_i y_i}{8+\sum_i w_i},\quad
w_i=2^{-\Delta t_i/180},\quad
p_A=(1-a)p_{best}+a p_{stable}.
$$

Normalpriorn genbruges fra den eksisterende bevarede rolle, ellers den eksisterende rolle-MM. Midlertidigt fravær uden gyldig rolleobservation tæller ikke som en serie taktiske bænkninger. Én atypisk kamp påvirker en længere historik gradvist. Exponering 8 og halvering 180 dage er genbrugte forskningspriors; a vælges blandt 0,25/0,5/1 på udviklingsdata. Aktuel tilgængelighed håndteres separat af caps. A ændrer startsignalet, ikke direkte starter-/bænkvarighederne.

Et negativt resultat for A's faste ekstra blend betyder ikke, at historiske roller er værdiløse: B bruger også normal-/stabil rolle som input, men lærer vægtningen fra tidligere startudfald.

### B: startkalibrering

En regulariseret logistisk kalibrering bruger eksisterende logit(p)/logit(q), normal/stabil rolle, tidligere start-/indskiftningshistorik, position, hvile, registrerede 7/14-døgnsminutter og manglende-data-indikatorer. Hver model ser kun tidligere kendte outcomes og aldrig den aktuelle start eller aktuelle minutter. Numeriske variable standardiseres på træningshistorikken. Regulariseringsstyrke vælges blandt 0,1/1/10. Minimum 200 tidligere interiørprognoser og begge klasser kræves; ellers bruges den uændrede reference, ikke syntetiske træningsrækker. Source-hard-zero/caps bevares efter projektion.

### C: individuel varighedsfordeling

Der startes ikke en ny global MM fra bunden. Ridge lærer **residualkorrektioner til de eksisterende s/c**, separat blandt faktiske startere og faktiske indskiftninger, kun på tidligere pålidelige observationer. Samme prior-only rolle-/belastningsfeatures anvendes. Alpha vælges blandt 1/10/100; mindst 100 startere/50 indskiftninger kræves, ellers beholdes baseline.

En positionstilpasset empirisk residualfordeling omkring den nye betingede middelværdi kombineres med spillerens decayed personlige minutfordeling:

$$
P_C(M=m\mid state)=\frac{5P_{residual,position}(m)+h_{player}(m)}{5+\sum_m h_{player}(m)}.
$$

Exponering 5 genbruges fra eksisterende duration-prior. Hver startfordeling ligger på 0–90 minutter; indskiftningsfordelingen på 1–90, betinget på en positiv optræden. Fraktionel bin-deponering bevarer kontinuitet mellem minutbin. Middelværdier fra disse fordelinger bliver C's s/c; p og q ændres ikke. Spredning, 10/90-percentiler og P(90) / P(1–15) gemmes. Residualformen er estimeret i træningshistorikken, ikke en garanti for kalibrerede predictive intervals; out-of-origin-kalibreringen måles nedenfor.

Registrerede starterminutter beskriver stint-varighed, men ikke verificeret årsag til en udskiftning. Core mangler verificerede sub-on/off-tidsstempler. Der er derfor **ingen opfundet udskiftningshazard, føringsstilling, taktisk eller medicinsk exitårsag** i C.

### D: kildeafgrænset tilbagevenden

Sidste tidligere eksplicit AVAILABLE-rolle i samme klub gemmes før dokumenteret medicinsk OUT eller SUSPENDED. D aktiveres kun ved ny eksplicit AVAILABLE/RETURNED_AVAILABLE, aldrig fordi spilleren faktisk ender med at spille den aktuelle kamp. En global vægt a/(1+n) trækker p og s mod før-fraværsrollen, hvor n er antal tidligere afsluttede, allerede kendte kampe siden den nye selection-return-origin; de første tre kendte kamptrin undersøges. Vægten a vælges blandt 0,25/0,5/1 på udvikling. Ny OUT eller klubskifte nulstiller episoden.

Det er en testet probabilistisk rolleprior, ikke en erklæring om fuld kampform eller klinisk helbredelse. Ved DGW kan to fremtidige kampe ved samme cutoff dele n=0: første kamps endnu ukendte spilletid bruges ikke til den anden. Grupperne return_1/2/3 svarer til 0/1/2 **kendte** tidligere kampe siden return-origin, ikke en fremtidsinformeret faktisk optrædenstæller.

D er et tillæg til den bedste eksisterende kandidat. Dennes allerede etablerede bevaring af startervarighed ved en kildeafgrænset retur fjernes ikke, selv om det nye udvidede p/s-carry ikke giver en sikker ekstra gevinst.

### Kombinationer og begrænsninger

A+B, A+C, B+C, B+D og A+B+C+D er kørt. B er fittet som kalibrering af baseline; i A+B anvendes B's faste log-odds-korrektion oven på A, ikke en skjult refit på evalueringsdata. Alle startsignaler caps/projekteres. Ændret p kan nødvendiggøre ændret q for at overholde den samme source appearance-cap. Ingen ny q-model, importance-score, klinisk regel eller optimering af FPL-point er indført.


Valgte udviklingsparametre: `{"A": 0.25, "B": 10.0, "C": [100.0, 1.0], "D": 1.0}`. Alle forsøgsværdier og udviklingsmål findes i `development_selection.csv`.

## 3. Samlede faktiske før/efter-resultater


| Arm | Minut-MAE | RMSE | Start-Brier | Start-log-loss¹ | Minut-bias | Start-ECE10 | Startervarighed MAE | Cameovarighed MAE | False-zero | ΔMAE vs bedste reference | 95% lav | 95% høj |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| best_existing | 10.521392 | 20.416725 | 0.070115 | 0.231354 | -0.377657 | 0.008207 | 8.064556 | 11.348578 | 35 | 0.000000 | 0.000000 | 0.000000 |
| original | 11.240711 | 21.115962 | 0.073445 | 0.241262 | -0.082509 | 0.007752 | 8.151007 | 11.348578 | 0 | 0.719320 | 0.604448 | 0.888724 |
| A | 10.676534 | 20.123737 | 0.069301 | 0.227795 | -0.384822 | 0.009394 | 8.064556 | 11.348578 | 35 | 0.155143 | 0.111298 | 0.195591 |
| B | 10.408358 | 20.172026 | 0.068827 | 0.226125 | -0.282791 | 0.004843 | 8.064556 | 11.348578 | 35 | -0.113034 | -0.148345 | -0.074534 |
| C | 10.809961 | 20.220984 | 0.070115 | 0.231354 | -0.503115 | 0.008207 | 7.873829 | 10.899898 | 35 | 0.288569 | 0.244206 | 0.336964 |
| D | 10.520169 | 20.310755 | 0.069947 | 0.230472 | -0.301471 | 0.007697 | 7.962419 | 11.348578 | 35 | -0.001223 | -0.045624 | 0.052844 |
| A_B | 10.757101 | 20.179456 | 0.070448 | 0.230203 | -0.285328 | 0.008104 | 8.064556 | 11.348578 | 35 | 0.235710 | 0.157023 | 0.324112 |
| A_C | 11.007898 | 20.034702 | 0.069301 | 0.227795 | -0.453032 | 0.009394 | 7.873829 | 10.899898 | 35 | 0.486507 | 0.409115 | 0.563980 |
| B_C | 10.696578 | 19.980957 | 0.068827 | 0.226125 | -0.434120 | 0.004843 | 7.873829 | 10.899898 | 35 | 0.175186 | 0.125989 | 0.227014 |
| B_D | 10.441749 | 20.173871 | 0.069335 | 0.227393 | -0.217537 | 0.004203 | 7.962419 | 11.348578 | 35 | -0.079643 | -0.139491 | -0.009072 |
| A_B_C_D | 11.124192 | 20.220899 | 0.071243 | 0.232253 | -0.328492 | 0.006471 | 7.848917 | 10.899898 | 35 | 0.602800 | 0.502514 | 0.712217 |


¹ Viste log-loss bruger eksplicit numerisk 1e−12-clip til scoring. Modstridende hard-zero/hard-one-prognoser har **uendelig teoretisk log-loss**; clippet gør ikke prognosernes sikkerhed korrekt. Globale start-bias tæt på nul følger delvist af præcis 11 forventede startere og er ikke i sig selv bevis for individuel kalibrering.

Alle parrede intervaller bruger 1.000 cirkulære fire-GW-bloktræk med bevaret tom kalenderuge. Ved pooling resamples sæsonerne uafhængigt. Klub-/gruppeintervaller med færre end otte befolkede GWs er Not Available. Små effektive blokantal, datakildeusikkerhed, hyperparametervalg og multiplicitet er ikke fuldt indregnet.

## 4. Sæsoner og kritiske grupper


Direkte kombinationsablationer, så effekter ikke tilskrives en anden komponent:

| Kandidat vs reference | ΔMAE | 95% lav | 95% høj | ΔBrier |
| --- | --- | --- | --- | --- |
| B_D vs B | 0.033391 | -0.002279 | 0.076744 | 0.000508 |
| A_B vs B | 0.348743 | 0.290721 | 0.402562 | 0.001621 |
| B_C vs B | 0.288220 | 0.245488 | 0.334390 | 0.000000 |
| A_C vs A | 0.331364 | 0.287689 | 0.381400 | 0.000000 |

| Sæson | Arm | Minut-MAE | RMSE | Start-Brier | Bias |
| --- | --- | --- | --- | --- | --- |
| 2024-25 | best_existing | 11.156276 | 21.048002 | 0.073653 | -0.446375 |
| 2024-25 | original | 12.653130 | 22.304667 | 0.081052 | -0.103681 |
| 2024-25 | A | 11.266585 | 20.701580 | 0.072507 | -0.452078 |
| 2024-25 | B | 10.948646 | 20.765577 | 0.072307 | -0.332369 |
| 2024-25 | C | 11.393231 | 20.798989 | 0.073653 | -0.489432 |
| 2024-25 | D | 11.171814 | 20.980513 | 0.073744 | -0.352526 |
| 2024-25 | A_B | 11.298592 | 20.779770 | 0.074059 | -0.332794 |
| 2024-25 | A_C | 11.551476 | 20.557889 | 0.072507 | -0.433071 |
| 2024-25 | B_C | 11.184639 | 20.521818 | 0.072307 | -0.413918 |
| 2024-25 | B_D | 11.014593 | 20.834136 | 0.073223 | -0.251065 |
| 2024-25 | A_B_C_D | 11.652811 | 20.839457 | 0.075170 | -0.291294 |
| 2025-26 | best_existing | 10.203330 | 20.093016 | 0.068343 | -0.343230 |
| 2025-26 | original | 10.533125 | 20.494545 | 0.069635 | -0.071903 |
| 2025-26 | A | 10.380934 | 19.827922 | 0.067695 | -0.351128 |
| 2025-26 | B | 10.137688 | 19.868006 | 0.067084 | -0.257953 |
| 2025-26 | C | 10.517757 | 19.925115 | 0.068343 | -0.509970 |
| 2025-26 | D | 10.193711 | 19.966778 | 0.068045 | -0.275894 |
| 2025-26 | A_B | 10.485828 | 19.871897 | 0.068639 | -0.261549 |
| 2025-26 | A_C | 10.735580 | 19.767393 | 0.067695 | -0.463033 |
| 2025-26 | B_C | 10.452071 | 19.704417 | 0.067084 | -0.444240 |
| 2025-26 | B_D | 10.154769 | 19.834833 | 0.067387 | -0.200740 |
| 2025-26 | A_B_C_D | 10.859367 | 19.903791 | 0.069276 | -0.347128 |


Alle gruppe-/klub-/armresultater er i `group_metrics.csv.gz`. Kritiske udsnit:

| Sæson | Gruppe | Arm | N | MAE | Brier | Bias | ΔMAE | 95% lav | 95% høj |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | regular | best_existing | 1665 | 14.150461 | 0.076182 | 0.448504 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | rotation | best_existing | 3473 | 22.114824 | 0.156311 | -0.740755 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | reserve | best_existing | 7967 | 5.753445 | 0.037092 | -0.505066 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | source_medical_return | best_existing | 174 | 22.301404 | 0.180456 | -13.599371 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | documented_return_1 | best_existing | 166 | 25.836605 | 0.213746 | -16.733547 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | documented_return_2 | best_existing | 150 | 23.382050 | 0.146086 | -13.525424 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | documented_return_3 | best_existing | 157 | 24.806787 | 0.170197 | -9.419102 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | documented_suspension_return | best_existing | 77 | 25.740286 | 0.185440 | -12.399649 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | short_rest | best_existing | 611 | 20.660214 | 0.141710 | -0.858671 | 0.000000 | Not Available | Not Available |
| 2024-25 | long_rest | best_existing | 5225 | 11.792553 | 0.076570 | -1.564129 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | prior_three_full_starts | best_existing | 2110 | 14.472330 | 0.084939 | 0.466597 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | single_short_after_three_full | best_existing | 196 | 19.488618 | 0.129834 | -8.378795 | 0.000000 | 0.000000 | 0.000000 |
| 2024-25 | regular | A | 1665 | 14.294755 | 0.076378 | 0.085774 | 0.144294 | 0.082856 | 0.210540 |
| 2024-25 | rotation | A | 3473 | 22.332217 | 0.153852 | -1.018276 | 0.217392 | 0.132738 | 0.291042 |
| 2024-25 | reserve | A | 7967 | 5.809971 | 0.036237 | -0.317663 | 0.056526 | 0.018563 | 0.091375 |
| 2024-25 | source_medical_return | A | 174 | 21.485845 | 0.156922 | -7.870362 | -0.815559 | -2.093101 | 0.454265 |
| 2024-25 | documented_return_1 | A | 166 | 24.560340 | 0.184379 | -10.312894 | -1.276265 | -2.602129 | 0.134743 |
| 2024-25 | documented_return_2 | A | 150 | 22.946796 | 0.137146 | -11.267862 | -0.435253 | -0.751424 | -0.193252 |
| 2024-25 | documented_return_3 | A | 157 | 24.775155 | 0.164267 | -9.693185 | -0.031632 | -0.821441 | 0.779693 |
| 2024-25 | documented_suspension_return | A | 77 | 25.271159 | 0.172496 | -10.801629 | -0.469127 | -1.817303 | 0.415320 |
| 2024-25 | short_rest | A | 611 | 20.755827 | 0.139937 | -1.846549 | 0.095614 | Not Available | Not Available |
| 2024-25 | long_rest | A | 5225 | 12.020276 | 0.074370 | -0.705714 | 0.227723 | 0.111390 | 0.341467 |
| 2024-25 | prior_three_full_starts | A | 2110 | 14.925671 | 0.082154 | 0.409626 | 0.453341 | 0.341282 | 0.570885 |
| 2024-25 | single_short_after_three_full | A | 196 | 19.580444 | 0.130001 | -6.439418 | 0.091826 | -0.396229 | 0.582022 |
| 2024-25 | regular | B | 1665 | 13.695206 | 0.075906 | 1.126257 | -0.455255 | -0.533168 | -0.363140 |
| 2024-25 | rotation | B | 3473 | 21.866295 | 0.153206 | -0.368259 | -0.248529 | -0.371755 | -0.132863 |
| 2024-25 | reserve | B | 7967 | 5.615393 | 0.036288 | -0.621557 | -0.138052 | -0.184215 | -0.092698 |
| 2024-25 | source_medical_return | B | 174 | 21.062900 | 0.157809 | -9.523257 | -1.238504 | -2.424143 | -0.071042 |
| 2024-25 | documented_return_1 | B | 166 | 23.851038 | 0.183815 | -11.539153 | -1.985567 | -2.988074 | -0.905590 |
| 2024-25 | documented_return_2 | B | 150 | 21.076523 | 0.132416 | -7.052521 | -2.305527 | -3.208783 | -1.555071 |
| 2024-25 | documented_return_3 | B | 157 | 24.323241 | 0.165821 | -8.721651 | -0.483546 | -1.061599 | 0.123871 |
| 2024-25 | documented_suspension_return | B | 77 | 24.522359 | 0.171029 | -9.530795 | -1.217927 | -1.867993 | -0.476454 |
| 2024-25 | short_rest | B | 611 | 20.207989 | 0.141749 | -1.205313 | -0.452224 | Not Available | Not Available |
| 2024-25 | long_rest | B | 5225 | 11.704076 | 0.074410 | -0.884739 | -0.088477 | -0.253863 | 0.070145 |
| 2024-25 | prior_three_full_starts | B | 2110 | 14.282305 | 0.082093 | 1.335741 | -0.190025 | -0.307939 | -0.068090 |
| 2024-25 | single_short_after_three_full | B | 196 | 19.044739 | 0.128846 | -8.290948 | -0.443879 | -0.835813 | -0.097528 |
| 2024-25 | regular | C | 1665 | 14.799689 | 0.076182 | -0.453740 | 0.649228 | 0.505831 | 0.803508 |
| 2024-25 | rotation | C | 3473 | 22.648155 | 0.156311 | -0.848246 | 0.533331 | 0.338637 | 0.702725 |
| 2024-25 | reserve | C | 7967 | 5.775043 | 0.037092 | -0.340476 | 0.021598 | -0.008814 | 0.054343 |
| 2024-25 | source_medical_return | C | 174 | 22.024874 | 0.180456 | -13.748646 | -0.276529 | -0.614007 | 0.076558 |
| 2024-25 | documented_return_1 | C | 166 | 25.189143 | 0.213746 | -16.606734 | -0.647463 | -1.012368 | -0.176027 |
| 2024-25 | documented_return_2 | C | 150 | 23.256377 | 0.146086 | -11.837325 | -0.125673 | -1.264500 | 1.134598 |
| 2024-25 | documented_return_3 | C | 157 | 25.279234 | 0.170197 | -8.984296 | 0.472447 | -0.527317 | 1.470467 |
| 2024-25 | documented_suspension_return | C | 77 | 25.416674 | 0.185440 | -11.639917 | -0.323612 | -2.728011 | 1.355896 |
| 2024-25 | short_rest | C | 611 | 20.659965 | 0.141710 | -1.006054 | -0.000249 | Not Available | Not Available |
| 2024-25 | long_rest | C | 5225 | 11.959100 | 0.076570 | -1.448166 | 0.166547 | 0.110017 | 0.221959 |
| 2024-25 | prior_three_full_starts | C | 2110 | 15.437831 | 0.084939 | -1.429298 | 0.965502 | 0.897486 | 1.041001 |
| 2024-25 | single_short_after_three_full | C | 196 | 18.822913 | 0.129834 | -2.074514 | -0.665705 | -2.441731 | 1.349471 |
| 2024-25 | regular | D | 1665 | 14.423908 | 0.076253 | -0.126060 | 0.273447 | 0.143957 | 0.388898 |
| 2024-25 | rotation | D | 3473 | 22.065718 | 0.155707 | -0.953163 | -0.049106 | -0.266326 | 0.123212 |
| 2024-25 | reserve | D | 7967 | 5.743264 | 0.037490 | -0.138023 | -0.010182 | -0.086234 | 0.063753 |
| 2024-25 | source_medical_return | D | 174 | 24.480993 | 0.207745 | 9.379797 | 2.179589 | -0.922005 | 5.925148 |
| 2024-25 | documented_return_1 | D | 166 | 27.261348 | 0.248449 | 13.065902 | 1.424743 | -3.010035 | 6.487871 |
| 2024-25 | documented_return_2 | D | 150 | 22.305847 | 0.135444 | -5.514306 | -1.076203 | -2.505081 | 0.444232 |
| 2024-25 | documented_return_3 | D | 157 | 24.415423 | 0.159420 | -7.066581 | -0.391364 | -1.838913 | 0.851812 |
| 2024-25 | documented_suspension_return | D | 77 | 23.657740 | 0.197022 | 0.700340 | -2.082547 | -8.515005 | 3.053718 |
| 2024-25 | short_rest | D | 611 | 20.424233 | 0.138918 | -1.003178 | -0.235981 | Not Available | Not Available |
| 2024-25 | long_rest | D | 5225 | 11.837694 | 0.077350 | -1.076537 | 0.045141 | -0.075661 | 0.189348 |
| 2024-25 | prior_three_full_starts | D | 2110 | 14.674927 | 0.085538 | 0.589984 | 0.202597 | -0.096158 | 0.532581 |
| 2024-25 | single_short_after_three_full | D | 196 | 20.870711 | 0.145627 | -3.825363 | 1.382093 | 0.327605 | 2.638263 |
| 2025-26 | regular | best_existing | 3142 | 13.369206 | 0.076502 | 0.461264 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | rotation | best_existing | 6771 | 20.801250 | 0.146656 | -0.600715 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | reserve | best_existing | 16246 | 5.174050 | 0.034126 | -0.391506 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | source_medical_return | best_existing | 271 | 21.794091 | 0.176521 | -15.474029 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | documented_return_1 | best_existing | 260 | 26.961295 | 0.205274 | -20.667616 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | documented_return_2 | best_existing | 231 | 22.556378 | 0.153130 | -10.268955 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | documented_return_3 | best_existing | 229 | 18.930844 | 0.123619 | -4.632099 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | documented_suspension_return | best_existing | 155 | 27.732427 | 0.183281 | -19.518527 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | short_rest | best_existing | 986 | 20.583878 | 0.148403 | 1.817052 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | long_rest | best_existing | 8046 | 12.870829 | 0.086635 | -2.185401 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | prior_three_full_starts | best_existing | 4059 | 14.499566 | 0.085999 | 0.770464 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | single_short_after_three_full | best_existing | 356 | 19.553270 | 0.140312 | -8.301483 | 0.000000 | 0.000000 | 0.000000 |
| 2025-26 | regular | A | 3142 | 13.449521 | 0.076899 | 0.362482 | 0.080315 | -0.089309 | 0.269943 |
| 2025-26 | rotation | A | 6771 | 21.316733 | 0.145593 | -0.662588 | 0.515483 | 0.383956 | 0.627084 |
| 2025-26 | reserve | A | 16246 | 5.229648 | 0.033448 | -0.359331 | 0.055598 | 0.015299 | 0.093237 |
| 2025-26 | source_medical_return | A | 271 | 20.343175 | 0.153488 | -10.840044 | -1.450916 | -2.504845 | -0.435259 |
| 2025-26 | documented_return_1 | A | 260 | 24.824660 | 0.167871 | -14.826528 | -2.136635 | -3.151908 | -1.014903 |
| 2025-26 | documented_return_2 | A | 231 | 23.032617 | 0.147988 | -9.582727 | 0.476238 | 0.069403 | 0.952259 |
| 2025-26 | documented_return_3 | A | 229 | 19.464384 | 0.123479 | -5.331586 | 0.533540 | 0.177672 | 0.869296 |
| 2025-26 | documented_suspension_return | A | 155 | 27.021517 | 0.155398 | -17.952862 | -0.710910 | -1.172014 | -0.238691 |
| 2025-26 | short_rest | A | 986 | 20.557267 | 0.146337 | 0.730732 | -0.026611 | -0.223986 | 0.164053 |
| 2025-26 | long_rest | A | 8046 | 13.192335 | 0.084079 | -1.082816 | 0.321506 | 0.197311 | 0.464985 |
| 2025-26 | prior_three_full_starts | A | 4059 | 15.109220 | 0.084713 | 0.997716 | 0.609654 | 0.394747 | 0.801939 |
| 2025-26 | single_short_after_three_full | A | 356 | 19.613236 | 0.135689 | -6.327351 | 0.059965 | -0.241860 | 0.343885 |
| 2025-26 | regular | B | 3142 | 13.041547 | 0.076641 | 1.177924 | -0.327659 | -0.447942 | -0.201721 |
| 2025-26 | rotation | B | 6771 | 20.875608 | 0.143885 | -0.221871 | 0.074358 | -0.063035 | 0.198266 |
| 2025-26 | reserve | B | 16246 | 5.100732 | 0.033226 | -0.550693 | -0.073318 | -0.120506 | -0.024191 |
| 2025-26 | source_medical_return | B | 271 | 20.517510 | 0.157457 | -12.663688 | -1.276580 | -1.890143 | -0.646077 |
| 2025-26 | documented_return_1 | B | 260 | 24.675609 | 0.169574 | -16.150873 | -2.285686 | -3.149655 | -1.365783 |
| 2025-26 | documented_return_2 | B | 231 | 22.135884 | 0.150830 | -6.751833 | -0.420494 | -1.418537 | 0.545686 |
| 2025-26 | documented_return_3 | B | 229 | 18.483539 | 0.117400 | -4.819493 | -0.447304 | -1.032512 | 0.010105 |
| 2025-26 | documented_suspension_return | B | 155 | 25.607301 | 0.146965 | -15.930585 | -2.125126 | -2.735192 | -1.395714 |
| 2025-26 | short_rest | B | 986 | 20.343828 | 0.148529 | 1.363685 | -0.240050 | -0.343185 | -0.079691 |
| 2025-26 | long_rest | B | 8046 | 12.937897 | 0.083556 | -1.311089 | 0.067068 | -0.064173 | 0.225962 |
| 2025-26 | prior_three_full_starts | B | 4059 | 14.600255 | 0.083966 | 1.662664 | 0.100689 | -0.065245 | 0.285630 |
| 2025-26 | single_short_after_three_full | B | 356 | 19.369840 | 0.133119 | -7.793351 | -0.183430 | -0.515674 | 0.131431 |
| 2025-26 | regular | C | 3142 | 14.277568 | 0.076502 | -0.524462 | 0.908362 | 0.699374 | 1.148128 |
| 2025-26 | rotation | C | 6771 | 21.455534 | 0.146656 | -0.996367 | 0.654284 | 0.477328 | 0.828436 |
| 2025-26 | reserve | C | 16246 | 5.231963 | 0.034126 | -0.304447 | 0.057914 | 0.029437 | 0.085434 |
| 2025-26 | source_medical_return | C | 271 | 22.262389 | 0.176521 | -15.612167 | 0.468298 | 0.192761 | 0.760749 |
| 2025-26 | documented_return_1 | C | 260 | 26.961257 | 0.205274 | -20.725461 | -0.000038 | -0.391291 | 0.376735 |
| 2025-26 | documented_return_2 | C | 231 | 22.224549 | 0.153130 | -9.601119 | -0.331830 | -1.427394 | 0.793952 |
| 2025-26 | documented_return_3 | C | 229 | 19.823202 | 0.123619 | -5.281968 | 0.892358 | 0.311405 | 1.467920 |
| 2025-26 | documented_suspension_return | C | 155 | 27.761104 | 0.183281 | -19.683066 | 0.028676 | -1.273552 | 0.966154 |
| 2025-26 | short_rest | C | 986 | 21.408543 | 0.148403 | 0.936048 | 0.824665 | 0.535284 | 1.109854 |
| 2025-26 | long_rest | C | 8046 | 13.081456 | 0.086635 | -2.104453 | 0.210627 | 0.105474 | 0.299600 |
| 2025-26 | prior_three_full_starts | C | 4059 | 15.619901 | 0.085999 | -1.350170 | 1.120335 | 1.035078 | 1.201878 |
| 2025-26 | single_short_after_three_full | C | 356 | 19.691959 | 0.140312 | -2.128010 | 0.138688 | -0.916197 | 1.111318 |
| 2025-26 | regular | D | 3142 | 13.571947 | 0.076189 | -0.009467 | 0.202741 | 0.125458 | 0.287300 |
| 2025-26 | rotation | D | 6771 | 20.689073 | 0.145305 | -0.509305 | -0.112178 | -0.219411 | -0.015249 |
| 2025-26 | reserve | D | 16246 | 5.166103 | 0.034270 | -0.230141 | -0.007947 | -0.066085 | 0.053163 |
| 2025-26 | source_medical_return | D | 271 | 23.266515 | 0.205313 | 3.837866 | 1.472424 | -2.138274 | 5.921488 |
| 2025-26 | documented_return_1 | D | 260 | 23.609137 | 0.192859 | 7.765506 | -3.352158 | -7.537088 | 1.977852 |
| 2025-26 | documented_return_2 | D | 231 | 22.373738 | 0.149278 | -5.458131 | -0.182640 | -1.435989 | 1.351766 |
| 2025-26 | documented_return_3 | D | 229 | 19.820094 | 0.123532 | -3.563238 | 0.889250 | -0.044388 | 2.105957 |
| 2025-26 | documented_suspension_return | D | 155 | 19.814693 | 0.113660 | -5.289046 | -7.917735 | -10.261765 | -6.408198 |
| 2025-26 | short_rest | D | 986 | 20.685406 | 0.148061 | 1.387869 | 0.101528 | -0.204842 | 0.292936 |
| 2025-26 | long_rest | D | 8046 | 12.731032 | 0.085518 | -1.598375 | -0.139797 | -0.286392 | 0.039447 |
| 2025-26 | prior_three_full_starts | D | 4059 | 14.628872 | 0.085662 | 0.616187 | 0.129306 | 0.007168 | 0.229400 |
| 2025-26 | single_short_after_three_full | D | 356 | 17.987589 | 0.125113 | -6.097831 | -1.565681 | -2.873231 | -0.356022 |


Regular/rotation/reserve-grupper defineres på tidligere Core-kampe, ikke aktuel opstilling. De bruges til evaluering, ikke til manuelle spillerboosts. Separat kildeafgrænset rollehistorik undgår at bruge ukendt fravær som taktisk rolleændring. Lange hvileperioder kan også være reservestatus eller manglende andre turneringer; grupperne må ikke alene kaldes restitutionsårsager.

## 5. Alle 40 klub-sæsoner

Tabellen viser den bedst målte nye samlede MAE-kandidat (ikke automatisk produktionsanbefalet) mod samme eksisterende reference. `club_metrics.csv` indeholder alle 11 arme pr. klub, alle metrics og parrede intervaller. Observeret MAE-stigning vises også, ikke kun gevinster.

| Sæson | Klub | Reference MAE | B MAE | Forskel | 95% lav | 95% høj | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | Man City | 16.754505 | 16.637559 | -0.116946 | -0.462187 | 0.192117 | 0.113023 |
| 2024-25 | Ipswich | 15.022570 | 14.832278 | -0.190292 | -0.508699 | 0.173422 | 0.102910 |
| 2024-25 | West Ham | 14.934611 | 14.710523 | -0.224088 | -0.436178 | 0.027229 | 0.099387 |
| 2024-25 | Man Utd | 13.777052 | 13.418600 | -0.358452 | -0.505784 | -0.194645 | 0.100576 |
| 2024-25 | Spurs | 13.406895 | 13.197377 | -0.209519 | -0.434602 | 0.003499 | 0.103260 |
| 2024-25 | Leicester | 12.163543 | 12.263495 | 0.099952 | -0.174847 | 0.368853 | 0.068868 |
| 2024-25 | Liverpool | 12.737472 | 12.116220 | -0.621252 | -0.807963 | -0.485329 | 0.085204 |
| 2024-25 | Fulham | 12.641919 | 12.051264 | -0.590655 | -0.786924 | -0.418671 | 0.084280 |
| 2024-25 | Southampton | 11.977146 | 11.965295 | -0.011851 | -0.212017 | 0.206253 | 0.081773 |
| 2024-25 | Aston Villa | 12.147908 | 11.944117 | -0.203791 | -0.566072 | 0.136483 | 0.083363 |
| 2024-25 | Arsenal | 11.170673 | 11.113791 | -0.056882 | -0.267071 | 0.154937 | 0.079859 |
| 2024-25 | Everton | 9.412867 | 9.607178 | 0.194311 | 0.019684 | 0.378063 | 0.060160 |
| 2024-25 | Chelsea | 9.415525 | 9.247330 | -0.168195 | -0.382593 | 0.076479 | 0.062328 |
| 2024-25 | Newcastle | 9.244533 | 9.091421 | -0.153112 | -0.459654 | 0.132416 | 0.043339 |
| 2024-25 | Nott'm Forest | 9.477088 | 8.979348 | -0.497740 | -0.672792 | -0.303763 | 0.049444 |
| 2024-25 | Crystal Palace | 9.253073 | 8.896174 | -0.356899 | -0.551051 | -0.131365 | 0.054536 |
| 2024-25 | Brighton | 8.721459 | 8.675618 | -0.045841 | -0.211589 | 0.117607 | 0.057833 |
| 2024-25 | Wolves | 8.117235 | 7.969228 | -0.148007 | -0.330156 | 0.071184 | 0.043917 |
| 2024-25 | Bournemouth | 7.232870 | 6.990065 | -0.242805 | -0.395615 | -0.073072 | 0.044386 |
| 2024-25 | Brentford | 7.024508 | 6.621588 | -0.402919 | -0.577897 | -0.247147 | 0.031359 |
| 2025-26 | Chelsea | 14.012438 | 13.840616 | -0.171823 | -0.308435 | -0.019243 | 0.098858 |
| 2025-26 | Fulham | 13.061602 | 12.935349 | -0.126253 | -0.302265 | 0.071069 | 0.085191 |
| 2025-26 | Newcastle | 12.057975 | 12.235110 | 0.177135 | 0.014841 | 0.340161 | 0.084950 |
| 2025-26 | Arsenal | 12.031301 | 11.800237 | -0.231064 | -0.347069 | -0.131285 | 0.085339 |
| 2025-26 | Wolves | 11.459118 | 11.692884 | 0.233766 | 0.020025 | 0.454888 | 0.083114 |
| 2025-26 | Man City | 11.524087 | 11.643786 | 0.119699 | -0.000173 | 0.243418 | 0.074899 |
| 2025-26 | Aston Villa | 11.225350 | 11.008769 | -0.216580 | -0.377372 | -0.049535 | 0.076247 |
| 2025-26 | Nott'm Forest | 10.725617 | 10.790627 | 0.065011 | -0.143547 | 0.268009 | 0.068577 |
| 2025-26 | Leeds | 10.459626 | 10.540812 | 0.081186 | -0.051589 | 0.214505 | 0.062246 |
| 2025-26 | Spurs | 10.281848 | 10.263783 | -0.018065 | -0.172754 | 0.140172 | 0.073518 |
| 2025-26 | Liverpool | 10.335087 | 10.014507 | -0.320580 | -0.486247 | -0.139156 | 0.064808 |
| 2025-26 | West Ham | 9.910380 | 10.009776 | 0.099396 | -0.017203 | 0.222589 | 0.059591 |
| 2025-26 | Burnley | 9.787110 | 9.800308 | 0.013198 | -0.157022 | 0.178703 | 0.064831 |
| 2025-26 | Man Utd | 9.294692 | 9.176968 | -0.117724 | -0.211406 | -0.017164 | 0.056957 |
| 2025-26 | Crystal Palace | 9.377725 | 9.054665 | -0.323060 | -0.441875 | -0.221281 | 0.059516 |
| 2025-26 | Brighton | 9.025065 | 9.003888 | -0.021177 | -0.154298 | 0.086390 | 0.056908 |
| 2025-26 | Brentford | 8.721664 | 8.649272 | -0.072392 | -0.238269 | 0.087726 | 0.055682 |
| 2025-26 | Everton | 8.471426 | 8.193659 | -0.277767 | -0.507570 | -0.076523 | 0.050361 |
| 2025-26 | Bournemouth | 7.301599 | 7.246905 | -0.054693 | -0.193116 | 0.088281 | 0.050759 |
| 2025-26 | Sunderland | 7.176161 | 7.026234 | -0.149926 | -0.255971 | -0.032161 | 0.043318 |


Forskningsscreening (ingen produktionsgodkendelse):

| Arm | MAE | ΔMAE | 95% høj | ΔBrier | Brier 95% høj | Kritiske forværringsudsnit | Passerer konservativ screen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | 10.408358 | -0.113034 | -0.074534 | -0.001288 | -0.000873 | 0 | True |
| B_D | 10.441749 | -0.079643 | -0.009072 | -0.000781 | -0.000079 | 0 | True |
| D | 10.520169 | -0.001223 | 0.052844 | -0.000168 | 0.000433 | 2 | False |
| A | 10.676534 | 0.155143 | 0.195591 | -0.000815 | -0.000428 | 9 | False |
| B_C | 10.696578 | 0.175186 | 0.227014 | -0.001288 | -0.000873 | 5 | False |
| A_B | 10.757101 | 0.235710 | 0.324112 | 0.000333 | 0.001019 | 7 | False |
| C | 10.809961 | 0.288569 | 0.336964 | 0.000000 | 0.000000 | 10 | False |
| A_C | 11.007898 | 0.486507 | 0.563980 | -0.000815 | -0.000428 | 10 | False |
| A_B_C_D | 11.124192 | 0.602800 | 0.712217 | 0.001128 | 0.001970 | 11 | False |


**Klubforbehold for B:** 31/40 klub-sæsoner forbedres og 9/40 forværres i punktestimatet. Nedenstående positive intervaller er yderligere valideringsflag, ikke skjult bag de gode poolede grupper. De er ikke multiplicitetstilpassede, og de forhindrer en ubetinget integrationsanbefaling. Ingen klubspecifik efterjustering laves på disse evalueringsresultater.

| Sæson | Klub | B ΔMAE | 95% lav | 95% høj |
| --- | --- | --- | --- | --- |
| 2024-25 | Everton | 0.194311 | 0.019684 | 0.378063 |
| 2025-26 | Newcastle | 0.177135 | 0.014841 | 0.340161 |
| 2025-26 | Wolves | 0.233766 | 0.020025 | 0.454888 |


Statistisk understøttede forværringsflag, med ovennævnte multiple-test-forbehold:

| Sæson | Arm | Gruppe | ΔMAE | MAE 95% lav | ΔBrier | Brier 95% lav |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | A | regular | 0.144294 | 0.082856 | 0.000196 | -0.000427 |
| 2024-25 | A | rotation | 0.217392 | 0.132738 | -0.002460 | -0.004070 |
| 2024-25 | A | reserve | 0.056526 | 0.018563 | -0.000855 | -0.001311 |
| 2024-25 | A | long_rest | 0.227723 | 0.111390 | -0.002201 | -0.003248 |
| 2024-25 | C | regular | 0.649228 | 0.505831 | 0.000000 | 0.000000 |
| 2024-25 | C | rotation | 0.533331 | 0.338637 | 0.000000 | 0.000000 |
| 2024-25 | C | long_rest | 0.166547 | 0.110017 | 0.000000 | 0.000000 |
| 2024-25 | D | regular | 0.273447 | 0.143957 | 0.000071 | -0.000768 |
| 2024-25 | A_B | rotation | 0.244772 | 0.023754 | -0.001126 | -0.004518 |
| 2024-25 | A_B | reserve | 0.130929 | 0.030321 | 0.000918 | 0.000144 |
| 2024-25 | A_B | long_rest | 0.516109 | 0.176894 | 0.000157 | -0.002127 |
| 2024-25 | A_C | regular | 0.824905 | 0.622110 | 0.000196 | -0.000427 |
| 2024-25 | A_C | rotation | 0.863457 | 0.611010 | -0.002460 | -0.004070 |
| 2024-25 | A_C | reserve | 0.101272 | 0.045362 | -0.000855 | -0.001311 |
| 2024-25 | A_C | long_rest | 0.450773 | 0.291041 | -0.002201 | -0.003248 |
| 2024-25 | B_C | rotation | 0.283610 | 0.036094 | -0.003105 | -0.005005 |
| 2024-25 | A_B_C_D | regular | 0.822184 | 0.561686 | 0.001507 | -0.000040 |
| 2024-25 | A_B_C_D | rotation | 0.950278 | 0.519109 | 0.000420 | -0.003353 |
| 2024-25 | A_B_C_D | reserve | 0.230682 | 0.133205 | 0.001996 | 0.001141 |
| 2024-25 | A_B_C_D | source_medical_return | 3.056396 | 0.040248 | 0.036665 | 0.000699 |
| 2024-25 | A_B_C_D | long_rest | 0.855934 | 0.493418 | 0.002512 | 0.000046 |
| 2025-26 | A | rotation | 0.515483 | 0.383956 | -0.001063 | -0.002666 |
| 2025-26 | A | reserve | 0.055598 | 0.015299 | -0.000678 | -0.000970 |
| 2025-26 | A | documented_return_2 | 0.476238 | 0.069403 | -0.005142 | -0.011546 |
| 2025-26 | A | documented_return_3 | 0.533540 | 0.177672 | -0.000140 | -0.004210 |
| 2025-26 | A | long_rest | 0.321506 | 0.197311 | -0.002555 | -0.003444 |
| 2025-26 | C | regular | 0.908362 | 0.699374 | 0.000000 | 0.000000 |
| 2025-26 | C | rotation | 0.654284 | 0.477328 | 0.000000 | 0.000000 |
| 2025-26 | C | reserve | 0.057914 | 0.029437 | 0.000000 | 0.000000 |
| 2025-26 | C | source_medical_return | 0.468298 | 0.192761 | 0.000000 | 0.000000 |
| 2025-26 | C | documented_return_3 | 0.892358 | 0.311405 | 0.000000 | 0.000000 |
| 2025-26 | C | short_rest | 0.824665 | 0.535284 | 0.000000 | 0.000000 |
| 2025-26 | C | long_rest | 0.210627 | 0.105474 | 0.000000 | 0.000000 |
| 2025-26 | D | regular | 0.202741 | 0.125458 | -0.000314 | -0.001034 |
| 2025-26 | A_B | regular | 0.000018 | -0.324884 | 0.001847 | 0.000433 |
| 2025-26 | A_B | rotation | 0.816403 | 0.585503 | 0.000505 | -0.001744 |
| 2025-26 | A_B | reserve | 0.114609 | 0.018032 | -0.000091 | -0.000862 |
| 2025-26 | A_B | long_rest | 0.711699 | 0.448002 | -0.001440 | -0.003361 |
| 2025-26 | A_C | regular | 1.054618 | 0.709318 | 0.000397 | -0.000207 |
| 2025-26 | A_C | rotation | 1.255423 | 1.010785 | -0.001063 | -0.002666 |
| 2025-26 | A_C | reserve | 0.129818 | 0.073761 | -0.000678 | -0.000970 |
| 2025-26 | A_C | documented_return_3 | 1.416612 | 0.681891 | -0.000140 | -0.004210 |
| 2025-26 | A_C | short_rest | 0.938895 | 0.604508 | -0.002066 | -0.004781 |
| 2025-26 | A_C | long_rest | 0.581632 | 0.420346 | -0.002555 | -0.003444 |
| 2025-26 | B_C | regular | 0.613371 | 0.335040 | 0.000138 | -0.000625 |
| 2025-26 | B_C | rotation | 0.712632 | 0.511807 | -0.002772 | -0.003901 |
| 2025-26 | B_C | short_rest | 0.646609 | 0.380307 | 0.000126 | -0.002098 |
| 2025-26 | B_C | long_rest | 0.269354 | 0.153971 | -0.003079 | -0.004186 |
| 2025-26 | A_B_C_D | regular | 1.091276 | 0.570275 | 0.001734 | 0.000204 |
| 2025-26 | A_B_C_D | rotation | 1.510941 | 1.204349 | 0.001281 | -0.001334 |
| 2025-26 | A_B_C_D | reserve | 0.215554 | 0.105497 | 0.000633 | -0.000313 |
| 2025-26 | A_B_C_D | documented_return_3 | 1.919614 | 0.536064 | 0.002684 | -0.010212 |
| 2025-26 | A_B_C_D | short_rest | 0.948946 | 0.530007 | 0.000529 | -0.005456 |
| 2025-26 | A_B_C_D | long_rest | 0.943021 | 0.638326 | -0.000371 | -0.002864 |

## 6. Fejlattribution og de 35 false-zero-tilfælde


| Komponent | Isoleret absolut størrelse | Algebraisk Shapley-MAE | Andel af samlet MAE |
| --- | --- | --- | --- |
| start_selection | 9.165592 | 7.605612 | 0.722871 |
| starter_duration | 2.263843 | 1.533239 | 0.145726 |
| sub_appearance | 1.598100 | 0.763876 | 0.072602 |
| sub_duration | 1.204110 | 0.618664 | 0.058801 |


Shapley-opdelingen summerer algebraisk til den samlede minut-MAE, men er **fejlattribution, ikke kausal forklaring**. Komponenterne kan forstærke eller ophæve hinanden. Klubdiagnosen i report.json viser også de største komponentstørrelser. For tidlige exit/minutfejl er der ikke verificeret føring, skade, rødt kort eller trænerbeslutning som årsag.

De samme 35 modstridende hard-source appearance-tilfælde bevares i alle nye arme. 32 er OUT, tre SUSPENDED. De tre suspensioners rå dag/måned matcher en senere DGW-kamp; der mangler fortsat fuldt verificerede predeadline-udløbstidspunkter. Udaterede/ufuldstændige returdatoer, senere artikler og kliniske gæt reparerer ikke en historisk forecast.

| Kildens begrundelseskategori | Tilfælde |
| --- | --- |
| registration_or_loan | 3 |
| source_fitness | 1 |
| source_medical_wording | 26 |
| source_personal | 1 |
| suspension | 3 |
| unknown | 1 |


Kategorierne beskriver **ordlyd i kilden**, ikke verificeret diagnose, transferfejl eller endelig årsag. Alle 35 individuelle IDs, rå nyheder, kildelinks, deadlines, kickoff, kildealder og dokumenterede begrænsninger står i `false_zero_source_diagnosis.csv`. Ingen tilføjet sandsynlighedsfloor eller falsk tilgængelighed skjuler problemet. Disse kilde-/certaintykonflikter blokerer fortsat fuld livegodkendelse.

## 7. Kalibrering af C's betingede minutfordeling

| Sæson | Betingelse | N | 10–90%-interval dækning | Gns. intervalbredde | Betinget MAE | P90 Brier |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | start | 3758 | 0.884513 | 19.327036 | 7.948493 | 0.186352 |
| 2024-25 | cameo | 1438 | 0.808067 | 31.863700 | 10.744478 | Not Available |
| 2025-26 | start | 7256 | 0.872106 | 18.885888 | 7.830370 | 0.189358 |
| 2025-26 | cameo | 2692 | 0.800892 | 31.648960 | 11.028202 | Not Available |


Dette er predictive duration-intervaller betinget på faktisk start/indskiftning og positiv modelmasse, ikke konfidensintervaller for modelparametre. Hard-excluded optrædener får ikke en kunstig positiv event-sandsynlighed for at kunne scores betinget. Original MM's komplette duration-PMF er ikke bevaret i den frosne tabel, så der er **ikke opfundet** en original P90- eller intervalbaseline ud fra dens middelværdi. Sammenlignelige s/c-MAE og samlet MM-MAE findes ovenfor; distributionens egen kalibrering vises som diagnostik.

## 8. Hvad bør videreføres?


### Hvorfor C ikke godkendes trods bedre betingede varigheder

C sænker startervarighed-MAE 8,064556→7,873829 og cameo-varighed-MAE 11,348578→10,899898, men øger samlet minut-MAE. Her er en eksakt opdeling af den samlede forskel i retrospektive udfaldsgrupper; labels bruges ikke som prognosefeatures:

| Faktisk udfald | N | Δs | Δc | Δx | ΔMAE i gruppen | Bidrag til samlet ΔMAE |
| --- | --- | --- | --- | --- | --- | --- |
| actual_start | 11022 | -0.690801 | 2.288710 | -1.168434 | 0.541953 | 0.152134 |
| actual_cameo | 4166 | 2.695912 | 0.469128 | 1.049416 | 0.426401 | 0.045242 |
| actual_zero | 24076 | -2.298527 | 0.440658 | 0.148721 | 0.148721 | 0.091193 |


Betinget varighedspræcision er altså ikke nok: x=p·s+(1−p)q·c scorer også for spillere, der ikke starter eller slet ikke spiller. Ændrede varigheder under uændrede p/q kan give en dårligere samlet tabsfunktion. Dette er en målt mekanismeopdeling, ikke bevis for taktisk eller medicinsk årsag. C bør derfor ikke integreres globalt på baggrund af de betingede gevinster alene.


Den poolede kritiske gruppescreen anbefaler **B** som reference/næste forskningskandidat. Den laveste samlede punkt-MAE fra **B** alene er ikke tilstrækkelig til integration. **B har klubspecifikke forværringsflag for Everton 2024/25 og Newcastle/Wolves 2025/26. Derfor anbefales kun videre uafhængig validering/kontrolleret integrationstest, ikke ubetinget produktion.** Se tabellerne for præcis hvilke rolle-/retur-/restitutionsgrupper, der forværres. Ingen klub- eller spiller-specifik efterjustering er indført for at skjule disse udsnit. A og C frarådes som generelle minut-MAE-ændringer; D giver ingen dokumenteret ekstra MAE-gevinst, og B+D er ikke bedre end B alene.


Før en ændring kan integreres, kræves nye ubrugte/prospektive MM-origins, dokumenteret kildekvalitet i nulkonflikterne, korrekt fixture-scoped suspension, kontrolleret dækning af øvrige turneringers belastning og evaluering af manglende event-/medicinske oplysninger. Modellen må ikke gøres mere kompleks alene for at opnå pænere Haaland-/Palmer-/João Pedro-tal. Der er ikke kørt PM/TS, så der drages ingen konklusion om FPL-point eller transfergevinst.

## 9. Reproduktion og sikkerhed

`research_individual_mm_refinement.py` udfører hele A–D-replayet, referencetjek, alle klub-/gruppeopdelinger, blokintervaller, kalibrering og distributionsarkivering. `fit_cutoffs.csv` dokumenterer hver origins tidligere kendte labels. `prior_only_features.csv.gz` har ingen aktuelle start-/minutlabels; `predictions.npz` og evalueringsfiler indeholder truth og må ikke bruges som prognosefeatures. `content_manifest.json` hasher gzip-indhold efter dekomprimering og NPZ som kanonisk decoded CSV.

```bash
pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests
python scripts/restore_core_checkpoint.py
python scripts/archive_role_injury_mm.py --restore work/refinement-mm-source
cp work/refinement-mm-source/results/predictions.npz analysis/results/role-injury-mm-20261016/
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/research_individual_mm_refinement.py
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/report_individual_mm_refinement.py
PYTHONPATH=src:scripts:. python -m pytest tests/test_individual_mm_refinement.py tests/test_club_match_importance.py tests/test_mm_competition_rotation.py tests/test_mm_all_clubs.py tests/test_mm_probability_robustness.py tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
```

72 fokuserede MM-/kildetests består lokalt. De nye tester bl.a. current-truth-leakage, known-at-grænser, ukendt fravær, tidligere observeret selektion, hard-source karantæne, klubskiftebelastning, klinisk uverificeret retur, lovlige marginaler og duration-support. Produktions-`src`, original MM og det frosne benchmark er bevaret; `locked_model_active=false`.


### Verificeret CI og eksakt reproduktion

[GitHub Actions 38966504511](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38966504511) består alle72 tests, begge sæsoner/40klub-sæsoner, alle11 arme, produktionsdiff og original MM-checksum. Kode `8cb2c3e`; resultatcommit `ea0b2ec`. Artifact 12076020691 er downloadet og ZIP-SHA-256-verificeret. Alle13 resultatfilers **indhold** matcher byte-for-byte mellem lokal kørsel og ren CI, herunder hele predictions-arkivet efter kanonisk NPZ-dekodning. Gzip-containere og NPZ-containerbytes påstås ikke at være identiske; det er de verificerede indholdshashes.

Den fulde sammenligning og kilde-/produktionskontroller findes i `docs/checkpoints/2026-10-16-individual-mm-refinement-reproduction.json`. De rapportafledte beslutnings-/ablationstabeller gemmes separat under `docs/research/data/`, så de ikke forurener modeloutputmanifestet ved en ny kørsel.
