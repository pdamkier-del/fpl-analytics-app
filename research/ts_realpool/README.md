# Full-original-pool funding study

Study EXP-TS-FUNDING-REALPOOL-001 follows the unchanged [PR56protocol](../evidence/next-study-20261123/PROTOCOL.md). Read the [result report](../results/EXP-TS-FUNDING-REALPOOL-001/REPORT.md) before any reproduction.

- v1registration/implementation freeze:35e06b73. Original recovery passed, but strict native-probability range guard rejected tiny negative roundoff. No states or arms generated. First receipt retained.
- v2registration/freeze:45a89aa1. Guard accepts at most1e-12 roundoff without clipping/mutating any original values or changing p>=.20sampling. Original preflight time deducted from3600second total. This is input-only correction before any test state/result, not candidate tuning or a numerical rerun.
- All12state batch committed e20c1046 before any arm; full original674player/sixGW/400draw object passed unchanged to original TSprojection/scorer.
- Actual worker uses only frozen source, original config, unchanged PR50candidate and existing scalar/transition audits. No source model or PR54file changes.

Reproduce in a detached checkout of45a89aa1 with its running registry; follow IMPLEMENTATION.md but invoke run_v2.py and fresh output/cache. The current canonical registry intentionally does not authorize accidental reruns after completion. Keep original first-run outputs; an independent replay of the same12states is not new independent evidence.

Existing PR54's immutable registry test contains a65-entry snapshot assertion. New canonical registry has66entries. Preserve the old file/manifest, report the count mismatch and validate current registry separately; do not edit a frozen study to conceal infrastructure drift. The report gives the exact test commands/status. No report-workflow integration or production activation is performed here.
