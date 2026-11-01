# B-rettelser publiceret og kontrolleret — 1. november 2026

Den eksisterende FPL-app har den nye B-model. Produktionsmodellen og låste benchmarks er bevaret.

**App:** https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/overview.html#dashboard

**Numerisk kilde:** `161b67b6fb8786a38e78c245b92a03ad841575d8`. PR #22 er fortsat åben; ingen produktionsmerge.

## Implementeret

- Vedvarende utilgængelighed i alle positioner og seks GW; 106 aktuelle status-u-spillere har 0 minutter og 0 xP gennem GW10–15. Dokumenterede salg/sæsonudlån holdes adskilt fra uklar utilgængelighed.
- Samme fysiske features i træning og prognose, med verificerede cup-/UEFA-minutter og indskiftninger. PL-rollehistorik er separat.
- Daterede skadesreturer bruges som usikre returforløb. Træningslabel er første registrerede PL-optræden, ikke lægelig clearing.
- Selvmål indgår i fælles resultat, indkasserede mål, clean sheets, point og BPS. Almindelige mål kræver en gyldig scorer. Straffebudgettet følger den aktive skytte; denne betingede konvertering fandtes allerede i B og er bevaret.
- Modelforklaringen beskriver de nye kilder og hændelser og linker til den publicerede kildeversion.

## Verifikation

- 1.111 Python-tests og 31 JavaScript-tests bestået.
- 341 historiske kampe, 27.092 spiller-kamp-rækker pr. arm, 400 simuleringer. Tidligere B reproduceret med maksimal xP-afvigelse 0.
- Én kamp og én GW matcher seks-GW-kørslen; genkørslen er byte-identisk. Syntetisk TS/chip-test gennemført uden at ændre manager-state.
- Direkte offentlig browserkontrol på mobil og desktop: samme prognose i profiler og planner, MM=PM forventede minutter, sandsynlighedskort, fem MathML-felter, ingen sidefejl eller vandret overflow, ingen rigtige private plan-POSTs.
- Publiceringsbevis: 88 produktionsfiler bevaret byte for byte. Otte repræsentative produktionsfiler kontrolleret direkte over HTTP er også identiske.

## Historiske resultater

| Sæson | Start-Brier før → efter | Minut-MAE før → efter | xP-MAE før → efter | xP-bias før → efter |
|---|---:|---:|---:|---:|
| 2024-25 | 0.072177 → 0.072112 | 10.91986 → 10.88206 | 0.890843 → 0.889531 | +0.003916 → -0.004085 |
| 2025-26 | 0.067899 → 0.068008 | 10.29107 → 10.29447 | 0.875883 → 0.873200 | +0.023739 → +0.014967 |

Gevinsten er lille og blandet. Første sæsons xP-MAE-interval omfatter ingen forbedring. Perioderne er genbrugte forskningsperioder. Minut- og startfejl stiger lidt i anden sæson. Målscorer-bias forbedres, mens absolut assist-bias bliver lidt dårligere. Ingen vilkårlig nedjustering af navngivne spillere er aktiveret.

## Offentlig før/efter-kontrol

GW10. Samme officielle kilder før/efter. Datagrundlag: 01.11.2026 kl. 07.20 dansk tid. Tabellen er et dateret snapshot; appen fortsætter automatiske opdateringer. xP-forskelle omfatter ændret Monte Carlo-rækkefølge.

| Spiller | Arm | P(start) | xM = PM E[min] | P(60+) | P(90) | xP |
|---|---|---:|---:|---:|---:|---:|
| Penders | Før | 95.49% | 85.75 | 95.18% | 94.86% | 3.1125 |
| Penders | Efter | 95.49% | 85.75 | 95.18% | 94.86% | 2.7350 |
| E.Le Fée | Før | 96.98% | 86.58 | 96.31% | 91.23% | 3.9500 |
| E.Le Fée | Efter | 96.75% | 86.36 | 96.12% | 90.94% | 4.2300 |

Penders’ startchance er uændret i denne rettelse. Hans forventede minutter afspejler risikoen for ikke at starte; han forventes at spille næsten 90 minutter, når han starter.

## Undersøgt og bevaret

- Fast G/xG-korrektion forbedrede ikke holdmålsmodellen stabilt og blev ikke aktiveret.
- TS-finansiering og fælles XI/bench/C/VC kan overse bedre kombinationer i afgrænsede eksempler. Den låste TSv3 er bevaret; der er ikke dokumenteret en generel gevinst ved en ny søgning.
- Kommende kampprioritet er neutral, da en egnet historisk kalender med korrekte kildetider ikke blev etableret.
- Historisk cupdækning er delvis og bruger dokumenterede tidsproxyer. Særlige penalty-winner-/selvmåls-assistregler er testet, men deres forekomstmodel mangler fortsat kalibreret evidens. Tidslinjen modellerer ikke fjernelse ved røde kort.

## Links

- PR: https://github.com/pdamkier-del/fpl-analytics-app/pull/22
- Fuld numerisk CI: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41216503954
- Første publicering: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41223882607
- Kontrolleret automatisk opdatering: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41278968979
- [Historisk rapport](../../analysis/results/integrated-repair-20261031/README.md)
- [Offentlig før/efter-data](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/gk/repair-comparison.json)
- [Offentligt produktionsbevis](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/publication.json)
- Browser- og publiceringsbeviser: [evidensmappe](integrated-repair-live-20261101).
