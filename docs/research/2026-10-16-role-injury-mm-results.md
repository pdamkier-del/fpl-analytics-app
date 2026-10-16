# MM: rolle-, skade- og team-news-test, 16. oktober 2026

**Forskningsresultat, PR #8. Ingen produktionsgodkendelse.** Kun MM er genafspillet. PM, FPL-point, TS og chips er hverken simuleret eller ændret. `locked_model_active=false`.

## Konklusion

Tidsafgrænset FPL-news korrigerer en væsentlig datamangel i 2024/25. Den eksisterende individuelle MM havde allerede de hårde statusser i 2025/26. En ekstra, GW-afgrænset FPL-spillechance som loft over fremmøde forbedrer de genbrugte forskningsperioder i begge sæsoner. Det er en følsomhedstest af kildens procenttal, ikke en valideret medicinsk sandsynlighed. Bevar den låste model og undersøg kandidaten prospektivt.

At bevare hele startchancen fra før en skade giver dårligere returprognoser. Kun at bevare minutter betinget på start er mere lovende, især i 2025/26. Kombinationen med spillechanceloftet er eksplorativ og blev tilføjet efter de separate ablationer; den er ikke en uafhængigt bekræftet vinder.

## Kilder, identiteter og begrænsninger

- Frosset MM-reference fra PR #4, commit `6d875a65251fb62f691dc0386ea81aeb29d27c0f`; seks MM-filer er udtaget med kontrol af del-, ZIP- og filchecksums. Ingen PM-tabeller bliver brugt.
- Officielle historiske FPL API-payloads i det uafhængige `Randdalf/fplcache`-arkiv, fastlåst ved commit `17e703acd4f744931afa9d1d90a2998cfb104286`. Identitet kræver sæsonens element-ID og uafhængig stabil FPL-kode; klubtilknytning og deadline skal passe. Forkerte klubber/urettidige observationer afvises.
- 2025/26 genbruger det eksisterende strenge team-news-arkiv. For 2024/25 var de gamle Actions-jobtider ikke længere tilgængelige. Alle 33 relevante snapshot-commits er nu tidsafgrænset ved et præcist match på offentligt GitHub PushEvent, repository-ID 359131220, branch, commit og parent. GH Archive bevarer GitHubs Events API: https://www.gharchive.org/ . Hver timefil har URL, størrelse og SHA-256; hvert match har event-ID, event-SHA og serverens tidspunkt i kildemanifestet.
- Dette verificerer, at den konkrete FPL-snapshot fandtes før deadline. Det er ikke dokumentation for et lægeligt skadestidspunkt. `news_added` bevares, når det findes; ellers er publiceringstidspunktet ukendt og kun den verificerede capture-grænse anvendes. Nye, mutable historiske artikler bruges ikke til at skrive fortidens inputs om.
- News er kun gældende ved matchende cutoff og payloadens aktuelle/næste GW. Ukendt status betyder ikke rask. `u` (unavailable) kan være klubskifte/udlån og bliver ikke omdøbt til skade. Skadetype kræver eksplicit tekst; “Expected back” alene betyder ikke rygskade.
- En medicinsk episode her er en observeret officiel FPL-skademarkering med eksplicit skade/illness-tekst, ikke en klinisk verificeret diagnose. En selection-return er første kildebekræftede AVAILABLE efter denne markering, ikke træningsretur eller fuld kampklarhed. Forventet-fraværstekst gemmes ordret uden at opfinde manglende år/dag.
- Faktiske skadestart-, træningsretur- og lægelige klaringsdatoer er ukendte. Retrospektivt første observerede kamp efter en flagning gemmes separat som evaluation-only og kommer aldrig ind i forecasts.

### Dækning ved alle 33 MM-origins (GW6–38)

| Sæson | Spillerkampe | Strengt matchede | Dækning | Medicinske OUT-rækker | Observerede episoder | Selection-returer | Træningsreturudsagn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | 24072 | 23974 | 99.59% | 1996 | 349 | 282 | 0 |
| 2025-26 | 26159 | 26074 | 99.68% | 2015 | 357 | 294 | 0 |

Kildeobservationer og forecast-spillerkampe har forskellige nøgler: samme GW-snapshot kan genbruges til begge kampe i en dobbelt-GW. Episoder/returer tælles i kilden; fejlmål tælles på de identiske forecast-spillerkampe.

Eksisterende taktiske roller genbruges beskrivende: 8.350 verificerede starterrækker og 13.627 historiske profiler i 2025/26; de anvendes ikke som nye numeriske features. 2024/25 har ikke tilsvarende verificerede taktiske labels. Historiske labels er koblet til faktisk start, kanonisk spiller og klub; kun tidligere labels vises ved en deadline. Roller ved tidligere klub opbevares separat. De nye labels er ikke indført som uvaliderede numeriske features.

## Matematisk kandidat og kontroller

MM-identiteten er `E[M] = p*s + (1-p)*q*c`, hvor p er startchance, s forventede minutter ved start, q indskiftningschance givet ingen start og c minutter ved indskiftning. Den eksisterende rollemodel og dens koefficienter er frosset. Et separat latent normalrolle-register gemmer seneste kildebekræftede tilgængelige rolle ved samme klub; en medicinsk OUT opdaterer ikke denne rolle til nul. Klubskifte nulstiller registeret, og ukendt tilgængelighed etablerer ikke en rask normalrolle.

Hårdt, rettidigt OUT/SUSPENDED giver fremmødeloft a=0. Spillechancevarianten bruger alene den verificerede, GW-scopede FPL-procent a. Ingen procent betyder intet ekstra loft, ikke en påstået 100% medicinsk tilgængelighed. Først p←min(p,a), dernæst q←min(q,(a-p)/(1-p)); dermed P(spil)=p+(1-p)q≤a. Sandsynligheden multipliceres ikke med samme skadeinformation igen. Dette er ikke en separat estimeret P(start|tilgængelig); den er stadig en manglende kalibreringsopgave.

Den eksisterende odds-projektion genbruges separat for målmand (sum p=1) og markspillere (sum p=10), under de samme caps og hårde utilgængeligheder. Alle evaluerede fulde hold er feasible. Det er en kontrol af MM-marginaler, ikke en ny kamp-/XI-Monte-Carlo-simulation. Ingen utilgængelig spiller opfindes for at få 11.

Returablationerne genbruger kun tidligere, samme-klub og kildebekræftet p/s/q/c: enten hele tuple ved første selection-return eller kun s. Der er ingen manuelt valgte spillerboosts, ny fitted koefficient eller opfundet return-to-play-kurve. Forskellige skadetyper får ikke nye uvaliderede restitutionstider.

## Walk-forward-protokol

PR #4-valget blev foretaget på 2024/25 GW11–21. Evaluering her er 2024/25 GW22–38 og 2025/26 GW6–38. Alle 13 arme bruger identiske nøgler og outcomes; forskelle afvises. Den frosne reference var trænet på præfikser kendt ved hver historisk deadline. Nye statusregler refitter ikke modellen. Primærarmen `role_news_projected` blev frosset før sammenligning; chance-, retur- og rolleafkoblingsarme vises også, inklusive negative resultater.

Perioderne har været brugt i tidligere forskning og er ikke uberørte holdouts. Den efterfølgende chance+duration-kombination er eksplicit post hoc. 95% intervaller er 1.000 parrede fixture-block-bootstrap-træk med fast seed. De måler fixture-sampling-usikkerhed, ikke systematisk kildefejl, serial korrelation mellem kampe eller modelvalgsusikkerhed; der er ingen korrektion for de mange sammenligninger. Under 20 kampblokke vises intet interval. Der køres ingen ny Monte Carlo, så resultaterne indeholder ikke ny simulationsstøj.

Historisk tilgængelighed for realiserede kampdata bruger stadig den nedarvede kickoff+3/4h-proxy. Dette er en konkret begrænsning for fuld cutoff-certificering, selv om FPL-news-snapshottene nu har uafhængige klokkegrænser.

## 2024-25 – samlede resultater

| Arm | N | MAE min | RMSE min | Bias min | Start-Brier | Start-logloss |
| --- | --- | --- | --- | --- | --- | --- |
| original | 13105 | 12.653 | 22.305 | -0.104 | 0.081052 | 0.265987 |
| no_role | 13105 | 12.328 | 22.100 | -0.224 | 0.080122 | 0.259891 |
| role | 13105 | 12.309 | 22.081 | -0.230 | 0.080019 | 0.259769 |
| original_news | 13105 | 11.449 | 21.622 | -1.349 | 0.076697 | 0.253367 |
| no_role_news | 13105 | 11.387 | 21.445 | -1.204 | 0.075761 | 0.250624 |
| role_news | 13105 | 11.364 | 21.425 | -1.214 | 0.075649 | 0.250437 |
| role_news_projected | 13105 | 11.272 | 21.321 | -0.425 | 0.075005 | 0.248064 |
| role_source_chance | 13105 | 11.160 | 21.068 | -0.479 | 0.073653 | 0.244040 |
| role_return_carry | 13105 | 11.329 | 21.348 | -0.302 | 0.075362 | 0.248769 |
| role_return_duration | 13105 | 11.268 | 21.301 | -0.393 | 0.075005 | 0.248064 |
| no_role_source_chance | 13105 | 11.186 | 21.087 | -0.474 | 0.073756 | 0.244260 |
| role_chance_return_duration | 13105 | 11.156 | 21.048 | -0.446 | 0.073653 | 0.244040 |
| no_role_chance_return_duration | 13105 | 11.181 | 21.067 | -0.442 | 0.073756 | 0.244260 |

### Isolerede ændringer mod rolle + hård news + projektion

| Ændring | MAE-delta [95% CI] | Retur-MAE-delta [95% CI] |
| --- | --- | --- |
| role_source_chance | -0.112 [-0.156, -0.068] | -0.040 [-0.114, 0.035] |
| role_return_carry | 0.057 [-0.016, 0.130] | 2.811 [-2.348, 7.537] |
| role_return_duration | -0.004 [-0.021, 0.012] | -0.330 [-1.597, 0.798] |
| role_chance_return_duration | -0.116 [-0.160, -0.073] | -0.345 [-1.632, 0.823] |

Ren rolleeffekt under samme chance-loft: -0.025 [-0.035, -0.015]

### Alle klubber, størst primær-MM-fejl først

| Klub | Eval N | Original MAE | Rolle MAE | News MAE | News RMSE | News bias | News Brier | News logloss | News−rolle MAE [95% CI] | Chance+duration MAE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Man City | 634 | 18.663 | 18.123 | 16.974 | 28.698 | -0.033 | 0.11923 | 0.35773 | -1.148 [Not Available] | 16.755 |
| Ipswich | 636 | 16.565 | 16.164 | 15.146 | 26.266 | -0.111 | 0.10889 | 0.37059 | -1.018 [Not Available] | 15.023 |
| West Ham | 538 | 16.375 | 15.805 | 15.010 | 25.020 | -0.684 | 0.10163 | 0.32212 | -0.795 [Not Available] | 14.935 |
| Man Utd | 687 | 16.255 | 15.336 | 14.051 | 25.472 | -0.357 | 0.10615 | 0.31996 | -1.285 [Not Available] | 13.777 |
| Spurs | 791 | 15.882 | 15.041 | 13.685 | 25.513 | -0.436 | 0.10983 | 0.32771 | -1.356 [Not Available] | 13.407 |
| Liverpool | 612 | 13.542 | 13.258 | 12.755 | 22.791 | -0.491 | 0.08941 | 0.32201 | -0.503 [Not Available] | 12.737 |
| Fulham | 524 | 13.324 | 13.561 | 12.591 | 21.863 | -0.500 | 0.08732 | 0.28231 | -0.969 [Not Available] | 12.642 |
| Leicester | 635 | 14.095 | 13.388 | 12.394 | 21.321 | -0.745 | 0.06821 | 0.23066 | -0.994 [Not Available] | 12.164 |
| Aston Villa | 721 | 13.184 | 13.257 | 12.295 | 23.264 | -0.674 | 0.08795 | 0.26836 | -0.962 [Not Available] | 12.148 |
| Southampton | 689 | 13.114 | 13.116 | 12.152 | 22.493 | -0.757 | 0.08401 | 0.27466 | -0.965 [Not Available] | 11.977 |
| Arsenal | 583 | 12.343 | 12.388 | 11.260 | 20.920 | -0.202 | 0.07814 | 0.25610 | -1.128 [Not Available] | 11.171 |
| Nott'm Forest | 581 | 10.412 | 10.132 | 9.681 | 18.005 | -0.407 | 0.05336 | 0.18810 | -0.450 [Not Available] | 9.477 |
| Chelsea | 785 | 10.099 | 10.124 | 9.506 | 20.026 | -0.227 | 0.06479 | 0.24139 | -0.618 [Not Available] | 9.416 |
| Everton | 605 | 10.967 | 10.944 | 9.457 | 18.287 | -0.407 | 0.05893 | 0.19379 | -1.487 [Not Available] | 9.413 |
| Crystal Palace | 591 | 10.157 | 10.253 | 9.317 | 18.285 | -0.444 | 0.05593 | 0.22839 | -0.936 [Not Available] | 9.253 |
| Newcastle | 572 | 11.251 | 10.559 | 9.255 | 16.608 | -0.467 | 0.04273 | 0.16130 | -1.304 [Not Available] | 9.245 |
| Brighton | 838 | 11.225 | 10.377 | 8.811 | 18.212 | -0.427 | 0.05967 | 0.18872 | -1.565 [Not Available] | 8.721 |
| Wolves | 754 | 9.405 | 8.893 | 8.084 | 16.619 | -0.575 | 0.04574 | 0.16168 | -0.810 [Not Available] | 8.117 |
| Bournemouth | 680 | 9.356 | 8.767 | 7.365 | 15.674 | -0.431 | 0.04776 | 0.16146 | -1.402 [Not Available] | 7.233 |
| Brentford | 649 | 7.774 | 7.929 | 7.090 | 14.364 | -0.124 | 0.03236 | 0.12239 | -0.839 [Not Available] | 7.025 |

### Spillergrupper (samme primære fejldefinition)

| Gruppe | N | Original MAE | Rolle MAE | News MAE | Chance+duration MAE | News RMSE | News Brier | News logloss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| player_type:regular | 1665 | 15.737 | 15.965 | 14.346 | 14.150 | 24.000 | 0.07994 | 0.29969 |
| player_type:rotation_or_short_history | 3446 | 24.539 | 24.541 | 22.322 | 22.053 | 30.438 | 0.15820 | 0.48244 |
| player_type:reserve | 7994 | 6.887 | 6.275 | 5.869 | 5.835 | 15.029 | 0.03811 | 0.13628 |
| news_medical_return:True | 174 | 23.371 | 23.279 | 22.647 | 22.301 | 32.939 | 0.18114 | 0.56277 |
| news_medical_out:True | 1086 | 8.884 | 7.840 | 0.257 | 0.257 | 3.423 | 0.00092 | 0.02544 |
| news_eligible:True | 13063 | 12.670 | 12.335 | 11.292 | 11.175 | 21.353 | 0.07524 | 0.24875 |
| news_eligible:False | 42 | 7.323 | 4.345 | 5.109 | 5.210 | 5.767 | 0.00161 | 0.03462 |

Gruppemetrics, bias og parrede primær-vs-rolle-intervaller findes også i report.json; små grupper skal fortolkes med ekstra varsomhed.

### Haaland, Palmer og João Pedro

| Spiller | N | Original MAE | Rolle MAE | News MAE | Chance MAE | Chance+duration MAE | Original bias | Kombination bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Erling Haaland | 17 | 33.852 | 31.368 | 20.636 | 20.620 | 20.620 | 6.870 | -7.306 |
| Cole Palmer | 17 | 17.545 | 18.492 | 17.676 | 18.304 | 18.304 | -2.334 | -3.403 |
| João Pedro Junqueira de Jesus | 17 | 22.873 | 22.864 | 17.422 | 17.044 | 17.044 | 3.394 | 0.093 |

Dette er fejl over de historiske evalueringskampe, ikke et nyt liveforecast eller en manuel korrektion af bestemte spillere.

### Svageste komponenter

| Komponent | Original MAE-attribution | Rolle | News | Chance+duration |
| --- | --- | --- | --- | --- |
| start_selection | 9.289 | 8.993 | 8.123 | 8.108 |
| starter_duration | 1.619 | 1.597 | 1.641 | 1.605 |
| cameo_selection | 1.064 | 1.058 | 0.859 | 0.799 |
| cameo_duration | 0.682 | 0.661 | 0.648 | 0.644 |

Eksakt algebraisk Shapley-fordeling af absolut minutfejl: komponenterne summerer til MAE, men er ikke kausale skades-/taktikforklaringer. Startudvælgelse er den største fejlkomponent; kildeudfaldskonflikter og ukendt kampklarhed består. 10 evaluerede medicinske OUT-rækker havde faktisk kampdeltagelse. Disse labels bevares; de omskrives ikke med fremtidsviden.

### Største individuelle primærfejl

| Spiller | GW | Faktiske min | Forventede min | P(start) | News | Diagnose |
| --- | --- | --- | --- | --- | --- | --- |
| Axel Tuanzebe | 30 | 90.0 | 0.000 | 0.000 | OUT | source_outcome_conflict |
| Curtis Jones | 25 | 90.0 | 0.000 | 0.000 | SUSPENDED | source_outcome_conflict |
| Marc Guéhi | 32 | 90.0 | 0.000 | 0.000 | SUSPENDED | source_outcome_conflict |
| Daniel Bentley | 33 | 90.0 | 0.784 | 0.009 | AVAILABLE | start_selection_error |
| Tyler Fredricson | 33 | 90.0 | 0.998 | 0.012 | AVAILABLE | start_selection_error |
| Pau Torres | 30 | 90.0 | 1.055 | 0.033 | AVAILABLE | start_selection_error |
| Altay Bayindir | 32 | 90.0 | 1.174 | 0.014 | AVAILABLE | start_selection_error |
| Charlie Taylor | 38 | 90.0 | 1.195 | 0.010 | AVAILABLE | start_selection_error |
| Guglielmo Vicario | 25 | 90.0 | 1.573 | 0.016 | DOUBT | start_selection_error |
| Christian Walton | 38 | 90.0 | 1.693 | 0.018 | AVAILABLE | start_selection_error |

De 30 største fejl pr. sæson og præcise fixture-/spiller-ID’er, cutoff, kilde og alle komponenter findes i report.json. “duration_error_unverified_cause” betyder, at årsagen ikke er dokumenteret, ikke at en taktisk udskiftning/skade er bevist.

## 2025-26 – samlede resultater

| Arm | N | MAE min | RMSE min | Bias min | Start-Brier | Start-logloss |
| --- | --- | --- | --- | --- | --- | --- |
| original | 26159 | 10.533 | 20.495 | -0.072 | 0.069635 | 0.228875 |
| no_role | 26159 | 10.395 | 20.338 | -0.286 | 0.069420 | 0.228468 |
| role | 26159 | 10.387 | 20.331 | -0.290 | 0.069380 | 0.228435 |
| original_news | 26159 | 10.355 | 20.443 | -0.252 | 0.069635 | 0.228875 |
| no_role_news | 26159 | 10.395 | 20.338 | -0.286 | 0.069420 | 0.228468 |
| role_news | 26159 | 10.387 | 20.331 | -0.290 | 0.069380 | 0.228435 |
| role_news_projected | 26159 | 10.387 | 20.331 | -0.290 | 0.069380 | 0.228435 |
| role_source_chance | 26159 | 10.212 | 20.114 | -0.355 | 0.068343 | 0.224998 |
| role_return_carry | 26159 | 10.408 | 20.308 | -0.221 | 0.069601 | 0.228622 |
| role_return_duration | 26159 | 10.379 | 20.310 | -0.278 | 0.069380 | 0.228435 |
| no_role_source_chance | 26159 | 10.221 | 20.122 | -0.351 | 0.068385 | 0.225046 |
| role_chance_return_duration | 26159 | 10.203 | 20.093 | -0.343 | 0.068343 | 0.224998 |
| no_role_chance_return_duration | 26159 | 10.213 | 20.101 | -0.339 | 0.068385 | 0.225046 |

### Isolerede ændringer mod rolle + hård news + projektion

| Ændring | MAE-delta [95% CI] | Retur-MAE-delta [95% CI] |
| --- | --- | --- |
| role_source_chance | -0.175 [-0.240, -0.121] | -0.173 [-0.412, -0.008] |
| role_return_carry | 0.021 [-0.020, 0.061] | 0.767 [-2.954, 4.535] |
| role_return_duration | -0.009 [-0.014, -0.003] | -0.821 [-1.378, -0.356] |
| role_chance_return_duration | -0.184 [-0.249, -0.130] | -1.001 [-1.579, -0.513] |

Ren rolleeffekt under samme chance-loft: -0.009 [-0.014, -0.005]

### Alle klubber, størst primær-MM-fejl først

| Klub | Eval N | Original MAE | Rolle MAE | News MAE | News RMSE | News bias | News Brier | News logloss | News−rolle MAE [95% CI] | Chance+duration MAE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chelsea | 1205 | 14.558 | 14.117 | 14.117 | 24.929 | -0.166 | 0.10291 | 0.31428 | -0.000 [-0.000, 0.000] | 14.012 |
| Fulham | 998 | 13.532 | 13.578 | 13.578 | 23.121 | -0.319 | 0.08833 | 0.31097 | 0.000 [-0.000, 0.000] | 13.062 |
| Newcastle | 1258 | 12.311 | 12.092 | 12.092 | 22.577 | -0.475 | 0.08615 | 0.26904 | 0.000 [-0.000, 0.000] | 12.058 |
| Arsenal | 1179 | 12.366 | 12.031 | 12.031 | 21.816 | -0.597 | 0.08752 | 0.28113 | -0.000 [-0.000, -0.000] | 12.031 |
| Wolves | 1339 | 11.614 | 11.626 | 11.626 | 22.231 | -0.174 | 0.08354 | 0.26849 | 0.000 [-0.000, 0.000] | 11.459 |
| Man City | 1221 | 11.860 | 11.605 | 11.605 | 21.560 | -0.167 | 0.07608 | 0.24789 | 0.000 [-0.000, 0.000] | 11.524 |
| Aston Villa | 1513 | 11.497 | 11.329 | 11.329 | 22.346 | -0.095 | 0.07913 | 0.24406 | 0.000 [-0.000, 0.000] | 11.225 |
| Nott'm Forest | 1256 | 11.015 | 10.894 | 10.894 | 20.140 | -0.420 | 0.07049 | 0.25854 | -0.000 [-0.000, 0.000] | 10.726 |
| Liverpool | 1217 | 10.792 | 10.533 | 10.533 | 20.487 | -0.339 | 0.06825 | 0.21759 | 0.000 [-0.000, 0.000] | 10.335 |
| Leeds | 1166 | 10.700 | 10.465 | 10.465 | 19.798 | -0.595 | 0.06370 | 0.23420 | -0.000 [-0.000, 0.000] | 10.460 |
| Spurs | 1400 | 10.596 | 10.348 | 10.348 | 20.492 | -0.274 | 0.07406 | 0.22730 | 0.000 [-0.000, 0.000] | 10.282 |
| West Ham | 1264 | 10.164 | 10.169 | 10.169 | 19.483 | -0.103 | 0.06232 | 0.21821 | -0.000 [-0.000, 0.000] | 9.910 |
| Burnley | 1417 | 9.933 | 9.953 | 9.953 | 19.564 | -0.199 | 0.06524 | 0.23667 | -0.000 [-0.000, -0.000] | 9.787 |
| Man Utd | 1382 | 9.773 | 9.722 | 9.722 | 19.717 | -0.343 | 0.06276 | 0.20492 | -0.000 [-0.000, 0.000] | 9.295 |
| Crystal Palace | 1350 | 9.738 | 9.610 | 9.610 | 19.778 | -0.356 | 0.06354 | 0.20633 | -0.000 [-0.000, 0.000] | 9.378 |
| Brighton | 1491 | 9.241 | 9.104 | 9.104 | 18.575 | -0.213 | 0.05789 | 0.18790 | -0.000 [-0.000, 0.000] | 9.025 |
| Everton | 1189 | 9.007 | 8.934 | 8.934 | 18.747 | -0.184 | 0.05435 | 0.17934 | -0.000 [-0.000, 0.000] | 8.471 |
| Brentford | 1315 | 8.963 | 8.857 | 8.857 | 18.284 | -0.129 | 0.05676 | 0.18851 | -0.000 [-0.000, 0.000] | 8.722 |
| Sunderland | 1589 | 7.755 | 7.585 | 7.585 | 16.925 | -0.350 | 0.04714 | 0.15770 | 0.000 [-0.000, 0.000] | 7.176 |
| Bournemouth | 1410 | 7.479 | 7.395 | 7.395 | 16.051 | -0.381 | 0.05172 | 0.16993 | -0.000 [-0.000, 0.000] | 7.302 |

### Spillergrupper (samme primære fejldefinition)

| Gruppe | N | Original MAE | Rolle MAE | News MAE | Chance+duration MAE | News RMSE | News Brier | News logloss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| player_type:regular | 3148 | 13.962 | 13.780 | 13.780 | 13.366 | 23.265 | 0.07990 | 0.28651 |
| player_type:rotation_or_short_history | 6718 | 21.311 | 21.253 | 21.253 | 20.818 | 29.304 | 0.14863 | 0.46785 |
| player_type:reserve | 16293 | 5.427 | 5.251 | 5.251 | 5.216 | 14.317 | 0.03467 | 0.11850 |
| news_medical_return:True | 271 | 22.387 | 22.796 | 22.796 | 21.794 | 34.050 | 0.17784 | 0.59140 |
| news_medical_out:True | 1846 | 2.045 | 0.268 | 0.268 | 0.268 | 4.184 | 0.00217 | 0.05987 |
| news_eligible:True | 26074 | 10.543 | 10.399 | 10.399 | 10.214 | 20.347 | 0.06953 | 0.22873 |
| news_eligible:False | 85 | 7.430 | 6.832 | 6.832 | 6.919 | 14.428 | 0.02347 | 0.13715 |

Gruppemetrics, bias og parrede primær-vs-rolle-intervaller findes også i report.json; små grupper skal fortolkes med ekstra varsomhed.

### Haaland, Palmer og João Pedro

| Spiller | N | Original MAE | Rolle MAE | News MAE | Chance MAE | Chance+duration MAE | Original bias | Kombination bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Erling Haaland | 33 | 22.405 | 23.029 | 23.029 | 22.973 | 22.973 | -1.210 | -2.513 |
| Cole Palmer | 33 | 20.776 | 19.492 | 19.492 | 19.411 | 19.411 | -7.989 | -10.167 |
| João Pedro Junqueira de Jesus | 33 | 23.611 | 23.713 | 23.713 | 23.641 | 23.641 | 2.153 | 1.372 |

Dette er fejl over de historiske evalueringskampe, ikke et nyt liveforecast eller en manuel korrektion af bestemte spillere.

### Svageste komponenter

| Komponent | Original MAE-attribution | Rolle | News | Chance+duration |
| --- | --- | --- | --- | --- |
| start_selection | 7.369 | 7.457 | 7.457 | 7.354 |
| starter_duration | 1.557 | 1.522 | 1.522 | 1.497 |
| cameo_selection | 0.982 | 0.798 | 0.798 | 0.746 |
| cameo_duration | 0.625 | 0.610 | 0.610 | 0.606 |

Eksakt algebraisk Shapley-fordeling af absolut minutfejl: komponenterne summerer til MAE, men er ikke kausale skades-/taktikforklaringer. Startudvælgelse er den største fejlkomponent; kildeudfaldskonflikter og ukendt kampklarhed består. 16 evaluerede medicinske OUT-rækker havde faktisk kampdeltagelse. Disse labels bevares; de omskrives ikke med fremtidsviden.

### Største individuelle primærfejl

| Spiller | GW | Faktiske min | Forventede min | P(start) | News | Diagnose |
| --- | --- | --- | --- | --- | --- | --- |
| Matz Sels | 28 | 90.0 | 0.000 | 0.000 | OUT | source_outcome_conflict |
| Anton Stach | 14 | 90.0 | 0.000 | 0.000 | OUT | source_outcome_conflict |
| Maxime Esteve | 21 | 90.0 | 0.000 | 0.000 | OUT | source_outcome_conflict |
| Dennis Cirkin | 18 | 90.0 | 0.424 | 0.005 | AVAILABLE | start_selection_error |
| Rio Cardines | 38 | 90.0 | 0.599 | 0.007 | AVAILABLE | start_selection_error |
| Stefan Ortega Moreno | 25 | 90.0 | 0.629 | 0.008 | AVAILABLE | start_selection_error |
| Melker Ellborg | 29 | 90.0 | 0.650 | 0.008 | AVAILABLE | start_selection_error |
| Senne Lammens | 7 | 90.0 | 0.705 | 0.008 | AVAILABLE | start_selection_error |
| Benjamin White | 14 | 90.0 | 0.871 | 0.011 | AVAILABLE | start_selection_error |
| Ethan Pinnock | 31 | 90.0 | 0.936 | 0.012 | AVAILABLE | start_selection_error |

De 30 største fejl pr. sæson og præcise fixture-/spiller-ID’er, cutoff, kilde og alle komponenter findes i report.json. “duration_error_unverified_cause” betyder, at årsagen ikke er dokumenteret, ikke at en taktisk udskiftning/skade er bevist.

## Kildedækning pr. klub – hele GW6–38-kataloget

| Sæson | Klub | Forecast N | Strengt matchede | Dækning | Medicinske OUT-rækker | Episoder | Selection-returer | Træningsudsagn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | Arsenal | 1110 | 1104 | 99.46% | 124 | 17 | 12 | 0 |
| 2024-25 | Aston Villa | 1325 | 1323 | 99.85% | 37 | 18 | 14 | 0 |
| 2024-25 | Bournemouth | 1190 | 1182 | 99.33% | 129 | 17 | 12 | 0 |
| 2024-25 | Brentford | 1193 | 1188 | 99.58% | 147 | 19 | 16 | 0 |
| 2024-25 | Brighton | 1575 | 1567 | 99.49% | 122 | 22 | 17 | 0 |
| 2024-25 | Chelsea | 1443 | 1436 | 99.51% | 96 | 16 | 14 | 0 |
| 2024-25 | Crystal Palace | 1129 | 1127 | 99.82% | 96 | 19 | 15 | 0 |
| 2024-25 | Everton | 1051 | 1043 | 99.24% | 124 | 19 | 14 | 0 |
| 2024-25 | Fulham | 997 | 996 | 99.90% | 79 | 15 | 11 | 0 |
| 2024-25 | Ipswich | 1165 | 1163 | 99.83% | 127 | 25 | 18 | 0 |
| 2024-25 | Leicester | 1172 | 1166 | 99.49% | 92 | 15 | 11 | 0 |
| 2024-25 | Liverpool | 1092 | 1088 | 99.63% | 60 | 13 | 13 | 0 |
| 2024-25 | Man City | 1115 | 1109 | 99.46% | 108 | 19 | 18 | 0 |
| 2024-25 | Man Utd | 1214 | 1203 | 99.09% | 97 | 23 | 21 | 0 |
| 2024-25 | Newcastle | 1100 | 1099 | 99.91% | 98 | 14 | 12 | 0 |
| 2024-25 | Nott'm Forest | 1113 | 1111 | 99.82% | 35 | 7 | 6 | 0 |
| 2024-25 | Southampton | 1291 | 1287 | 99.69% | 79 | 22 | 21 | 0 |
| 2024-25 | Spurs | 1410 | 1403 | 99.50% | 138 | 27 | 22 | 0 |
| 2024-25 | West Ham | 996 | 993 | 99.70% | 58 | 7 | 5 | 0 |
| 2024-25 | Wolves | 1391 | 1386 | 99.64% | 150 | 15 | 10 | 0 |
| 2025-26 | Arsenal | 1179 | 1178 | 99.92% | 86 | 14 | 11 | 0 |
| 2025-26 | Aston Villa | 1513 | 1508 | 99.67% | 82 | 18 | 16 | 0 |
| 2025-26 | Burnley | 1417 | 1414 | 99.79% | 142 | 12 | 9 | 0 |
| 2025-26 | Bournemouth | 1410 | 1407 | 99.79% | 97 | 18 | 17 | 0 |
| 2025-26 | Brentford | 1315 | 1309 | 99.54% | 99 | 12 | 9 | 0 |
| 2025-26 | Brighton | 1491 | 1487 | 99.73% | 107 | 14 | 10 | 0 |
| 2025-26 | Chelsea | 1205 | 1197 | 99.34% | 91 | 25 | 24 | 0 |
| 2025-26 | Crystal Palace | 1350 | 1345 | 99.63% | 130 | 24 | 19 | 0 |
| 2025-26 | Everton | 1189 | 1188 | 99.92% | 63 | 11 | 9 | 0 |
| 2025-26 | Fulham | 998 | 996 | 99.80% | 59 | 20 | 18 | 0 |
| 2025-26 | Leeds | 1166 | 1162 | 99.66% | 55 | 23 | 19 | 0 |
| 2025-26 | Liverpool | 1217 | 1213 | 99.67% | 190 | 23 | 16 | 0 |
| 2025-26 | Man City | 1221 | 1217 | 99.67% | 89 | 18 | 17 | 0 |
| 2025-26 | Man Utd | 1382 | 1377 | 99.64% | 67 | 14 | 13 | 0 |
| 2025-26 | Newcastle | 1258 | 1255 | 99.76% | 117 | 22 | 17 | 0 |
| 2025-26 | Nott'm Forest | 1256 | 1253 | 99.76% | 124 | 18 | 13 | 0 |
| 2025-26 | Sunderland | 1589 | 1585 | 99.75% | 111 | 21 | 17 | 0 |
| 2025-26 | Spurs | 1400 | 1394 | 99.57% | 191 | 26 | 20 | 0 |
| 2025-26 | West Ham | 1264 | 1258 | 99.53% | 30 | 10 | 9 | 0 |
| 2025-26 | Wolves | 1339 | 1331 | 99.40% | 85 | 14 | 11 | 0 |

## Reproduktion, tests og godkendelsesgrænse

28 relevante regressionstests bestået lokalt; samme tests køres i den dedikerede MM-workflow. Testene dækker kildeklokker, deadline-lighed, klubskifte, identiteter, eksplicit skadetekst, ukendte datoer, træning versus raskmelding, latent rollepersistens, fremmødeloft uden dobbeltregning, målmand/markspiller-projektion, parrede cohorts og eksakt fejlidentitet. Produktionsmappen `src/fpl_v1_1_model` er uændret mod PR #8-start `4f34321`.

```sh
PYTHONPATH=src:scripts:. python -m pytest tests/test_mm_role_injury_integration.py tests/test_research_role_injury_club_audit.py tests/test_team_news_history.py tests/test_team_news_audit.py -q
git fetch origin 6d875a65251fb62f691dc0386ea81aeb29d27c0f
PYTHONPATH=src:scripts python scripts/restore_role_mm_source.py
python scripts/restore_core_checkpoint.py
python scripts/restore_team_news_audit.py
python scripts/archive_role_injury_mm.py --restore work/permanent-mm-evidence
cp -r work/permanent-mm-evidence/news-2024 work/news-2024-push-verified
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/validate_role_injury_mm.py
```

Det permanente allowlistede MM-checkpoint ligger i `checkpoints/role_injury_mm_20261016/`. Manifestet indeholder kodecommit, alle part-/ZIP-/medlemchecksums og kildeledger. Det indeholder de frosne MM-inputs, kildebekræftede news, normalrolleprofiler, evaluation-only returobservationer, taktiske labels og alle MM-predictions. Ingen privat manager-state, købspriser, PM-outputs eller tokens. Workflowet genafspiller fra dette checkpoint og afhænger ikke af udløbende Actions-artifacts.

Før integration i appen mangler en ny, ubrugt/prospektiv evalueringsperiode, kalibrering af FPL-spillechance som tilgængelighedsinput, verificerede medicinske/træningsreturer og bedre historiske outcome-publiceringstider. Retur-duration-gevinsten skal bekræftes uden post hoc-modelvalg. Den eksisterende låste MM og alle andre modeller forbliver uændrede. Ingen PM/TS-effekt eller FPL-pointgevinst påstås.

## Verificerede workflowkørsler og eksakt reproduktion

- [Indsamling af 2024/25-kilder](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38921917263): bestået.
- [Uafhængig genverificering af kildeklokker og fuld 13-arm-MM](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38924972037): bestået.
- [Fuld 13-arm-MM fra permanent checkpoint](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38925148538): bestået, inklusive 28 tests, produktionskodekontrol, pakning/genindlæsning og GitHub-publicering af forskningsdata. Kodecommit `ef6cea3f3f38527fd5bc1dbcd9e2afc230321dad`.
- Alle ti resultatfiler er lokalt byte-identiske med den checksum-verificerede CI-kapsel, inklusive alle predictions, normalrolleprofiler og taktiske profiler. Se `analysis/results/role-injury-mm-20261016/reproduction.json`. ZIP-manifestets kodecommit identificerer den præcise kørsel, også hvis et senere identisk numerisk replay har en anden workflowcommit.

Kildekvalitet er kategorisk, ikke en opfundet sandsynlighed: råteksten er officiel FPL-information, den konkrete arkivversion og dens historiske eksistens er verificeret med hashes og klokker, mens klinisk diagnose, præcis skadestart og medicinsk kampklarhed fortsat er ukendte. `identity_status`, `timing_verified`, `deadline_matches`, `source`, `timestamp_basis` og de rå status-/news-felter følger hver observation. Normalroller er modelestimater med historisk as-of og må ikke læses som trænerudsagn.
