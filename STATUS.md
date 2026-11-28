# Season operations and research status

Updated 2026-11-28. This is a navigation/handoff document, not a deployment receipt.

## Frozen models and observation phase

Keep MM, PM, TS v3 (rho 0.60, six GW, hit buffer 1) and existing chip logic unchanged. TS v4.1 is the PR66 research candidate: objective and beam ranking rho 0.90, candidate shortlist rho 0.60, same scorer and costs, chip-free comparison. No promotion without the preregistered evidence. The 16-GW paired shadow trial is not yet running. No new research needed until observations justify it.

## Where to work

| Scope | Authoritative reference / current status |
|---|---|
| Default branch and public archive automation | main (observed 5e35397b); [archive handoff](integration/research-data/MAIN_READINESS.md) |
| Standard B preview publication | [.github/workflows/mm-current-preview-publication.yml](.github/workflows/mm-current-preview-publication.yml); numerical source 161b67b6, UI source b6ecb068 at observed main |
| Private B worker | Render service fpl-analytics-private-manager; verify actual health and deployed source before modifications |
| Separate team/transfers UI preview | [PR60](https://github.com/pdamkier-del/fpl-analytics-app/pull/60), integration/app-team-transfers-20261126; separate public path, not merged |
| Dual TS comparison | [integration/ts-v4-dual-preview](https://github.com/pdamkier-del/fpl-analytics-app/tree/integration/ts-v4-dual-preview), based on b6ecb068; backend and UI code written, not tested or deployed; reconcile with currently selected UI and backend before release |
| Prospective MM/PM evaluation | [PR55](https://github.com/pdamkier-del/fpl-analytics-app/pull/55) open; [PR58](https://github.com/pdamkier-del/fpl-analytics-app/pull/58) supplies versioned boundary-roundoff correction and activation handoff; review/pin corrected evaluator before activation |
| Private state persistence | [PR51](https://github.com/pdamkier-del/fpl-analytics-app/pull/51); unresolved real end-to-end durability |
| TS study | [PR66](https://github.com/pdamkier-del/fpl-analytics-app/pull/66) consolidated report and protocol; [61](https://github.com/pdamkier-del/fpl-analytics-app/pull/61), [62](https://github.com/pdamkier-del/fpl-analytics-app/pull/62), [63](https://github.com/pdamkier-del/fpl-analytics-app/pull/63), [64](https://github.com/pdamkier-del/fpl-analytics-app/pull/64), [65](https://github.com/pdamkier-del/fpl-analytics-app/pull/65) are retained research evidence, not release dependencies |

## Observed operational blockers

1. [Preview run 46134909789](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46134909789): original computation succeeded; 1139 Python tests and subsequent JS contracts passed; browser validation timed out in analysis/verify_desktop_probabilities.cjs:23 on [data-open="560"]. Determine why the real selector is absent; do not bypass gate.
2. [Weekly review 45468369366](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45468369366): score_prospective_player_forecast.py:40 rejected Invalid archived probability. Identify actual field and magnitude. PR58 documents a separate evaluator's tiny negative native p_play roundoff, not proof this is the same defect. Preserve archived bytes; only a verified boundary-roundoff correction at scoring, with counts and strict rejection of substantive errors.
3. Public archive runs [46099511958](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46099511958) and [46137737470](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46137737470) succeeded. [46109840134](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/46109840134) failed overall despite verified next-origin coverage and no missing completed origins: prior producer failures were reported. Distinguish forecast coverage from pipeline health. Do not mark missing evidence as recovered.
4. PR55 was reported nonmergeable at audit; inspect conflict/base and update only the activation wrapper after review of PR58. Do not merge the stacked C1 research branches to activate evaluation.
5. Dual TS integration requires actual Render workspace/service identification, existing deployed revision, regression and browser checks, matching health hash/publication pins and live verification. No workspace selected in current connector session. Preserve current UI and existing chip output.

## Release and maintenance rules

- main: reviewed operational code only. integration/: small, scoped technical PRs from the actual relevant baseline. research/: immutable experiment evidence, linked by PR and commit. Existing historical names are retained; no bulk branch deletion, force pushes or stacked merges.
- A green numerical job is not a successful app deployment. Report original forecast receipt, service revision, UI revision, test and publication run independently.
- Keep existing weekly review and public archive; repair and verify before adding automation. Preserve privacy, immutable originals, official finalized labels and fail-closed gates.
- Start the PR66 paired trial only after durable authorized private state and final outcome capture are verified. Both simulated arms branch from one predeadline state, then evolve separately. Live side-by-side advice from the current real squad is not a season replay. Record plans separately from actual executed transfers. Follow the frozen 16-GW protocol; no tuning mid-trial.
- Review errors weekly using existing jobs; distinguish data/code bugs, random variation and recurring model bias. No new model changes or Codex research tasks at this stage.
- Before closing or deleting old branches, check open stacked PR dependencies and retained commit references. Prefer linking historical evidence over destructive cleanup.

## Handoff

This documentation-only change does not repair or deploy the listed services, run numerical tests, or activate the shadow trial. Next actions: fix reproducible browser and weekly-review failures in their actual pinned sources, review existing PR55/58 activation, verify archive/outcomes/private persistence, then test and deploy dual TS comparison. Record exact receipts here or in the relevant existing handoff.
