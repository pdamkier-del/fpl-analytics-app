# Common deadline joint inputs and controlled cohort

Continues ba0febd847537cf20dbe685f85dd8b24bc688536; old frozen inputs/results are preserved.

Original Phase 3G keeper fit/experiment and Phase 5E team experiment/results recovered with archive/member checksums in joint-team-keeper-recovery-v1. The selected latent team model already updates by prior GW; all 17 target deadlines pass its source-history boundary check, so its exact selected means are preserved without fitting.

The original keeper CSV labels team_id as attacking and opp as defending. New common inputs explicitly key save opportunities by defending team, using the original arithmetic SOT blend and frozen save parameters. SOT histories, player histories, and current-season assist ratio use a declared kickoff+3h guard, not verified source publication timestamps. This is a conservative operational assumption, not a claim of fully audited historical availability.

The new cohort contains 144 whole fixtures, 11,794 rows and 11 verified first-entry priors. Both arms exclude the same 26 whole fixtures because 32 original roster rows lack matching predeadline team/position evidence. No player is silently removed from a retained fixture. Control and v4 minute forecasts are unchanged. Original adapter, simulator, scoring, transfer/chip policy and old diagnostic outputs remain unchanged.

`PYTHONPATH=src python scripts/check_deadline_joint_inputs.py` passes 12,896 checks, including hashes, exact roster partition, original minute identities, team allocation and minute-only adapter differences. Complete-fixture paired replay is technically ready; full-period and full-season readiness remain false. Recover authoritative predeadline evidence for the 32 blocked rows before expanding the cohort. Season scoring/chip audit remains required before full-season decision replay.
