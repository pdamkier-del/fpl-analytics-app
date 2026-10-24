# All-player MM → PM → TS input and realism review

This is the requested general review, not a Cherki-specific adjustment.
Production, private manager state and the selected forecasting parameters are
unchanged. Results are in `analysis/results/all-player-chain-audit-20261024/`.

## Coverage and the distinction that earlier checks missed

The initial served snapshot covers **668 players, 4,008 player-fixture rows,
60 fixtures and 120 team-fixtures**, GW9–14, data as of 24 October 2026
11:09:45 UTC (13:09:45 Copenhagen), seal
`712e420f5321387e313422cbea5c0f541f671f5b24444e991867a2cc8ae0c5a5`.
It was produced by run 40087908653, numerical/UI source
`b0a229c0de05a640f49937616c070dfbcdf986fc`.

All-player numerical identity and MM/PM moment checks pass. This does **not**
establish a physically coherent match or calibrated individual probabilities.
The previous technical claim was broader than the tests justified.

| Boundary | Current finding / new control | Remaining limitation |
|---|---|---|
| Identity | Every forecast/MM/catalogue/input player/fixture is joined by exact keys; club and position are checked | A valid registered identity is not evidence of a real first-team role |
| Source clocks | Hashed input provenance, strict training/feature prefix clocks and target-outcome exclusion | Historical publication clocks still include documented proxies |
| Workload and roles | Explicit workload/last-start fields are PL-only; detailed role history includes verified all-competition starters | Different scope is visible; it has not been replaced with an unvalidated all-competition feature distribution |
| Availability | Known appearance caps and moment/probability bounds are checked | Uncertain medical recovery and latent rest/selection causes are not fully learned |
| MM → PM | Per-fixture and per-GW moments, mixtures, point components and identity coverage are checked | Independent outfield durations/cameos do not form a physical substitution process |
| Ordinary/penalty goals | Exact selected policy decision, source-table hashes, actual scorer-weight hash and full weight reproduction | Count-based FPL-scale NP estimate; penalty-assist and taker-bias limitations remain |
| PM → TS | Shared scenario identity and six-GW synthetic decision checks are retained | Heuristic search and independent full-season/chip return are not certified |
| Statistical reliability | Historical start and minute-probability bins, subgroup errors and fixture-paired intervals | Reused research periods; no independent individual-player certification |
| App | Per-player, forecast-bound data audit with checksum validation; missing/stale evidence never appears verified | A complete source trail is not a guarantee of a start, minutes or points |

## Critical physical-process finding

All 120 initial team-fixtures fail the standard 900 outfield-minute budget.
Expected totals range from about **818 to 918 minutes**. Of 48,000 exported
team draws, **47,559 do not sum to 900**, **19,434 exceed 900**, and **4,935**
have more than fifteen outfield participants; the maximum is 21. The kernel
does select ten outfield starters and its goalkeeper process covers 90
minutes. The error lies in sampling unpaired outfield exits and entries.

The check is conditional on a normal match. Explicit dismissal/removal and
concussion-exception timelines are not exported or modelled completely; a
deficit cannot silently be declared explained by one. Double-gameweek samples
are not falsely used as individual-fixture timelines. Matching the *average*
900 is also insufficient if individual draws violate it.

## General repair candidate: tested and rejected

An offline physical timeline kernel retains the existing joint starter
mixture, uses the existing duration/cameo inputs, constrains normal matches to
five substitutions including GK and three windows, and derives analytical
MM probabilities/minutes from the exact same finite ensemble sampled by PM.
It contains no named-player rule or newly fitted coefficient. Original
default seeded results reproduce exactly on 100 historical fixtures.

The protocol was fixed before scoring. Both seasons use GW22–38, **341 paired
fixtures**, 400 draws per arm, excluding the NP development GW16–21. Every
baseline xP reproduces the selected published NP-head archive exactly, with
maximum error **0**. Results are in
`analysis/results/physical-timeline-20261024/`.

| Metric | 2024/25 before → candidate | 2025/26 before → candidate |
|---|---:|---:|
| Minute MAE | 10.912877 → 10.919865 | 10.184831 → 10.291065 |
| Minute bias | −0.332790 → +0.135902 | −0.210245 → +0.122113 |
| All-player xP MAE | 0.889075 → 0.890843 | 0.870893 → 0.875883 |
| Played-player xP MAE | 1.890859 → 1.885212 | 1.993161 → 1.991926 |

The 2025/26 minute-MAE increase **0.106234** exceeds the predeclared maximum
**0.05**. Its fixture-bootstrap interval is [0.064712, 0.146044]. The xP-MAE
increase also has a positive interval [0.001752, 0.008230]. P(60+) and P(90)
Brier improve, but P(0) and some rotation errors worsen. No subgroup or metric
has been hidden to call the candidate a win.

**Decision: do not activate this candidate.** The gate is not loosened after
scoring. Rejection does not resolve or excuse the baseline's physical error:
it remains a critical outstanding requirement, and prevents full-model
certification or production promotion. A proper joint duration/substitution
model needs calibration against observed squads, entrances/exits and removal
events, rather than a live minute rescaling or a boost to Cherki.

A post-hoc dismissal-context diagnosis does not explain away the failure.
Among the 150 evaluated 2025/26 fixtures with no recorded red card, minute
MAE still rises from 10.307809 to 10.400528. The 20 fixtures with a recorded
dismissal also worsen (9.266594 to 9.473737). This is an explanatory split,
not a replacement acceptance cohort or independent test; unrecorded removal
events are not ruled out. The original all-fixture rejection remains intact.
The read-only reproduction is `analysis/summarize_physical_removal_context.py`.

Repeated deterministic uniform generation was cached and conditional-state
grouping vectorized after stack profiling. All intervals are bit-identical
to the original implementation on 160 conditional ensembles × 128 states.
A numerical boundary failure from sub-micro starter-mass residuals was fixed
with endpoint-preserving normalization and regression cases. Failed/incomplete
runs produced no acceptance decision; the fixed cohort, statistical
parameters and gates were not tuned to those outcomes.

## Source/documentation repairs

1. Scheduled jobs omitted their current-input artifact. The exact initial
   snapshot inputs cannot be recovered by their advertised hashes, so the
   audit marks that fact unknown. Older inputs are never substituted. Every
   future origin now retains its fresh feature inputs, role ledger, source
   receipts and NP source tables, separately from reusable historical gates.
2. The public NP evidence export pointed to the earlier prototype decision
   while actual inference and its gate used the correct final-v2 policy.
   Export now reads the exact selected, approved and checksum-pinned decision,
   and rejects missing/tampered/out-of-root/failed decisions. This was an
   evidence-export error, not evidence that the prototype drove inference.
3. The ordinary-goal weight audit is deterministically compressed and its hash
   embedded in the forecast. The source audit recomputes all scorer weights
   from the exact saved PM frame, selected model and five NP source tables.
   Fresh publication requires complete source linkage. This is separate from
   the deliberately false full-model-certification flag.
4. PL-only workload scope is declared in provenance. Current metadata also
   explicitly says the outfield budget and substitution cap are not enforced
   by the active model. The rejected candidate remains offline.

A retained 23 October release is audited separately using its exact input
bundle. An additional offline complete-source fixture reproduces all 4,008
ordinary scorer weights from matching raw sources; its missing old export
metadata is supplemented **only for the test**, not backfilled into the public
forecast. The two origin scopes and their hashes remain distinct.

## Probability calibration, not a universal rotation boost

The start reliability review covers **24,099 outfield validation rows** across
the two reused periods. For rotation/short-history rows in the 40–50% bin,
mean predicted/observed starts are 45.45%/43.68% in 2024/25 and
44.97%/39.18% in 2025/26. That does not support raising all rotation players
because one 48% player starts. It also does not disprove a Cherki-specific
missing role signal. Unknown or sparse information must remain visible;
coach statements and prospective competition-priority/absence inference are
not newly activated by this audit.

Final CI, public browser/source-linkage, production-byte and synthetic-service
receipts will be recorded with the delivered preview. No user team or private
job key belongs in the public evidence directory.

## Prospective recording

Publication also writes a compact all-player/fixture prediction ledger for
future evaluation. It records the actual capture time separately from source
data-as-of, stable player codes, exact fixture predictions and source hashes.
A capture after the origin deadline or kickoff is not retrospectively marked
eligible merely because the forecast's source timestamp is old. The ledger
and manifest are retained as a separate 90-day publication artifact; origin
feature/source artifacts have a 30-day retention window. This enables honest
prospective evaluation during those windows, not a promise of permanent
archival storage or an independent calibration result today.
