# C2 handoff — permanent research-data integration

**Delivered:** [PR #51](https://github.com/pdamkier-del/fpl-analytics-app/pull/51), stacked on #46; no merge or service/app deployment.

22 November 2026. Separate integration branch
`integration/c2-permanent-research-data-20261122`, from PR46 `876e61b0`.
Read [research-data/README.md](research-data/README.md),
[VERIFICATION](research-data/VERIFICATION.md), [C1 contract](research-data/C1_DATA_AVAILABILITY.md)
and the earlier [STABLE-LIVE](model-interface/STABLE-LIVE.md).

## Delivered code and tests

Existing B producer/config/source remains161b67b6. Reuse PR46freeze and
PR42/43 private ledger, observation routes and completion hook. Public archive is
a sibling of Pages, with immutable revision/tag/checksums and independently
recoverable release assets. A manual `research_archive_only=true` verification
must skip Pages. Full model inputs/scenarios are original, not regenerated.

Private integration is installed only on a verified disposable runtime. Known
bench-role mismatch is fixed in validation without rewriting original output.
Store original canonical input/output and prices, and require runtime hash
receipt and secure private mount. No private payload enters Git/Pages/artifacts.
Intentions and reported executions remain distinct, unverified execution never
enters realized-strategy evidence. Existing1 hour capabilities do not create a
durable login after restart; do not claim they do.

47 integration/logger tests,47 pinned service/B tests,13 existing JS contract tests
pass. Actual TSruns on synthetic inputs and private records recover in another
process. Mount and release-backend durability are mocked in local tests; see
the live probe receipt before claiming public production readiness.

## Remaining gates / minimal next steps

1. **Public issue verified:** archive-only run 45076646704succeeded; original
   GW12–17release 454789206/revision90229f06… and all11data/manifest assets were
   independently recovered before27Nov18:30UTCdeadline. Pages and model
   computation skipped. Cold-runner retry 45076965409 also succeeded with all 12 asset IDs/digests/clocks unchanged.
   Next review/activate automatic capture on main. No historical backfill.
2. Confirm the intended Render workspace or existing private host, then inspect its
   storage without guessing. Provision/verify a private persistent mount and
   private backups; no paid resource has been created here. Configure exact
   `FPL_TS_PRIVATE_VOLUME/ROOT`, owner/modes and operator attestation. Run real
   restart and backup-restore tests. Local environment has no such configuration.
3. Review/install this hook on the intended backend only after PR46's service,
   identity, browser and release checks. Public source/forecast must match the
   backend exactly. No service/app deploy was performed in this task.
4. Supply a trusted authenticated private execution/recovery path before claiming
   actual-performed-transfer or realized-policy research. Existing reported
   execution is explicitly not verified official data; do not upgrade it.
5. Activate the reviewed archive job on main without changing any model pointers,
   then monitor missing/late origins, retention, release permissions and label
   finality. Preserve all revisions. Independent backup protects against admin
   deletion; release assets have no artifact TTL but are not magical WORM storage.

Render inspection is currently blocked by unselected workspace, and the local
private service health request timed out. The current Pages forecast was expired
GW11 at observation. Source/job metadata can be verified, but direct artifact
download failed here. Complete unaffected work; do not bypass access or call the
private system operational. C1 gets schemas/tested recovery now, not fabricated
fresh manager observations or permission to rerun completed research.
