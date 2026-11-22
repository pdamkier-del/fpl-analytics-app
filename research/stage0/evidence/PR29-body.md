Denne audit måler, hvor den eksisterende MM → PM → TS-kæde mister præcision, uden at ændre app, produktion, låst PM, TS v3 eller den nuværende B-preview.

[Samlet rapport](https://github.com/pdamkier-del/fpl-analytics-app/blob/audit-systematic-precision-20261101/docs/2026-11-01-systematic-precision-audit.md) · [Reproduktion](https://github.com/pdamkier-del/fpl-analytics-app/blob/audit-systematic-precision-20261101/analysis/precision_audit/README.md) · [Frosne resultater](https://github.com/pdamkier-del/fpl-analytics-app/tree/audit-systematic-precision-20261101/analysis/results/systematic-precision-audit-20261101)

- 341 historiske kampe / 27.092 spillerobservationer, 48 fælles oracle-kampe, alle otte M/S/G-kombinationer, 14 MC-kampe × seks seeds ved 400/2.000/10.000 draws; i alt 1.710.000 simulerede kampe.
- Returspillere undervurderes cirka 7–8 minutter; stamspilleres P(90) overvurderes. 400-draws-støj kan ændre tætte beslutninger. Penders og Le Fée er opdelt i pointkomponenter.
- Tre historiske konstruerede holdtilstande / seks FT-cases: intet fundet pruning-tab i det afgrænsede univers, én 0,18 xP-gevinst fra fælles XI/bænk/C/VC. Praktisk forekomst af negative finansieringsben og fuld seks-GW-policy-performance kan ikke estimeres med de foreliggende input.
- Perioderne er genbrugt forskningsdata; 2024/25 NP-parametre er trænet senere. Ingen påstand om uafhængigt dokumenteret præcisionsløft. Første ægte predeadline GW10–15-forecast er låst med offentlig hashkæde og frosne evalueringsregler.

Validering: 42 relevante lokale tests består; eksakt publiceret B-replay (maksimal xP-afvigelse 0), historisk beslutningsreplay, kildeisolering, SHA-manifest og separat CI-smoke med baseline + alle oracle-arms. Hele numeriske audit er kørt lokalt; CI er eksplicit et afgrænset replay. Ingen publicering eller modelaktivering i denne PR.

Afsluttende CI på `c18cfa4b`: **bestået** — https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/41304444696. Den uafhængige baseline-/oracle-genkørsel matcher de gemte draw-resultater; alle seks historiske beslutningscases og hele evidensmanifestet er verificeret.
