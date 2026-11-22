# Reproducibility and validation requirements

## Read-only programme commands

```sh
python research/tools/registry.py validate
python research/tools/registry.py status
python research/tools/registry.py next
python research/tools/registry.py search workload
python research/tools/registry.py show EXP-TS-SEARCH-001
python research/tools/registry.py evidence EXP-TS-SEARCH-001 --verify
```

These use the Python standard library, do not fetch network sources, fit models, run TS or publish a product. `status --render` explicitly refreshes only the derived Markdown status table. It is a dated registry view, not a live monitor.

## Evidence and immutable registrations

Each `experiments/ID.json` has question, hypothesis, primary/secondary metrics, comparator/modification, train/dev/test periods, sources/cutoffs, sample/power status, dependencies, reproduction scope, acceptance gates, result links, decision and next action. The initial registration is sealed in `events.jsonl`; changing it in place makes validation fail. Historical study IDs and decisions remain linked to their original evidence hashes. Large original result files are referenced, not regenerated or duplicated unnecessarily.

`reproduction_command` for imported/planned work is explicitly an evidence-integrity command; it is not represented as a full model replay. `full_experiment_command=null` and `execution_ready=false` mean the new harness does not exist. A scientific ready state is permission to begin implementation, not a false claim that an unimplemented experiment already runs.

After implementing a real harness on an isolated research branch, append its execution recipe without rewriting scientific registration:

```sh
python research/tools/registry.py implement EXP-TS-SEARCH-001 \
  --command 'python research/IMPLEMENTED_HARNESS.py --REGISTERED_ARGUMENTS' \
  --harness research/IMPLEMENTED_HARNESS.py
```

The paths/arguments above are templates, not existing executables. The command refuses a missing harness. Changes to hypotheses, targets, model arms, train/test splits or stopping criteria need a new registered protocol/version. Implementation events cannot be used to sneak in new scientific settings.

State changes use `record ID --state ... --reason ... --evidence ...`; no direct edits of existing events/decisions. Running requires a registered implementation. Completed/accepted claims require versioned public evidence, and acceptance needs an explicit independent-validation statement (independent correctness for deterministic infrastructure; independent out-of-sample evidence for efficacy). Acceptance never changes production. Private evidence is referenced through nonidentifying review metadata only, never copied into a public event.

## Result package contract

Every new result has a unique run/result ID, experiment/protocol hash, source/model/fit/scorer hashes, exact data vintages/cutoffs, rule year, original forecast receipts, eligible/excluded counts, metric definitions, paired effects and uncertainty, run command/environment, diagnostics, limits and a narrow final decision. Include failed/inconclusive results. Corrections get a new result version and a supersedes link; preserve prior outputs.

Candidate ablations require a proper prior-only refit and nested validation; an oracle or component deletion is not that ablation. Keep common inputs/random draws where justified, report Monte Carlo variability and do not reuse simulator draws as statistical replicates. No expensive rerun if stored predictions and a scoring-only check suffice.

## Tests before claiming readiness

Validate registry hashes, IDs, dependencies, transitions and existing-protocol preservation; local links/evidence hashes must resolve. For later execution: temporal future-label noninterference, original identity/seal validation, scoring units, full horizon, legality, missing/DGW/blank/schedule revisions and deterministic output requirements. Add privacy and capability tests to any private boundary; artifact allowlists and explicit negative tests prevent managerdata export.

Programme tests:

```sh
python -m pytest -q research/tests
```

These test registry behaviour and the plan's scope, not MM/PM/TS efficacy. Existing audit tests and original model tests remain separate; listed tests are not automatically claimed as passed.

## Scope guard

This branch may add only `MASTER_PLAN.md` and `research/`. No production pipeline, UI, model, preregistered substitution file or original PR41/42 result is modified. Draft PR43 is preserved on a different branch and is not merged into the programme.
