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
