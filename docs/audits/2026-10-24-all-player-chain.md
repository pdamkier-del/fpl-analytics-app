# All-player MM → PM → TS input and realism review

This is the requested general review, not a Cherki-specific adjustment.
Production, private manager state and the selected forecasting parameters are
unchanged. Results are in `analysis/results/all-player-chain-audit-20261024/`.

**Correction, auditor v2:** the initial audit incorrectly treated the sum of
reported/modelled FPL minutes as an exactly conserved physical 900-minute clock.
That validity criterion and the resulting claim that all 120 team-fixtures
failed it are withdrawn. The retained v1 receipts are historical diagnostics,
not evidence of that claimed defect. Reported-minute sums, physical timelines
and normal substitution-count constraints must be distinguished.

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

## Reported minutes and substitution timelines

Read-only Core observations from the original FPL historical source have a
median reported outfield total of **897**, in both reviewed seasons, among
team-fixtures with no recorded red card and complete minute/red labels.
Only 26 of 709 such 2024/25 team-fixtures and 23 of 718 in 2025/26 sum to 900.
Goalkeeper reported totals also occasionally equal 89 or 91. This does not
establish a particular rounding/added-time conversion law, but it disproves
using exact equality of reported totals to the physical clock as a universal
validity test. Reproduction: `analysis/summarize_reported_minute_clock.py`;
receipt: `analysis/results/all-player-chain-audit-20261024/minute-clock/`.

The initial forecast's expected outfield totals range from about 818 to 918.
Those figures and the former counts of non-900 draws are descriptive, not a
standalone physical-failure verdict. The separate observation that 4,935
draws have more than fifteen outfield participants (maximum 21) remains a
standard five-substitution concern. Auditor v2 checks a lower bound on known
substitutions, including additional known goalkeeper participants; it does
not infer missing keepers from a reported-minute shortfall.

No continuous exit/entry timeline is exported, so totals and counts cannot
certify one. A detected standard-count breach is reported; otherwise the
timeline status remains **unknown**, even when totals happen to equal 900.
Dismissal/concussion exceptions are not silently invented. Double-gameweek
aggregates are not treated as individual-fixture timelines. The existing
normalized goalkeeper kernel's declared 90-minute invariant is a model
consistency check, not a claim that empirical FPL keeper sums are always 90.

## General repair candidate: tested and rejected

**Measurement limitation:** this candidate forces its model-minute totals to
900 and was scored directly against reported FPL minutes without a separately
validated reporting-clock conversion. Its results below are retained honestly;
they do not prove that a correctly measured joint timeline must perform worse.

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

**Decision: do not activate this candidate as implemented.** The gate is not
loosened after scoring. A proper joint duration/substitution model needs a
validated physical-to-reported-minute mapping and calibration against observed
squads, entrances/exits and removal events. Raw FPL marginals must not simply
be rescaled to 900. Full-model certification and production promotion are not
established by this trial or by the corrected source audit.

A post-hoc dismissal-context diagnosis retains the same reported-label limitation.
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

## Publication integration recovery

Run 40100293118 stopped in the refactored historical replay's reporting step:
the penalty-attempt frame had moved into task preparation but its reporting
reference had not. All 341 saved fixture predictions exactly reproduce the
reviewed NP replay (maximum xP difference zero); the missing frame load is
restored and a CLI reporting regression covers the taker cohort. The failed
run was not deployed.

Run 40105396189 passed 903 tests and the repeated current six-GW calculations,
then received an official Chelsea squad payload containing coaching staff
but no goalkeeper records. Validated uncached retries now reject that partial
payload and retain response hashes. The source gate requires parsed first-team
goalkeeper records, not the presence of a specific named player. An omitted
FPL goalkeeper is recorded as a registration-page discrepancy, never inferred
to be injured, on loan or unavailable. Replaying the actual failed response
followed by a fresh official request recovers 14 goalkeeper registrations
on attempt two. Full local regressions pass 908 tests; new publication still
requires a successful full external run and public browser/service checks.

Run 40119501751 then completed the historical replay successfully but correctly
rejected the old source hash for the reporting script repaired in adc38ed.
All 54,184 baseline/candidate prediction rows match the approved 341-fixture
reference exactly. Only that script's policy hash is updated after this
comparison; the model, decision, protocol, parameters and acceptance gates
remain unchanged. A fast repository-policy consistency regression now catches
such stale pins before the expensive replay. No failed run was published.

The subsequent isolated export check also tightened goalkeeper source coverage.
The source-completeness flag now requires the exact compressed GK squad-history
input (verified against the forecast's uncompressed hash), every saved official
source response, the embedded evidence receipt and the official FPL goalkeeper
status snapshot. Scheduled origin artifacts include that GK role input too.
Missing, modified or corrupt GK inputs cannot produce a complete-source status.
Earlier receipts from the preceding auditor version cover the MM/role/NP subset;
they are not retroactively claimed to satisfy this added GK requirement.
