# Issue 23: joint GK safety correction (not released)

Based on PR22 c60b6bd, which includes PR18. Production remains inactive and the
locked default sampler is unchanged. This is an incomplete delivery, not a
certified new MM/PM model or a deployed preview.

## Implemented

The opt-in joint GK kernel now rejects unverified roster completeness, invalid
probabilities, incomplete/excess start mass and a shortened starter duration
without an eligible reserve. It never normalizes a partial roster into a certain
starter. Callers must explicitly supply `verified_goalkeeper_roster_teams` from
source evidence; merely having a single official FPL player is insufficient.
An unknown keeper must be an explicit input with documented probabilities, not
a fabricated player or an automatic reassignment to the sole known keeper.

Conditional duration reuses the existing experimental mean-preserving Normal
kernel (sigma 10), rather than PR22's extra substitution coin which failed to
preserve its conditional mean. The reserve receives exactly the remaining
interval, with no overlap. `joint_goalkeeper_expected_minutes` exposes the exact
marginals for comparison with MM. Reserve cameo probabilities act as conditional
replacement selection weights in this experimental kernel; they are not locked
PM independent cameo marginals. This change is experimental PM mathematics and
has not been activated in the current B pipeline or TS.

## Source-backed Penders diagnosis

The current diagnostic release was recovered through the repository's existing
checksum-verified restore, using the public selector on
`free-github-static-20261010`. Its source receipt is
`2026-10-18T14:00:27.092061+00:00`; bootstrap SHA256:
`c18a54c53dbc978e8998efc53f4292d9ea59383aaba742a6ceb99521063b05b1`.
This is a restored snapshot, not a fresh direct API acquisition.

Chelsea's official FPL snapshot has Martinez injured (head injury, unknown
return, chance 0); Sanchez and Jorgensen unavailable on loans; Penders available.
The official FPL roster alone does not certify the entire available club squad.

The following is the **locked current input**, not an authentic B after-change
forecast. Fixture `live-2026-27-fpl-73`, GW8, 400 draws, seed 93000000:

| Quantity | Existing locked input/output | Joint after correction |
| --- | ---: | --- |
| Penders p_start | 0.6147737705505526 | Not Available |
| Conditional starter minutes | 78 | Not Available |
| MM xM | 49.20009494390442 | Not Available |
| PM analytic E[min] | 48.859510461213034 | Not Available |
| PM sampled E[min] | 48.85 | Not Available |
| PM xP | 2.5325 | Not Available |

Bench cameo probability is 0.2082247224990318 and conditional cameo minutes
15.555223258097357. Thus clipping accounts for only about 0.34 minutes of the
MM/PM discrepancy here; incomplete GK start mass and the 78-minute conditional
duration are separate upstream problems. Forcing p_start=1 and s=90 would change
both probabilities and points without verified roster evidence.

The restored locked six-GW input spans GW8-13 and 120 team-fixtures. None has GK
start mass equal to one (range 0.6147737705505526 to 1.133006420472415). These
inputs cannot be activated as a joint exclusive GK forecast without a verified
upstream bridge. This is a preflight diagnosis, not a six-GW B validation.

## Validation and outstanding work

- 694 Python tests passed after the correction; 39 targeted GK/bridge tests.
- 36 existing JS contract/jobs/personal-view/adapter assertions passed.
- Exact PR18 locked-default parity across 100 seeded match simulations, all
  result fields compared. No assertion of byte-identical source code.
- Core and MM capsules restored with original checksum validation.
- Desktop API health and model status respond; this verifies the desktop
  passthrough application, not a working current B forecast.
- Historical matched-cohort GK Brier/minute MAE/xP MAE/bias, authentic B MM mean
  alignment, one-match/full-GW/six-GW joint validation and exact-source CI/deploy
  remain outstanding. No reused old results are claimed as fresh validation.

First blocked operations: `curl -fsSL
https://api.github.com/repos/pdamkier-del/fpl-analytics-app/issues/23` and
`curl -fsSL https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/live.html`
returned 403. Direct official bootstrap request failed CONNECT with 403 as well.
The issue body was read successfully from github.com HTML; the official snapshot
was recovered via checksummed GitHub release. These fallbacks do not establish
API write permissions or a live browser/deployment check.

Environment draft saves include the additive required custom domains
`api.github.com`, `pdamkier-del.github.io`, `fantasy.premierleague.com`, plus
installation and startup instructions. Saving the draft does not apply or publish
it. Review/save environment settings, then publish the environment to apply the
network changes. No credentials were requested or exposed.

## Additional recovered B preview evidence

After the initial blocked Pages request, the public B assets were recovered
from `free-github-static-20261010/app/mm-preview/current/` using
raw.githubusercontent.com. Every downloaded forecast/MM/catalogue/role-ledger
file matched the checksums in its index. This is a recovered published artifact,
not a new publication or a successful request to the Pages host.

B index data_asof: `2026-10-18T14:41:38.075226+00:00`; forecast file SHA256:
`e078227a833f868198cef3a0e6232e7500247f789a2603ebbc2cfe36e62fe80f`.

| Penders GW8 quantity | Existing B preview | New joint preview |
| --- | ---: | --- |
| p_start | 1 | Not Available |
| MM xM | 78 | Not Available |
| PM analytic E[min] | 77.43978449733301 | Not Available |
| PM sampled E[min] | 77.9875 | Not Available |
| xP | 3.965 | Not Available |

Unlike the locked-input preflight above, all 120 **B** team-fixtures have GK
start mass equal to one. None has analytic PM GK minutes equal to 90. The
remaining conservation error therefore persists after B start normalization.

The local B page was checked with Playwright and system Chromium against these
checksum-verified recovered assets. It rendered GW8-13, 667 players, 60 matches
and the diagnostic/not-certified status. Before restoring the assets it properly
showed Not Available on the missing current/index.json (HTTP404). No live Pages
browser check or new preview deployment is claimed.

Updates were pushed to the existing PR22 branch; no additional parallel remote
branch or research PR was created. Full Python and JS CI was added at commit
7b2b902; run https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39149557375
was in progress when first inspected. Local pass results do not establish its
remote conclusion.

## Fresh local B chain execution

The missing 2024/25 input archive was restored with the repository's checksummed
restore command. PR4 role-training reconstruction completed: both frozen season
references reproduced within 1e-6. Current NUM feature parity also passed.
Authentic B inputs were rebuilt for 667 players, 60 fixtures, GW8-13 at the
restored current source cutoff `2026-10-18T14:00:39.615446+00:00`.

`verify_current_b_stages.py` passed the real one-match (66 player-fixture rows)
and full-GW8 (667 rows, 10 matches) checks. The unmodified locked B->PM six-GW
entry point then completed 4,002 player-fixture rows, 60 fixtures, 400 draws each,
with point components reconciled. This validates the existing diagnostic chain,
not the new joint GK kernel. Its MM/PM maximum analytic minute discrepancy is
3.934590524959731, so its mean-consistency gate remains false. Personalized TS
was not run: no actual private manager state was supplied, and no manager was
fabricated. Production stays inactive.

On this fresh B run Penders GW8 remains p_start=1, xM=78,
PM analytic minutes=77.43978449733301, sampled minutes=77.81, xP=3.94. These
numbers differ from the recovered deployed snapshot above because the source
cutoff/seed indexing is a different run; they are not a joint-model improvement.

CI for commit 995c6b1 completed successfully:
https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39149720827

A direct Playwright navigation to the public Pages host failed certificate
validation. Automatic approval review rejected importing the platform proxy CA
into the browser's persistent trust store, citing the broader TLS trust change.
No TLS checks were disabled and no workaround was used after that rejection.
Explicit user approval is pending separately. The network policy still requires
the saved domain changes to be applied before API/deploy access can be checked.

The full six-GW diagnostic execution was repeated with the same immutable
inputs. `cmp` passed for both forecast.json and mm.json; both registered MM
snapshots have SHA256
`8bccf457a58dcfe7f84bebee1782c8be6a9416889e3673bc395d4cd99b4945a1`.

## Approved browser trust and successful live verification

The user explicitly approved the platform proxy CA installation on 2026-10-18.
The CA is trusted in the browser's local NSS stores. Chromium required write
access to initialize its NSS database, so the approved browser check was run
with that filesystem access and TLS verification enabled. Public Pages returned
HTTP200. The page verified its snapshot checksums and rendered the actual
Penders row: xM78.00, PM E[min]77.44, p_start100.0%, GW xP3.96, six-GW xP6.39.
This verifies the existing deployed preview, not a new joint-GK deployment.

GitHub API and official FPL API access now work. A new direct bootstrap request
confirms the same Chelsea statuses: Martinez injured/chance0, Sanchez and
Jorgensen unavailable on loans, Penders available. The remaining source gap is
an independently evidenced full available goalkeeper squad/reserve set; the FPL
player listing itself does not certify that a sole known available keeper has
no unlisted eligible replacement. Source checks to the official Chelsea men's
squad and Premier League squad pages both failed CONNECT with403. Required
additional domains `www.chelseafc.com` and `www.premierleague.com` were saved
additively in the environment draft. Existing domains and presets were retained.
The saved draft must be applied through environment settings before these
source operations can be retried. No new CA approval is needed.
