# B normal-match correctness requirements

User instruction on 25 October: establish known football constraints even if
historical error does not improve, including at most five substitutions.
This explicitly supersedes the earlier statistical-promotion requirement for
these structural constraints. It does not turn a particular substitution
heuristic, uncertainty estimate or reported-clock transform into known truth.

The existing normal-match kernel is now the default for current unified B
forecasts. Production and low-level historical reference calls are unchanged.
The real B publisher and one-match/one-GW/six-GW stage checks use the same kernel.

For every modeled **normal match**, per team:

- Exactly ten outfield starters and one goalkeeper.
- Paired arrivals and departures; ten outfield players plus one keeper active
  over every open interval of the normalized 0..90 regulation clock.
- 900 outfield minutes plus 90 goalkeeper minutes, including unlisted goalkeeper
  outcomes rather than silently omitting them from the conservation check.
- At most five substitutions, including keeper replacements.
- At most three live substitution windows; half-time does not consume a window.
- Identical analytical MM marginals and PM minute law. TS consumes the same
  shared PM point/minute draws; it does not reconstruct independent minutes.

Every sampled interval plan is validated. Public forecast validation also checks
team MM means and individual single-fixture scenario coverage, with explicit
unlisted keeper samples. A conservation check on observed FPL minute labels is
**not** introduced. The physical normalized clock is explicit in the contract;
an empirically calibrated mapping to reported FPL minutes remains unavailable.

## Scope and evidence

This is a planned normal-match timeline, before dismissal/removal events.
The existing discipline-point layer remains present, but dismissal-driven
truncation and emergency-keeper reassignment are not modeled by this kernel.
Concussion substitution exceptions are not modeled. The artifact says so;
it does not claim universal full-match physical certification.

The earlier two-season diagnostic remains unchanged at
`analysis/results/physical-timeline-20261024/`: minute MAE changed
10.912877→10.919865 and 10.184831→10.291065; xP MAE changed
0.889075→0.890843 and 0.870893→0.875883. These compare normalized physical
minutes against reported labels on reused periods without a validated clock
conversion. They are reported as diagnostics, not vetoes on football rules.

The original historical rejection receipt is retained as history. New
`protocol.json` documents the correctness acceptance separately. No fitted
MM, NP, penalty or role coefficients are changed. The NP source-integrity policy
pins the modified orchestration/contract and the physical kernel; its original
head fit, historical head decision and source guards remain intact.

Local tests: 984 passed; an additional focused run checks the strengthened
clock and audit contract. The default historical/nonphysical path reproduces
100 fixtures exactly, including events, intervals, RNG, aggregates and shared
preview scenarios. Current-source, stage and release receipts are recorded
separately as they complete; this document alone is not evidence of deployment.

To rehearse the full current B chain on the exact archived source bundle:

```sh
PYTHONPATH=src:scripts:.:analysis python scripts/locked_numerical_runtime.py analysis/replay_normal_match_chain.py --artifact /path/to/origin-40124214540 --out /path/to/rehearsal-output
```

The script binds live GK history, role squads and NP input sources to the same
origin artifact, runs the actual current publisher into a private output
directory, verifies one-match/one-GW scope replay, and exercises the existing TS
search with a synthetic legal squad. It never changes an actual manager team.

## Completed same-input rehearsal

All 48,000 normal-match team draws pass. The original model required more than
five substitutions in 8,356 draws (maximum 12); the coupled model has zero such
draws (maximum five). New sampled outfield totals are exactly 900 throughout.
This concerns modeled normal-match scenarios, not observed FPL label sums.
Start marginals differ only by floating-point roundoff, at most 2.45e-15.
Details: `same-input-minute-comparison.json`. Full six-GW synthetic TS search
and exact one-match/one-GW scope replay pass.

The deployment's older default guard compared source text from before the
reviewed scoring extraction. It now checks strict SHA-256 pins for the exact
reviewed simulator, scorer and input contract and executes the original
`49b5a829...` PM against the current disabled-B path. Every event/result field,
RNG state and aggregate is identical on 100 full-roster fixtures (20 draws and
20 aggregate draws each), plus the original 100 seeded small fixtures and its
100-draw aggregate. Unknown default-source edits still fail closed. All 986
tests pass under the GitHub test environment; no model output is changed by
this guard repair. Fresh release validation remains separate.

## Reuse original-head reference evidence without refitting it

The original full historical job takes about one hour. Its original fitted
heads and source datasets have not changed. `historical_reference_reuse.py`
permits the specific successful `4a5e421...` reference after checking a reviewed
dependency manifest, exact extraction receipts and executing the original PM
parity oracle again. Every existing changed source/data file must be explicitly
pinned; deletions/renames and unreviewed additions fail closed. No new-head
statistical score is substituted for an old reference result.

The run provenance records both the historical reference commit and the new
numerical commit, rather than claiming the whole source is identical. Cached
evidence covers the unchanged original heads only. Current official inputs,
both current simulations, the new normal-match law, one-match/one-GW scope
replay and the full synthetic TS chain still run afresh. Subsequent same-source
refreshes retain the existing stricter exact-commit reuse path.
