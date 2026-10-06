# Team News availability audit — 2025/26

Scope: source research, identity/timestamp audit and immutable research projections only. MM, PM and TS are untouched. No final integration, forecast weights or P(start) adjustments.

## Observed results

- 76 complete bootstrap snapshots (one nominal pre + one post for each GW), 59,294 source-player observations.
- All 59,294 rows map exactly to existing Core UUIDs via season-scoped FPL element + stable FPL code; unresolved=0, ambiguous=0.
- 74 snapshots have historical successful server-job timing and a verified original fetch/push pipeline.
- Strict coverage: **GW2–38, 37/38 GWs**, 28,960 player/GW observations (698–840 players per covered GW). GW1 is excluded from strict input.
- Clock-only conditional coverage: **GW1–38**, 29,645 player/GW observations; GW1 contributes 685 rows with no independent server timing. Additional same-day GW1 06:38/02:08 snapshot creation-parent probes also returned no archive runs. No forced certification.
- Strict unknown normalized states are retained as UNKNOWN; “usable rows” counts eligible observed status records, not a guarantee of player fitness or starting eligibility. See known-state counts in validation.json and per-GW coverage.csv.
- Actual missing-snapshot carry-forward: **0** in either projection; every covered GW has a newer complete pre-deadline snapshot. Strict unchanged status/news across adjacent covered GWs: **25,631** player/GW cases. These are fresh reconfirmations, distinguished from stale observation carry.
- **29,649** sampled player records are excluded as post-deadline for their associated GW. This is an audit of the selected post snapshots, not a count of all archive updates. The same source can be usable later if a subsequent GW cutoff allows it.
- Strict target leakage=0; duplicate source/player/GW=0; duplicate strict player/GW=0; future news timestamps=0; historical deadline mismatch=0; pipeline mismatch=0; out-of-range chance=0.

An important timestamp trap was caught: GW2/GW3 run.updated_at had moved to September/October 2026 while original successful jobs.completed_at remained August 2025. The final dataset uses the original job completion after archive push, not the mutated run metadata. Source manifest records both timestamps and metadata URLs. This remains an inferred conservative archive-availability bound, not the official news publication time.

The chosen pre-deadline captures are hours old (maximum 5.572 hours). Therefore full roster/status coverage does not mean every late press-conference update is observed. A current injury page carrying an earlier publication header is not an eligible historical replacement. Article-based recovery is supplementary and version-dependent; no unverified article verdicts were silently added.

## Coverage by GW

| GW | Strict observed rows | Known normalized state | Conditional rows | Unchanged news | Post-deadline excluded | Age hours |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 685 | 0 | 685 | — |
| 2 | 698 | 696 | 698 | 0 | 699 | 4.645 |
| 3 | 709 | 705 | 709 | 636 | 709 | 3.460 |
| 4 | 738 | 737 | 738 | 570 | 738 | 3.475 |
| 5 | 740 | 740 | 740 | 682 | 740 | 3.454 |
| 6 | 741 | 740 | 741 | 647 | 741 | 3.476 |
| 7 | 742 | 742 | 742 | 696 | 742 | 4.674 |
| 8 | 743 | 742 | 743 | 649 | 743 | 3.442 |
| 9 | 745 | 745 | 745 | 688 | 745 | 4.599 |
| 10 | 746 | 745 | 746 | 669 | 746 | 0.708 |
| 11 | 748 | 748 | 748 | 698 | 748 | 4.424 |
| 12 | 752 | 752 | 752 | 671 | 752 | 4.418 |
| 13 | 755 | 755 | 755 | 697 | 755 | 0.650 |
| 14 | 755 | 754 | 755 | 722 | 756 | 5.030 |
| 15 | 758 | 757 | 758 | 698 | 758 | 4.388 |
| 16 | 759 | 759 | 759 | 680 | 759 | 0.632 |
| 17 | 760 | 728 | 760 | 666 | 760 | 4.355 |
| 18 | 770 | 738 | 770 | 709 | 770 | 5.572 |
| 19 | 775 | 742 | 775 | 714 | 775 | 5.027 |
| 20 | 780 | 749 | 780 | 704 | 780 | 4.321 |
| 21 | 790 | 762 | 790 | 734 | 792 | 5.516 |
| 22 | 796 | 781 | 796 | 641 | 796 | 4.334 |
| 23 | 802 | 802 | 802 | 706 | 802 | 4.317 |
| 24 | 808 | 807 | 808 | 713 | 808 | 0.447 |
| 25 | 817 | 817 | 817 | 730 | 817 | 5.234 |
| 26 | 817 | 816 | 817 | 748 | 817 | 4.314 |
| 27 | 817 | 817 | 817 | 745 | 817 | 0.433 |
| 28 | 818 | 818 | 818 | 771 | 818 | 5.253 |
| 29 | 819 | 819 | 819 | 771 | 819 | 4.758 |
| 30 | 820 | 819 | 820 | 737 | 820 | 0.359 |
| 31 | 822 | 821 | 822 | 758 | 822 | 5.232 |
| 32 | 825 | 824 | 825 | 737 | 825 | 4.050 |
| 33 | 826 | 826 | 826 | 745 | 826 | 2.666 |
| 34 | 829 | 829 | 829 | 784 | 829 | 3.577 |
| 35 | 830 | 830 | 830 | 779 | 830 | 3.768 |
| 36 | 832 | 831 | 832 | 764 | 832 | 1.928 |
| 37 | 838 | 835 | 838 | 790 | 838 | 3.099 |
| 38 | 840 | 838 | 840 | 782 | 840 | 4.835 |

## Reproduction and hand-off

Primary input: data_v1_1/derived/team_news_audit/2025-26-v2/predeadline_strict.jsonl.gz, restored from checksum-verified lossless Git parts. Raw observations, immutable sources, deadlines and weaker clock-only projection are stored alongside it. Fields include cutoff, UUID/FPL element+code, historical club, observed_at/effective_at, source URL/ID, raw_status/raw_news/news_added, both chance fields and event scopes, normalized state and timing/identity/carry flags.

Collector: scripts/audit_fpl_team_news.py. Source/schema research: scripts/research_team_news_sources.py. Restoration: scripts/restore_team_news_audit.py. Rules/limitations: docs/checkpoints/2026-10-06-team-news-availability-research.md. Four focused research contract tests passed. Both online collection runs also passed an offline byte-for-byte dataset rebuild, without network or model code during rebuild.

Validated runner: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/37492277095, code commit 341480b28d2e303b06d09841c9829e81d27fac7a. Preliminary runner fbbfd5c was refined after the mutated run timestamp trap; final published dataset is v2 only.

The future integration must choose evidence tier explicitly, reject effective_at >= cutoff and unmapped identities, retain null chances, respect event scope, preserve stale sources, and treat UNKNOWN/absence/training/availability distinctly. No inference of P(start), minutes or suspension duration is made here.
