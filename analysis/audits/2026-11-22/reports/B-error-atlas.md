# B. Error Atlas

Kilde: oprindelige GW8–10-forecasts, 2.007 rækker, 30 kampe. Positiv bias betyder overvurdering. Alle dimensioner findes i `../results/error-atlas.csv`; 58 grupper, plus alle individuelle spillere i `player-error-atlas.csv`. Cutoff-stemplet rolle/status og pris bruges til gruppering. Ingen nutidige trænernyheder er lagt tilbage i en gammel prognose.

## Klub

Hver klub har blot tre kampe. N er antal registrerede spiller/GW-rækker, ikke antal uafhængige kampe. Der gives ingen signifikansrangering af klubberne.

| Klub | N | Kampe | Minut-MAE | xP-MAE | xP-bias |
| --- | --- | --- | --- | --- | --- |
| Bournemouth | 87 | 3 | 7.10 | 1.34 | -0.601 |
| Arsenal | 87 | 3 | 14.76 | 1.52 | -0.565 |
| Leeds | 93 | 3 | 14.08 | 1.19 | -0.274 |
| Liverpool | 108 | 3 | 8.07 | 0.95 | -0.239 |
| Spurs | 120 | 3 | 7.55 | 0.88 | -0.224 |
| Everton | 75 | 3 | 14.12 | 1.26 | -0.183 |
| Newcastle | 102 | 3 | 17.93 | 1.13 | -0.172 |
| Brighton | 111 | 3 | 8.24 | 1.10 | -0.159 |
| Sunderland | 93 | 3 | 15.74 | 1.24 | -0.141 |
| Aston Villa | 108 | 3 | 12.13 | 1.05 | -0.125 |
| Hull City | 129 | 3 | 10.21 | 0.72 | -0.026 |
| Fulham | 84 | 3 | 7.13 | 1.14 | +0.011 |
| Brentford | 87 | 3 | 12.23 | 1.09 | +0.087 |
| Chelsea | 105 | 3 | 10.74 | 1.06 | +0.174 |
| Coventry City | 111 | 3 | 11.56 | 0.80 | +0.175 |
| Ipswich Town | 108 | 3 | 8.78 | 0.80 | +0.206 |
| Nott'm Forest | 90 | 3 | 12.49 | 1.16 | +0.433 |
| Man Utd | 102 | 3 | 11.64 | 1.10 | +0.462 |
| Crystal Palace | 108 | 3 | 14.20 | 0.78 | +0.477 |
| Man City | 99 | 3 | 11.62 | 0.84 | +0.544 |

## Roller, stjerner, status og position

| Startrolle | N | Minut-MAE | P(start)-Brier | xP-bias |
| --- | --- | --- | --- | --- |
| low_start | 1152 | 4.71 | 0.0228 | +0.004 |
| regular | 337 | 11.24 | 0.0536 | -0.054 |
| rotation | 518 | 26.42 | 0.1923 | +0.029 |

Pris ≥£9m definerer en prædeadline-premiumgruppe: 15 rækker og minut-MAE 15,56. Det er for lidt til at erklære en særlig stjernefejl. Arkiveret `normal_role` er en anden dimension end P(start)-gruppen: `rotation_or_short_history` har 510 rækker og minut-MAE 21,46; `regular` 329 rækker/11,60. De må ikke sammenblandes.

`DOUBT` har 67 rækker og minut-MAE 23,34; `OUT` 508 rækker og MAE 0,081. Det viser stor forskel i usikkerhed, men identificerer ikke særskilt skadestilbagevenden, skadetype eller medicinsk clearance. Målmænds lave all-player-minutfejl skal læses sammen med den store reservegruppe. Positionsvise scores og kalibrering står i CSV-filerne.

## Fejlmekanismer og observationsstyrke

| Fejltype | Evidens | Vurdering |
| --- | --- | --- |
| Få forventede indskiftninger / høj P90 | GW9–10 tællingsaudit + fysisk identitet | Konkret mekanisme; kandidat kræver ny fremadrettet test |
| Uventet start/bench blandt rotationsspillere | Høj minutfejl, startandele tættere på faktiske | Stor usikkerhed; ikke hver forkert start er forkert sandsynlighed |
| Minutter og pointfejl følges | r=0,464 signeret | Sammenhæng, ikke kausal gevinst |
| DEF DC / GK bonus for lavt | Positionsvise komponenttotaler | Tre runder; scoringsreglerne er verificeret korrekte |
| MID bonus/DC og dele af angrebet højt | Komponentfejl, share-bins, historiske budget-ablationer | Hypotese; ingen generel multiplikator dokumenteret |
| Mål-/CS-fejl udligner hinanden | Angrebs- og CS-komponenter | Samlet bias alene skjuler fejl |
| Europa/cup/rotation efter belastning | Eksisterende eksperiment; historiske tidsstempler ufuldstændige | Kan ikke få et nyt cutoff-certificeret effektmål her |
| Udskiftningstid og skadeårsag | Kun rapporterede minutter og statusproxy | Ikke tilgængelig som præcis hændelseslabel |

## Spillerfejl uden hindsight-udvælgelse

CSV'en indeholder alle spillere, ikke kun dem der fik de største fejl. Hver har højst tre målinger i denne periode. Der findes ingen stabil individuel korrektion ud fra dette materiale alene. Store afvigelser bør undersøges med startrolle, minutfejl og kendt hændelsesrealisering, ikke forklares med efterfølgende artikler.

Kalibrering med ti sandsynlighedsbånd findes i `calibration.csv`; intervalmål i `uncertainty.csv`. Klub-, spiller- og mange statusgrupper har for få kampe til meningsfulde individuelle konfidensintervaller. Manglende kup-/skadefelter er eksplicitte datagab og sættes ikke til “ingen belastning” eller “rask”.
