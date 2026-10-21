# Unified B MM → PM → TS

Implementation on the existing PR #22 branch. Production forecast configuration,
default simulator, original transfer search and original private worker retain
their behavior. New B behavior is explicitly versioned `B-MM-PM-TS-v1`.

## Implemented

- The B player panels and private planner consume the same sealed forecast.
  Publication updates the catalogue/fixture/role documents to that identity.
  Original B role memory remains separately checksummed and is reusable at the
  next refresh. No private manager record is rewritten.
- The existing role-aware joint goalkeeper process retains exactly one starter
  and 90 total keeper minutes, including an explicit unlisted reserve pool.
- Outfield durations use the existing bounded, rounded Normal sampler with its
  location inverted to preserve MM's conditional mean. Start/cameo states remain
  separate; the cameo support permits early substitutes to exceed 45 minutes.
  All analytic fixture and weekly MM/PM expectations must agree before export.
  Sample means can still differ because only 400 scenarios are drawn.
- Official FPL penalty order determines the hierarchy among players actually
  on the pitch at the event. Tied orders retain historical relative weights;
  missing orders retain historical fallback. There is no named-player override.
  Penalty occurrence and conversion models are retained. The ordinary-goal
  budget still uses its existing team conversion approximation.
- PM exports aligned points/minutes draws. TS reuses the original six-GW beam
  search, prices, free-transfer transitions, discount weights and hit buffer,
  but scores proposed squads with legal automatic substitutions and conditional
  captain fallback from those same draws. Nonzero-minute cameos block autosubs.
  XI selection, candidate generation and bench ordering remain heuristics.
- FH/WC comparisons and the current lineup use the same B scorer. Bench Boost
  deducts ordinary autosub coverage using the shared scenarios, avoiding double
  counting reserve points. Original chip timing policies remain diagnostic;
  missing whole-half TC scenarios are not invented.
- A separate preview worker scopes and restores scoring hooks. The production
  `/plans` route and `service/manager_job.py` remain unchanged. The preview route
  retains official catalogue, deadline, freshness, snapshot, private capability,
  idempotency and state-immutability checks. Service health advertises the new
  capability only when the preview worker imports successfully.

## Completed local validation

Full Python suite: **760 passed**. Locked-default parity: all result fields
match the retained original simulator for 100 seeded fixtures plus a 100-draw
aggregate. JavaScript adapter, B contract, goalkeeper and probability checks pass.

The six-GW stage check on archived 20 October inputs completed: one-match and
one-GW outputs reproduce their full-horizon PM distributions exactly; a legal,
explicitly synthetic manager fixture runs all six TS weeks without mutation.
It is not the user's private plan. Current fresh-source CI and public-browser
publication are recorded separately when complete.

The historical protocol was fixed before inspecting the replay results. It
tests all 501 archived PM fixtures, with 400 draws per arm and past-only B minute
inputs. Goalkeeper/joint-XI sampling is identical between duration arms, so the
point comparison isolates the duration change; existing GK-v2 role validation
is separate. The analytic minute check covers all 50,231 frozen B rows.

| Metric | 2024/25 control → corrected | 2025/26 control → corrected |
|---|---:|---:|
| Analytic minute MAE | 11.88499 → 11.50008 | 10.52218 → 10.13769 |
| Analytic minute bias | −1.14539 → −0.35678 | −1.00008 → −0.25795 |
| xP MAE | 0.891884 → 0.889120 | 0.904609 → 0.903286 |
| xP bias | −0.002700 → −0.010548 | 0.007767 → 0.003526 |
| xP RMSE | 1.813718 → 1.811475 | 1.862162 → 1.864737 |

Start Brier is unchanged by the duration-only correction. Historical 2024
official penalty-order snapshots give xP MAE 0.889113 versus 0.889120 without
the role repair: effectively flat, not a claimed point-accuracy breakthrough.
No equivalent pre-cutoff 2025 rank archive is supplied, so current roles are not
backfilled into that season. Deterministic tests verify first choice, absence
handover, minute support, keeper separation, formation constraints, cameo
blocking, reserve value, correlated captain fallback and BB accounting.

All predeclared preview gates passed; this is consistency and non-inferiority
evidence, not independent production certification or a full-season TS return
claim. Point bias worsens in 2024 and RMSE worsens in 2025. Research periods have
been reused, historical availability clocks retain documented proxies, and
the 2024 rank snapshots' publication timing is not independently verified.

Additional analytic outfield checks improve P(90) Brier from 0.09910 to 0.09373
and from 0.09120 to 0.08436 respectively. P(60+) Brier worsens very slightly
(0.087795→0.087816 and 0.078915→0.078956). Fixture-paired 95% intervals for the
xP-MAE change include zero in both seasons: [−0.00550, 0.00008] and
[−0.00321, 0.00065]. These are not statistically established point gains.
Reproduce these checks with `scripts/audit_b_chain_uncertainty.py`.

Local Chromium desktop and mobile checks passed for the existing player
catalogue, profile, probability cards, team sheet, transfer plan display,
green-button cache refresh, one mocked private job, 429 retry behavior and
dashboard injury/news invalidation. No page errors or real private submissions
occurred; saved manager state remained unchanged. The mocked result was
calculated through the B scorer on a clearly synthetic local fixture.
The additional four-route identity check confirms the identical forecast and
analytic MM/PM minutes on player catalogue, profile, My Team and Transfers in
both viewports. A narrow additive CSS fix prevents the existing profile grid's
table minimum width from expanding the mobile page; desktop layout is retained.
The canonical current PM audit now describes the unified forecast; the old
locked-PM audit is explicitly archived as a reference rather than displayed as
the current model's audit.

Evidence: `analysis/results/unified-b-chain-20261021/validation.json`,
`protocol.json`, `predictions.csv.gz`; executable
`scripts/validate_unified_b_history.py`. No finishing correction, own-goal/red-card
physics change or new score-dependent match model is promoted by this work.


Publication and actual-service check (21 October 2026):

- Numerical run [39573140691](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39573140691) passed. The complete current chain covers 668 players, 60 fixtures, GW8–13 and 400 aligned scenarios, with exact numerical repeatability.
- Publication [39580113437](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39580113437) passed, including 761 Python tests and all four desktop/mobile browser suites. The public app serves canonical forecast `275d8ac1dee7b1687d0a788091c6276e776041521e37383e88377f61431552ff`, cutoff 2026-10-21 09:15:46 UTC. All 88 production asset hashes are preserved.
- All four suites were repeated against the actual public HTTPS app with TLS verification enabled. Player catalogue/profile, My Team and Transfers use the same forecast; no horizontal overflow or page exceptions, private manager state unchanged. Transfer/news tests intercept private submissions and use an explicitly synthetic local fixture.
- An additional real remote synthetic request exposed a standalone-worker import error: the HTTP process imported the B adapter successfully, but its child process had no repository root on `sys.path`. Added that path only in the isolated B worker, with an end-to-end subprocess regression removing `PYTHONPATH` and using an unrelated working directory. The whole 762-test suite passes after this repair. A current-data standalone six-GW calculation also completed. No production worker or numerical source changed.
- The isolated backend correction is ready on the existing live source branch at `45c2c316fb2338dba4fd66dd2ad4ed7c24ed193a`. Render activation was verified at 12:31 CEST by the exact worker SHA-256 `e89e1ec8d7c11674d6d997e43b80c1b9db3bd97f26ea144d42874771a28907d1`. A single explicitly synthetic private remote job completed all six GWs at 12:32 CEST. Independent recomputation verifies its reported scores and captain/vice selection against the shared PM scenarios; unauthorized result access returns 404. This verifies the actual worker in addition to the browser mock suites. Health now exposes a public worker source hash for deployment verification. No real user plan, private receipt, key or squad is committed or published.

Fresh Penders comparison is in `analysis/results/unified-b-chain-20261021/current-before-after.json`. MM xM and analytic PM E[min] now both equal 89.4700; P(start) 99.7593%, P(60+) 99.2808%, P(90) 98.7707%, xP 3.7675. Point estimates use 400 draws and are not a statistically established accuracy gain.


The additional unmocked browser readiness check then correctly refused a stale
forecast: official FPL status for Gourna-Douath and Cho changed from injured/0%
to doubtful/50% after the captured source. A fresh source/MM/PM/TS rebuild is
required; neither the public news nor the manager state is rewritten to bypass
that condition. The refresh workflow can reuse historical gates only from a
successful archived run with exactly the same checked-out numerical commit.
It checks the run source/status and gate acceptance and records every reused
file hash; it still captures official current data and runs both original and
B six-GW chains afresh, twice. This avoids repeating 35 minutes of unchanged
historical research while the current availability data ages.


Intraday refresh status at 17:20 CEST:

- Refresh/publication runs 39586643552 and 39610903008 passed, including the additional unmocked browser gate requiring real captured news and forecast alignment. Run 39610903008 published forecast `37f3d0ef09cc5168c2b1e3c9479739edb102ebf7d913784da0df9b7ce3981513`, model cutoff 16:04 CEST and news capture 16:16 CEST.
- Later official Gibbs-White availability changed; the remote regression preflight correctly refused that older snapshot before submitting a job. Refresh 39620552568 subsequently stopped because Šeško's official news changed during source acquisition. No mixed snapshot was published.
- Attempt 2 of 39620552568 is queued during GitHub's reported Actions degradation. Its completion is wired to the actual private synthetic six-GW regression and a TLS-verified desktop/mobile display check. This is pending validation, not a completed latest-data delivery.
- The display helper first asserts that real `validation_only` state/results are rejected as personal plans. It then uses a clearly synthetic browser-only presentation copy, rebinds its state hash and compares all six-GW numerical rows against the unchanged actual remote result. No user state or private capability is published.
- Main publication additionally requires the exact corrected standalone worker SHA before deployment. Numerical source remains f492be4795bfd630ba91377d71497e68c1d85934 and production assets remain outside the preview overlay.
