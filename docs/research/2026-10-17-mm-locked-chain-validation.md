# Final MM integration round: verified scope and remaining gates

Status: **NOT READY** for the requested live MM → PM → TS activation.

The historical preview and isolated current entry point are functional. This is
not a claim that a verified current B feature producer, candidate backend route
or a real personal six-GW calculation has been completed. No new MM specification or hyperparameters were selected in this round. The
existing fixed B calibrator is refitted chronologically at the same50 origins. Production remains unchanged; locked_model_active=false.

## Reused architecture

- PR9 model B: fixed alpha10/C=.1 standardized logistic calibration, original
  role/chance/return-duration inputs and exact GK/outfield cap projection.
- PR11: prior-only formation/role compatibility selects expected XI. It does
  not nudge B's calibrated marginal start probabilities.
- PR13/15: experimental 91-point duration PMF, four bands and shortest intervals,
  with expectation agreement within 1e-6. This PMF does not replace the locked
  PM's original duration sampler.
- Original vFinal simulator: unchanged goals, assists, penalties, own goals,
  clean sheets, DefCon, BPS, bonus, scoring rules and on-pitch propensities.
- Original TS/chips: unchanged six-GW weights, search, hit buffer and coordinator.

xM = p s + (1-p) q c. The PM bridge changes only the five candidate minute
columns (p, q, s, c and their derived xM). Its original control exposure is
preserved because the original adapter derives goal/assist/DefCon propensities
from that exposure. A second check inspects the final simulator object: all
non-minute inputs must remain identical. Points are simulated again, not scaled
in JavaScript. Expected XI is a point summary, not a replacement for marginals
or for the locked PM's sampler.

## Repeated historical MM test

39,264 matched predictions, 2024/25 GW22–38 and 2025/26 GW6–38. All are reused
research periods. B_XI, B_PMF and combined retain exactly B's marginal outputs.

| Arm | MAE | RMSE | Start Brier | Errors >60 min |
|---|---:|---:|---:|---:|
| original | 11.240711 | 21.115962 | 0.073445 | 1559 |
| best_existing | 10.521392 | 20.416725 | 0.070115 | 1362 |
| B | 10.408358 | 20.172026 | 0.068827 | 1278 |
| combined | 10.408358 | 20.172026 | 0.068827 | 1278 |

B absolute-error median/P90/P95/P99: 1.965745, 34.839239, 50.723173,
77.990725 minutes. Worst5%/10% contribute 32.060% /
52.231% of total absolute error. Full error bands,
top100, per-club/season, role, calibration and XI tables remain in
`analysis/results/mm-integration-preview-20261017/`. Additional per-GW/club
metrics and zero-filled 0/11–11/11 hit counts are exported in this round.

On 660 eligible 2025/26 team-fixtures, expected XI has 101 exact11 results
(15.303%) and 43.939% with at least10 correct. There is no equivalent verified
2024/25 formation ledger. The small mean XI-hit gain is not independently
established; see the existing paired intervals, not just point percentages.

PMF CRPS 6.656089854, minute log-loss
1.562013316. The earlier 80% equal-tail interval covers
about90.6%; shortest80 covers about87.7% and contains about92.3% model mass on
average. Discrete mass is not independent calibration evidence. Mean repair
slightly worsens CRPS/log-loss versus PR13. PMF remains experimental.

## Actual B → locked PM replay

11,794 matched player-fixtures, 144 fixtures,
2025/26 GW22–38, 400 draws per fixture, seeds93000000+fixture-index.
2,193 B rows lie outside the frozen PM universe and are
explicitly excluded. No full-universe PM claim is made. The earlier vFinal
minute inputs are the matched historical comparator, not today's live model.
One complete paired fixture is rerun exactly. Same seed/budget does not mean
event-aligned common random numbers after stochastic branches diverge.

| Matched historical arm | xP MAE | xP RMSE | Bias |
|---|---:|---:|---:|
| Frozen vFinal minutes | 0.918241 | 1.845620 | 0.017725 |
| B minutes → same PM | 0.881045 | 1.811052 | 0.014766 |

Paired four-GW circular-block95% intervals, 1000 fixed-seed resamples:
MAE delta [-0.045809260862540835, -0.0276149490817402]; RMSE delta
[-0.045844565604585344, -0.023318951590036413]. These quantify temporal sampling
variation conditional on the frozen reused dataset and one simulation seed.
They do not independently quantify Monte Carlo uncertainty or fix historical
source certification. No PM/TS parameters were optimized against these results.

Illustrations (historical fixtures, not current advice):

| Player | GW | Old xM | B xM | Old xP | B→PM xP |
|---|---:|---:|---:|---:|---:|
| Haaland | 22 | 82.5948 | 81.3911 | 4.6200 | 4.4725 |
| Saka | 22 | 66.5333 | 66.6895 | 4.1650 | 3.9750 |
| Palmer | 24 | 55.4613 | 56.9454 | 3.0275 | 3.4425 |
| João Pedro Junqueira de Jesus | 24 | 77.6622 | 75.5245 | 4.8375 | 5.0150 |

Historical GW7 João Pedro Junqueira de Jesus has B p=.965522 and xM=87.142189.
The different identity João Pedro Ferreira Silva has verified-source OUT and
zero xM. These UUIDs are not interchangeable. Haaland's historical GW7 B xM is
82.496388, not a manual90-minute override. These are 2025/26 examples and must
not be presented as today's GW7 forecast.

## Confirmed MM→PM mean mismatch: activation blocker

The unchanged PM draws rounded Gaussian starter durations (sd10, clipped1–90)
and cameo durations (sd7, clipped1–45). A supplied conditional mean is not the
mean after clipping. For a certain starter with input90, PM E[min] is about86.01.
For a cameo input60 the PM mean is below45. This is a mathematical discrepancy,
not Monte Carlo noise and not a player-specific issue.

For a clipped integer duration K in[1,U], the exact mean is
1 + sum(k=2..U) Phi((mu-(k-.5))/sigma). Mixing the starter/cameo means with
B's p and q yields the analytical PM E[min]. The regression tests this identity.

Across11,794 matched B rows, analytical PM E[min]−B xM averages−0.728064 minute;
for B xM>60 it averages−3.014520 minutes. The corresponding previous-vFinal
average is−0.712296. Sampled means additionally contain400-draw Monte Carlo
variation. Both input xM and analytical PM minutes are shown in the preview.

The adapter intentionally preserves the locked PM sampler and records this
failed coherence gate. It does not reparameterize B, alter sampler variances,
clip B's output or substitute the experimental PMF without approval/validation.
An explicitly reviewed MM-owned sampling interface is needed to resolve this
boundary. Therefore independent validation is **not** the only remaining block.
The point metrics above are a controlled minute-parameter ablation conditional
on frozen PM inputs, not a raw-source complete pipeline certification.

## Six-GW technical test and current-data gate

The current entry point validates source hashes and observation clocks,
official complete fixture horizon, kickoffs, FPL/UUID bijection, rosters,
positions, same cutoff, freshness, current deadline and future-news scope.
It then invokes real B inference, unchanged PM, forecast sealing and original
private TS/chips. A generated regression fixture exercises the full path:
576 MM player-fixtures, 18 fixtures, 96 players and six GWs, followed by an
original TS plan and legal15-player/11-starter FPL lineup. No mocked simulator,
no published synthetic results and no mutation of manager state. This exposed
and fixed an exporter reliance on the incidental expected_minutes input column.

This regression is not a verified real-world B forecast or personal plan.
The strict entry point requires a genuine PR8 role/chance/return-duration
feature pack. PR15 had a frozen historical replay and real calibration refit,
but no current producer for that upstream contract. Current production
legacy/vNext output cannot simply be renamed B. The private production backend
also explicitly accepts its existing original forecast contract; no candidate
plan is routed into the production manager view in this change.

The historical PM rows are single-GW predictions at different origins. They
cannot be concatenated into a cutoff-correct historical six-GW TS replay.
The 2125-point benchmark is unchanged and was not falsely rerun. Captain,
transfer and chip changes on real current inputs remain Not Available.

## Prospective registration and source collection

The old register() compared registration time against forecast_at/cutoff,
rejecting newly computed forecasts. It now requires an explicit official
deadline and cutoff≤registered_at<deadline, rejects missing/naive/future clocks,
retains forecast bytes and a separate registration receipt, and refuses overwrite.

A versioned prospective protocol is in
`2026-10-17-mm-prospective-protocol.md`. No statistical gate is relaxed.
The new main workflow captures public bootstrap/fixtures hourly at:17 and
retains timestamped artifacts. Its successful source capture explicitly says
BLOCKED_CURRENT_B_FEATURES and forecasts_registered=0. It is not mislabeled
as automatic B forecasting. Scheduled execution is distinguished from push
execution in the delivery checkpoint.

## Remaining concrete blocks

1. Verified current PR8→B upstream producer and fresh six-GW inputs, including
   a current classified role ledger. No legacy/vNext substitution.
2. Real current B→PM→TS run and isolated candidate backend/app manager route,
   once those inputs exist. No private manager state was obtained or published
   in this round; synthetic tests do not verify the user's personal plan.
3. MM/PM minute-distribution coherence: the unchanged PM clipping loses the
   supplied conditional mean; no certified unified duration interface exists.
4. Untouched prospective observations with preregistered witnessed predictions.
5. PMF calibration/proper-score gate and existing club-risk flags.
6. 35 historical hard-source appearance conflicts, incomplete medical/return
   coverage, historical known-at proxies, and absent2024/25 formation ledger.

No production activation or scientific certification is justified. Existing
original production files are checked against PR14; only the mm-preview path
is overlaid on the current public Pages artifact. Rollback is to repin the
preview gateway to d8e53370; original production model files need no rollback.

## Reproduction

```sh
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python -m pytest -q tests
PYTHONPATH=src:scripts:. python scripts/locked_numerical_runtime.py scripts/replay_mm_candidate_calibration.py
PYTHONPATH=src:scripts:. python scripts/build_mm_integration_preview.py
PYTHONPATH=src:scripts:. python scripts/report_mm_integration_preview.py
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 python scripts/replay_mm_locked_pm.py
node --check app/mm-preview/preview.js
node --check app/mm-preview/chain.js
```

PR16 builds on PR15. CI, deployment, browser verification and exact commit
identities are recorded in `docs/checkpoints/2026-10-17-mm-locked-chain.json`.
