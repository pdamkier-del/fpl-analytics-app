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

27 public-only tests pass: inherited byte/config/deadline/revision/recovery/blank/
DGW contracts and new discovery, archive-once, source/branch rejection, failed
producer, late/private payload rejection, deleted asset and missing-GW checks.
Numerical/model/private/UI code is absent from the dependency set. The existing
producer/Pages and protected substitution workflows must remain byte-identical.

Live original-source probe45137281151and automatic-discovery probe45137636876
both SUCCEEDED. The latter found four previously unarchived originals and skipped
the existing two. Source45105050197produced new forecast4d1a2e39… / revisionf54f651e…,
release455143034, GW12–17,4,044player-fixture rows. Every file was independently
recovered from Releases only; original source/computation were not rerun. All12
asset IDs/digests/sizes/clocks of the first new release remained unchanged after
catch-up. Exact receipts and filtered nonprivate summaries are in `evidence/`.

GitHub requires new scheduled/workflow_run definitions to exist on the default
branch. For these initial probes ONLY, a separate test branch installed the
identical consumer under an already registered workflow filename. That branch
is never a production merge source; the main PR keeps the original producer/Pages
file byte-identical. These probes verify consumer behavior and permissions,
not actual default-branch timer/event delivery. Main-only schedule/event registration
must be reported separately from a feature-branch manual probe. No main activation,
production merge, app deploy or private storage permission change is implied by
a successful branch run.

## Release blockers

- Public schema, no-overwrite and source/identity rules: covered by inherited/new tests.
- GitHub writer/readback and new-original discovery: verified in the two live probes and independent recovery.
- Official next-origin/missing-GW monitoring: live probes report origin12covered and no missing completed origins; synthetic negatives fail correctly.
- Actual `schedule`/`workflow_run` delivery on main: requires reviewed integration into the default branch; cannot be self-certified from an unmerged PR.
- Unfinished PR44/46app/private work: excluded, no dependency for this PR.
- Private TSdurability and authenticated execution: unresolved, unchanged, no enabling code copied.

The only integration permitted here is the isolated public consumer. No full-stack
merge, model optimization, historical experiment rerun or app deployment.

Branch-protection configuration could not be inspected with the connected token
(HTTP403). No policy was weakened and no administrator override/direct main push
is permitted. The normal PR/check/review/merge mechanism must enforce repository
requirements. Existing workflow push filters were inspected: this public-only
diff matches no producer/app-deploy push trigger.

## Main activation — actual result

**PR #52 merged normally** as0d0690d9108b762931ea6161ac95445804592640.
PR44,46and51remain OPEN. Their app/private stack was not merged. No admin
protection override or direct main push was used; GitHub public-only PRtest
run45138593147passed27tests with publication skipped.

GitHub registered `public-forecast-archive.yml` as ACTIVE (workflow427556513).
Actual main run45138854260SUCCEEDED on0d0690d9. It was an explicitly labelled
manual catch-up, using the same discovery path as schedule. It verified current
GW12coverage with no missing completed origins, skipped all6already retained
original runs, and preserved existing asset IDs/digests/clocks. A second independent
Release-only recovery after this main run succeeded. Exact main-run, summary,
recovery and tested-code receipts are in evidence/main-*.json and main-summary.txt.

**Configured, not yet observed:** first actual `schedule` or `workflow_run` event
on main. Do not relabel the manual main run as a timer run. Both triggers are
registered/enabled; normal monitoring must confirm their next delivery. GitHub
cron is best effort. This remaining observation is not an unresolved PR44/46
integration dependency and does not justify triggering a model/app job.

### Final release-blocker status

| Gate | Result |
| --- | --- |
| Public component isolated; no full-stack dependency | PASS |
| Local and read-only PR CI | PASS,27tests |
| New original discovery, catch-up, no-overwrite, independent recovery | PASS, live branch probes and main recovery |
| Main registration and execution permissions | PASS, ACTIVE workflow and successful main execution |
| Actual first timer/producer-completion delivery | Pending next natural event; configured and monitored, not falsely certified |
| Original producer/Pages/protected trial unchanged | PASS, byte comparison after merge |
| Private TSstorage/authentication | Still unresolved and fail-closed; excluded, not a public-archive blocker |

No changes to MM B, PM vFinal, TS v3, app, substitutions or historical research.
