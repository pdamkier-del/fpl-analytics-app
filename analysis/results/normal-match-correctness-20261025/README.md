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
