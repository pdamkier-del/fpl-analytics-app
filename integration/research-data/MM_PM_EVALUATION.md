# C2 prospective MM/PM evaluation

This integration runs the registered PR #54 evaluator at `eb35ab4f523c5d5037146bcfbaf721ce32e9f884`. Its archive dependency is the PR #53 main commit `d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c`. Both checkouts are sparse and pinned. The evaluator verifies its registered implementation manifest, and the archive adapter verifies the helper hashes and checkout commit. The original registered workflow remains in the evaluator checkout because its bytes are part of that manifest. Only the main wrapper and this handoff are added by the integration PR.

After reviewed merge, the wrapper runs after successful completion of the same-repository main **Archive original public B forecasts** workflow, daily at 07:43 UTC, and on explicit main dispatch. The verify job uses read permissions and runs the existing registry and synthetic evaluator tests. Pull requests stop at verification. The main evaluation job runs only after verification passes. Its repository write token is used by the existing public Release store. The only Actions artifact is the public status JSON. There is no Pages, model execution, user-state input or private manager endpoint in this path.

## Registered rules

The registration boundary is 23 November 2026 at 11:04:39.640399 UTC. The evaluator requires a later original issue and completed publication within the registered deadline-minus-60-minute cutoff. The pre-registration GW12 issue does not qualify. The evaluator selects one original per origin GW, waits for official finished and data-checked results, and uses the registered metrics and finality checks. It retains original selections and label revisions as write-once Release records under `fpl-research-mm-pm-v1-*`. The 16-origin window, fixed 30-day data lock and minima of 12 complete GWs and 120 fixtures are inherited from the pinned protocol.

## Verified before merge

- Main archive run [45150316270](https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/45150316270) completed on a natural `workflow_run` event at the pinned archive commit.
- Local tests with Python 3.12, NumPy 2.3.5 and pytest 9.1.1 validated all 65 registry entries and passed all 37 tests in the pinned evaluator and registry suites. They cover registration and cutoff exclusion, finality, report recovery, label revisions and fixed-lock behavior.
- A read-only live preflight against the public archive recovered and verified the original GW12–17 Release revision `f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633`. The example was explicitly ineligible, zero eligible candidates were found, and zero origins were scored. No release publication was attempted.
- The wrapper's YAML structure, shell syntax and read/write separation were checked locally.

The evaluation schedule and real report publication are pending review and merge. The first main run should retain its Actions URL and status receipt even if it reports `awaiting_eligible_original`. Actual end-to-end scoring and immutable report publication require an eligible original and final official labels. The evaluator and protocol pins are part of the review scope. Review the registered scientific implementation in PR #54 before enabling the publishing job on main.
