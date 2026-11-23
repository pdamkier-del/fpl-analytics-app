# Prospective frozen MM/PM validation

Read [PROTOCOL.md](PROTOCOL.md), [setup report](../results/EXP-MM-PM-LIVE-SETUP/REPORT.md) and [next improvement gates](NEXT_IMPROVEMENTS.md). This implements EXP-MM-LIVE-001 and new EXP-PM-LIVE-001 under existing EXP-OPS-EVAL-001. It is not a new model. Existing research supplies definitions and historical context only.

## Reproduce

Python 3.12, numpy 2.3.5, pytest 9.1.1. Supply a separate checkout of this repository at `d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c` as `FPL_ARCHIVE_RUNTIME`; it supplies the existing C2 archive/producer-interface helpers. Their exact source hashes are checked. No model execution occurs.

```sh
python research/tools/registry.py validate
FPL_ARCHIVE_RUNTIME=/absolute/pinned-checkout OPENBLAS_NUM_THREADS=1 python -m pytest -q research/mm_pm_live/tests research/tests research/pm_defs/tests research/ts_search/tests research/ts_funding/test_funding.py research/stage0/tests
OPENBLAS_NUM_THREADS=1 python research/mm_pm_live/run_online_v2.py --archive-root /absolute/pinned-checkout --out /fresh/run-directory
```

The last command reads public original archives and official finality metadata, and writes local status. `GH_TOKEN` is used by the existing GitHub backend; do not print it. A fresh output directory is required. Use `--verify-example <original-release-tag>` for an infrastructure-only recovery check; it does not make that issue eligible or score outcomes. Only the reviewed automation adds `--publish` with narrowly scoped repository contents-write access.

## Automatic cycle, pending integration

The proposed `.github/workflows/research-mm-pm-evaluation.yml` consumes the existing main archive workflow and a daily schedule. It checks registry/code contracts, recovers originals, waits for cutoff and final official labels, then writes public immutable selection/window/report records under `fpl-research-mm-pm-v1-*`. Per-GW reports retain raw official label vintages; corrections create new revisions. Final primary reads only reports retained by the fixed lock. There is no forecast recomputation, model import, private state or app deployment. Old six-GW targets are never pooled as independent origin targets.

**This research PR does not activate that workflow on main.** C2's original forecast archiving is already automatic; scientific report automation still requires reviewed integration. A missing/invalid origin remains visible, never a zero error. Interrupted empty release shells can complete; conflicting nonempty records fail closed. Public Release durability excludes administrator deletion/tampering guarantees; archived byte hashes and immutable identities remain checked on every recovery. Status artifacts are transient convenience only; the research Release records are the permanent report store.

## Version history and audit boundary

Protocol commit `7c4df96f` preceded new eligible issues/outcomes. v1 implementation `e7a7dade` and its manifest/first preflight remain intact; reproduce v1 at that commit with its contemporaneous registry. v2 commit `e09dbf5c` changes only archive I/O and manifest identity, registered before its own preflight. See [IMPLEMENTATION_V2.md](IMPLEMENTATION_V2.md). The latest registry intentionally requires the v2 harness. No later outcomes motivated either implementation.
