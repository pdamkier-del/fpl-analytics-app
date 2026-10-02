# Conditional-minutes v1 — isoleret frosset OOS

Bygget **efter** den reproducerbare role-foundation. Role-aware P(start) holdes
uændret. App/UI er ikke ændret; modellen er eksperimentel og ikke promoveret.

## Definition og protokol

`src/fpl_v1_1_model/minutes_decomposition.py` fitter tre separate komponenter:

- E[min|start]: standardiseret Ridge, alpha=20, clip 0–90.
- P(sub appearance|not start): standardiseret logistic, C=1.
- E[min|sub appearance]: standardiseret Ridge, alpha=20, clip 0–90.

Alle fits bruger samme GW6–21-labels kendt før GW22-cutoff som role-modellen:
3.520 starts, 8.652 nonstarts, 1.332 af disse med sub appearance. Koefficienter
fryses gennem GW22–38. Hyperparametre er faste, ikke tunet på holdout.

Input er V2's historiske conditional-minutes-estimater, cutoff-safe q/H-summary
features, tidligere start, FPL-position og **historisk forventet** fine role.
Target-rolle, target-lineup, actuals og in-sample-fittet role-P(start) er ikke
inputs til komponenternes træning. P(start) bruges kun i den endelige identitet.

På den faste benchmark-roster betyder 'bench' alle ikke-startende spillere,
**også spillere uden for den faktiske matchday-squad**. Den præcise betegnelse
er derfor P(appearance|not start), ikke P(appearance|confirmed matchday bench).
Modellen forudsiger endnu ikke matchday-squad-selection/availability separat.
Bench-listen i raw lineups er historisk outcome, ikke kendt ved forecastcutoff.

Identiteten på denne population er:

E[min] = P(start) × E[min|start]
       + (1 − P(start)) × P(sub appearance|not start) × E[min|sub appearance].

Alle minutter/probabiliteter er begrænsede og finite. Flydende afrundingsstøj
omkring 90 minutter accepteres inden for 1e-9, ikke reelle værdier over 90.
De tidligere dokumenterede cutoff/publication-proxies gælder også her.

## Resultat, GW22–38, samme 13.987 rækker

| Variant | Brier | Log-loss | xMins MAE | xMins RMSE |
|---|---:|---:|---:|---:|
| V2 baseline | 0,077148 | 0,257716 | 11,958642 | 21,922479 |
| Role-aware + gamle duration/sub-komponenter | 0,076645 | 0,251343 | 11,823680 | 21,858693 |
| Kun ny E[min|start] | 0,076645 | 0,251343 | 12,124040 | 21,786863 |
| Kun ny P(sub|not start) | 0,076645 | 0,251343 | 12,138721 | 21,890124 |
| Kun ny E[min|sub] | 0,076645 | 0,251343 | 11,922438 | 21,786995 |
| Alle tre nye komponenter | 0,076645 | 0,251343 | 12,470570 | 21,729419 |

Start-målene er identiske ved design. Full decomposition sænker RMSE med
0,129274 mod role-aware, men **øger MAE med 0,646890**. Ingen ablation vælges
som 'vinder' på denne holdout; alle prædefinerede ændringer er gemt.

## Separate komponenter

| Conditional mål | n | Gammel | Ny |
|---|---:|---:|---:|
| Start-duration MAE | 3.740 | 7,810422 | 7,684866 |
| Start-duration RMSE | 3.740 | 14,374910 | 11,755518 |
| Sub-duration MAE | 1.377 | 13,568324 | 10,944070 |
| Sub-duration RMSE | 1.377 | 18,441473 | 13,919005 |
| Appearance-given-nonstart Brier | 10.247 | 0,086339 | 0,078578 |
| Appearance-given-nonstart log-loss | 10.247 | 0,506460 | 0,258740 |

Alle tre komponenter forbedrer deres direkte holdout-mål, men det er **ikke**
tilstrækkeligt til at forbedre den sammensatte minutes-MAE. Sammensætningen
afhænger også af start-probabilitetsfejl og korrelation med duration-estimater.
Desuden er en conditional mean/MSE-model ikke en conditional median/MAE-model;
for en population med mange nulminutter kan højere forventede minutter øge
absolutte fejl, selv om proper probability loss/RMSE forbedres. Det er en
mulig mekanisme, ikke et bevist enkelt-årsagssvar.

Konkrete posthoc-grupper, role-aware→full decomposition:

- Ingen appearance, n=8.870: MAE 6,390724→7,103090.
- Actual start, n=3.740: MAE 21,851569→22,690331.
- Actual sub appearance, n=1.377: MAE 19,584048→19,288032.
- Target-role disagreement, n=541: MAE 22,674551→23,827991;
  RMSE 30,964188→30,881543.
- Historisk disagreement, n=4.184: MAE 20,816397→21,841291.
- Role-change ≥5pp, n=1.994: MAE 26,546922→26,931741.

Der er dermed **ikke** evidens for, at denne første decomposition løser de
high-impact/disagreement xMins-problemer. Der er heller ikke basis for at
overskrive den fungerende app-model med den.

## Reproduktion/artefakter

```bash
python scripts/build_reproducible_role_benchmark.py --db work/core.sqlite3
python scripts/benchmark_minutes_decomposition.py
python scripts/run_model_checks.py
```

`analysis/results/minutes-decomposition-v1/` indeholder permanent holdout-CSV
med de fulde q/H/role-features og alle tre komponenter, immutable P(start),
actuals og ablations; metrics pr. GW/hold/expected fine-role/disagreement/
actual-event; komponent-metrics; alle modeller/scalers/koefficienter; protokol
og input/code/output-checksums. Foundation-checkpointet ligger fortsat separat.

34 assertion-tests passerer samlet. En separat genkørsel genskaber alle ti
genererede minutes-artefakter byte-identisk; alle output-checksums passer.
Den samlede model er ikke fuldt etableret
til en ny officiel sæsonsimulering: squad/availability-semantik, duration-
composition, uafhængig OOS, workload/cups/Europe og senere Match Importance
mangler stadig. Der er ikke begyndt på importance/cup-value eller tunet efter
den gamle MAE 11,64. Næste modelvalg bør besluttes ud fra udviklingsvalidering
og en ny, uafhængig testperiode, ikke genbrug af GW22–38 som tuning-set.
