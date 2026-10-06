# Official Team News / availability research checkpoint

Research and data audit only. No MM, PM or TS mathematics, duration model, weights, P(start) adjustments or final integration are changed. This checkpoint began by reading branch HEAD `c8094985421db7a65370739632b421b498554e28`; publication uses the latest branch tree and preserves other work committed concurrently.

## Sources and what each can establish

| Source | Useful evidence | Historical cutoff requirements |
|---|---|---|
| [Official FPL bootstrap API](https://fantasy.premierleague.com/api/bootstrap-static/) | Player listing, FPL ID/code, club, status, news, news_added, chance_of_playing_this_round, chance_of_playing_next_round; events.deadline_time | Capture the entire response at observation time. Current response is not a historical API. No discovered endpoint accepts a historical bootstrap as-of timestamp. |
| [PL injury hub](https://www.premierleague.com/en/news/4242565) | Club injury summaries and links to official club announcements | Mutable article. Observed header 22 January 2026 and body update 29 January at 16:14 GMT differ. Historical header date cannot date the current body. Preserve a version/hash before using it. |
| [PL suspension hub](https://www.premierleague.com/en/news/4425344) | Confirmed bans, affected GWs, disciplinary explanation | Also a living page; observed September 2026 header with October update. Risk of a future ban is not a current suspension; validate competition and affected fixtures. |
| Official club press-conference reports linked by PL | Named injury/doubt/return statements; sometimes precise publication time | Preserve the relevant statement, club/player/fixture and publication/modification timestamps. A return to training is not proof of match availability. Example [Chelsea report](https://www.chelseafc.com/en/news/article/enzo-maresca-delivers-chelsea-team-news-ahead-of-newcastle). |
| PL/FPL dated GW guides | Historical editorial mentions or explicit availability statements | A guide's link to a live hub does not freeze that hub's historical content. Date-only same-day publication is insufficient before an intraday deadline. |
| [PL predicted line-ups example](https://www.premierleague.com/en/news/4720146/predicted-line-ups-for-premier-league-teams-in-matchweek-5) | Editorial expected selection and linked club news | The inspected example is 2026/27, not evidence for 2025/26. Editorial predictions are not confirmed starting XIs, medical clearance or probabilities. Do not use post-deadline announced XIs. |
| [Official Player Notes announcement](https://www.premierleague.com/en/news/4485566/new-player-notes-feature-warns-fpl-managers-of-possible-upcoming-absences) | Future cautions: booking threshold, AFCON, parent-club loan fixture and blank GW | Feature introduced 5 December 2025. Do not infer that all earlier payloads contain it or treat a warning/BGW as current injury or suspension. Bootstrap schema audit records actually present keys. |

Research capture metadata and repo file inventory are in `analysis/results/team-news-source-research-20261006-v1/`. Retrieval today is distinguished from an old page's claimed publication date. Sources that fail direct retrieval remain documented failed probes, not fabricated downloaded evidence.

Historical official editorial anchors inspected:
- [GW1 guide](https://www.premierleague.com/en/news/4373995/quick-fantasy-tips-your-basic-guide-to-gameweek-1): 11 August 2025; GW1 deadline 15 August 18:30 BST = 17:30 UTC. Mentions Rogers/Kelleher/Kluivert without itself establishing all three availability states.
- [GW12 guide](https://www.premierleague.com/en/news/4462450): 21 November 2025, deadline 22 November 11:00 GMT. Contains an explicit Gabriel injury statement; other player mentions alone do not establish a verdict.
- [GW38 guide](https://www.premierleague.com/en/news/4664134/everything-you-need-for-gameweek-38-of-fpl-with-the-latest-tips-and-advice): 22 May 2026, deadline 24 May 14:30 BST = 13:30 UTC.

No completeness claim is made for a player-by-player article reconstruction. Today-visible article bodies without historical versions cannot supply a complete cutoff-certified ledger. They are candidate supplements for missing observations, not automatic substitutes for snapshots. No article-derived player verdicts are inserted into this ledger without version evidence and identity review.

## Existing repo evidence and historical reconstruction

The repo already held more original availability evidence than the earlier model feature files showed:
- `analysis/results/joint-deadline-snapshots-v1/`: 17 complete, losslessly split bootstrap snapshots, GW22–38. Raw payloads retain news/news_added; the older derived states CSV retained status/chances but not those news fields. Existing identity audit mapped 13,956 rows with zero unresolved.
- `analysis/results/joint-deadline-snapshot-selection-v1/selection.json`: pinned source paths, Git blob SHAs, archive creation commits and cutoff selections.
- `analysis/results/blocked-roster-bracket-v1/`: 31 original post-deadline bootstrap snapshots and publication metadata. These are exclusion/audit evidence for their original GW. A later snapshot may become legitimate evidence for the next GW only after its availability time.
- `analysis/results/blocked-roster-source-index-v1/`: frozen archive month trees. Core lineup/formation/average-position extracts are not Team News snapshots.

Historical official API response values are recoverable from the already used **data source** [Randdalf/fplcache](https://github.com/Randdalf/fplcache), pinned to `17e703acd4f744931afa9d1d90a2998cfb104286`. This third-party archive is not the project/model source of truth or an official host. Every selected immutable payload URL is pinned to its path-specific commit and its bytes must match the frozen Git blob SHA. The archived cache code fetches the official bootstrap API. Git paths are nominal runner clocks, not official news publication timestamps.

The audit samples the nearest nominal pre-deadline capture and first nominal post-deadline capture for all 38 GWs. Official deadlines come from the verified final snapshot and are checked against each selected historical payload's own event deadline. This indexes the audit and does not backfill later FPL player attributes before they were observed.

A complete sampled snapshot is not proof of minute-by-minute historical news completeness. Snapshots are usually hours before deadline; updates in the remaining interval can be missed. Old seasons exist in the archive, but only 2025/26 has been audited here. Identity joins are exact season-scoped FPL element + independently verified FPL code to existing frozen Core UUIDs; no fuzzy matching or future roster inference.

## Timing and append-only contract

Three different clocks are retained:
1. `observed_at`: nominal capture time inferred UTC from the archive workflow/runner; path resolution is minutes.
2. `archive_clock_effective_at`: max(nominal capture, self-reported Git committer time); conditional evidence only.
3. `effective_at`: conservative historical server job completion bound, or server run updated upper bound when a job timestamp is absent; always at least the archive clock time.

A successful archive job is linked through its run HEAD to the source commit's parent. Historical `cache.py` and cache workflow are verified byte-for-byte against the inspected pinned fetch-then-commit/push pipeline. GitHub job completion after the final push is the conservative availability bound. This is a documented inference about archive availability, not a PL news publication timestamp. `run.updated_at` can change much later than original completion, so the audit prefers the original successful job's `completed_at`.

The strict projection requires verified timing, matching official deadline and `effective_at < cutoff`. Equal-to-deadline rows are excluded. Future `news_added` values are excluded from their observation. The clock-only projection is a separate conditional dataset and must not silently replace missing strict evidence. `news_added` dates a news-field update, not every status/chance change; it must never backdate current status or chance values.

The bootstrap cohort is the set actually listed in the chosen historical snapshot, including unavailable/unselectable players. Absence does not mean AVAILABLE, OUT, legally eligible, or that a later FPL listing existed earlier. The ledger preserves both FPL ID and stable code so season-scoped IDs cannot accidentally join the next season.

New output directories are required: the collector refuses to overwrite a prior version. Raw observations are immutable source/player facts with original audit GW. Derived per-GW projections select only earlier evidence. If no newer observation exists, earlier status may be carried forward with its original source/effective time and staleness. The exporter distinguishes `carried_from_earlier_gw` from `unchanged_news_since_previous_gw`: freshly reconfirmed unchanged text is not a missing-snapshot carry.

## Proposed normalized states (research labels only)

| Raw evidence | Proposed state | Meaning / restriction |
|---|---|---|
| status=a | AVAILABLE | FPL currently lists no unavailable flag; does not guarantee fitness, selection or minutes. |
| a after previously observed d/i/s/u | RETURNED_AVAILABLE | Observed flag restoration; not inferred from training alone or future appearances. |
| status=d, scoped chance absent or >25 | DOUBT | Preserve the original chance/news. |
| status=d, scoped chance <=25 | MAJOR_DOUBT | Descriptive official chance category; no model coefficient or probability calibration. |
| status=i or u | OUT | Generic FPL unavailability; u may concern transfer/unavailability rather than injury. Preserve news/reason. |
| status=s | SUSPENDED | FPL suspension flag; do not derive from approaching a booking threshold. |
| status=n, null or unrecognized code | UNKNOWN | No forced inference. |

Null chance is not zero. `chance_this_round` and `chance_next_round` are retained verbatim alongside `payload_current_event`/`payload_next_event`. `scoped_chance` is populated only when that event ID equals the projected GW. On carry-forward, an old round's chance is not relabelled as the new GW's probability. These are appearance availability flags, not P(start), expected minutes or a reason to change duration models. If status and chance/news disagree, retain the raw contradiction for review rather than inventing a resolution.

## Files the later integration can read

Dataset directory: `data_v1_1/derived/team_news_audit/2025-26-v2/`.
- `observations.jsonl.gz`: append-only raw selected observations, including post-deadline and unverified records. **Not directly an eligible feature table.**
- `predeadline_strict.jsonl.gz`: research-only cutoff projection; correct starting input for a later integration. Require timing_verified, mapped identity, effective_at < cutoff and inspect UNKNOWN/state staleness.
- `predeadline_archive_clock.jsonl.gz`: conditional sensitivity/recovery reference; explicitly weaker temporal evidence.
- `coverage.csv`, `summary.json`, `deadlines.json`: per-GW coverage, counts, cutoffs and gaps.
- `source_manifest.json`: immutable raw URLs and hashes, commits, historical pipeline hashes, server run/job IDs, metadata URLs and clock basis.
- `SHA256_MANIFEST.json`: hashes of the complete dataset files. If Git storage splits gzip bytes, restore using `restore_team_news_audit.py`; never parse an individual part as a complete gzip.

Rows include season, GW, cutoff, UUID, FPL element/code, player name, historical team, observed/effective times, source/source_id/URL/commit, raw_status/raw_news/news_added, both raw chance fields, their event scopes, proposed state, identity status, timing_verified, timestamp_basis and eligibility/carry/staleness flags. Source IDs identify the immutable archive commit and path. The integration should join by season + FPL element or existing UUID, not name alone. No production feature/model reader has been wired up in this checkpoint.

Reproduce online (Python standard library; frozen Core needed for identity only):

```bash
python scripts/restore_core_checkpoint.py --out work/core.sqlite3
python scripts/audit_fpl_team_news.py --out work/team-news-new-capture
```

Reproduce projections offline without network, Core or model code:

```bash
python scripts/restore_team_news_audit.py
python scripts/audit_fpl_team_news.py --rebuild data_v1_1/derived/team_news_audit/2025-26-v2 --out work/team-news-offline-rebuild
python tests/test_team_news_audit.py
```

Exact observed coverage and validation results are in `analysis/results/team-news-availability-audit-20261006-v2/report.md`. No availability weights, lineup predictions, model simulations or forecast promotion are part of this checkpoint.
