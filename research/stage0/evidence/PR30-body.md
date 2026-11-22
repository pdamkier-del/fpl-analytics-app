Fortsætter fra PR #29 på `c18cfa4b` med en isoleret B-kandidat. Skadesreturer adskilles fra suspensionsreturer via verificerede, frosne predeadline-features. Lovlige XI-vægte kan ændres inden for de eksisterende P(spil)-lofter; udskiftningsprioritet/P(90) testes separat og kombineret.

**Beskyttet:** produktion, B-appkode, modelartefakter, publiceringsworkflows og TS v3 er uændrede. Ingen aktivering, deployment eller merge. Kun analyse, regressionstests og isoleret CI er tilføjet; auditworkflowets allowlist tillader præcis det nye analyseworkflow.

**Validering:** 60 lokale kandidat-/fysik-/GK-/event-/pointtests består. Den oprindelige audit-CI består på den nye branch, inkl. baseline, alle otte oracle-arme, frosne beslutninger og prospektiv hashkæde. Fuld analytisk før/efter-kørsel på de 341 historiske kampe er stadig i gang; rapporten færdiggøres efter den.

**Afgrænsede lokale xP-kontroller:** alle fire historiske MC-kampe fra #29, 2.000 draws × to nye seeds × seks arms (96.000 simulerede kampe). Gennemsnitlig spiller-xP-MAE:

| Sæson | baseline | return_start | return_start_p90 |
| --- | --- | --- | --- |
| 2024/25 | 0,854680 | 0,853718 | 0,854377 |
| 2025/26 | 0,923218 | 0,921429 | 0,922667 |

Fire kampe og små forskelle er ikke dokumentation for generel xP-forbedring. Minut-/P(90)-kontrollerne viser også tradeoffs; ingen kandidat er godkendt til aktivering. Begge historiske sæsoner er genbrugte forskningsperioder.

[Aggregerede kontrolmålinger og hashes](https://github.com/pdamkier-del/fpl-analytics-app/tree/improve-b-return-p90-20261101/analysis/results/return-p90-candidate-20261101). PR'en publicerer aggregerede metrics og manifests; rå spillerbaserede outputs tilføjes ikke.
