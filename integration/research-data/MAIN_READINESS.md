# Release decision — public archive only

23 November2026. Branch `integration/public-archive-main-20261123`, based on
main `e515658e27b1967a6149a5db13934a91cae7ac59`.

| Dependency | Actual scope | Main decision |
| --- | --- | --- |
| PR44 `84c41932` | Three frontend contract files | Excluded; not needed for public storage. |
| PR46 `876e61b0` | UI/PWA/store/module overlay, smoke tests and frozen exporter | Only pure exporter copied unchanged; no UI/service/release dependency. |
| PR51 `18335b36` | Public archive and mixed private TS integration | Copy only `archive.py`, `releases.py`, `computation_receipt.py`, `frozen-ts-config.json` and public tests. All private logger/routes/installers and runtime manifests excluded. |
| Existing main B producer | Pinned source161b67b6, original artifacts, hourly wrapper | Consumed without modifying or invoking it. Parent UI failure does not invalidate successful original computation. |
| Private storage/auth | Still unresolved in mixed integration | Does not block public archiving; remains fail-closed and out of this diff. |

The previous live PR51issue/retry/recovery demonstrated Release storage. This
task adds main-safe completion/discovery/catch-up and explicit missing-GW/failure
status. It does not repeat model research or change any original forecast.

## Local release checks

26public-only tests pass: inherited byte/config/deadline/revision/recovery/blank/
DGW contracts and new discovery, archive-once, source/branch rejection, failed
producer, late/private payload rejection, deleted asset and missing-GW checks.
Numerical/model/private/UI code is absent from the dependency set. The existing
producer/Pages and protected substitution workflows must remain byte-identical.

Actual GitHub probe, release-only recovery, changed-file list and code hashes
are recorded in `evidence/` after execution. Main-only schedule/event registration
must be reported separately from a feature-branch manual probe. No main activation,
production merge, app deploy or private storage permission change is implied by
a successful branch run.

## Release blockers

- Public schema, no-overwrite and source/identity rules: covered by inherited/new tests.
- GitHub writer/readback and new-original discovery: live verification pending at initial registration.
- Official next-origin/missing-GW monitoring: live verification pending at initial registration.
- Actual `schedule`/`workflow_run` delivery on main: requires reviewed integration into the default branch; cannot be self-certified from an unmerged PR.
- Unfinished PR44/46app/private work: excluded, no dependency for this PR.
- Private TSdurability and authenticated execution: unresolved, unchanged, no enabling code copied.

The only integration permitted here is the isolated public consumer. No full-stack
merge, model optimization, historical experiment rerun or app deployment.
