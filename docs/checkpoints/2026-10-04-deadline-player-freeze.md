# Common player components frozen at one GW deadline

Continues `229784dc6f1670cceb3c5dca39a1bdff6f09400e`. No archived input/output
was overwritten and no parameter was refitted. The new frozen experiment has
13,955 player-fixture rows, including all 15 first entrants with verified
predeadline FPL team/position evidence. The remaining 32 roster rows are saved
explicitly and block 26 whole fixtures from complete-roster replay.

For each cutoff the generator queries only current-season observations whose
kickoff+3h is before the cutoff, deduplicates exact logical records and rejects
conflicts. Kickoff+3h is an explicitly declared conservative event-availability
guard, not an invented authoritative publication timestamp. In this actual
period the most recent source kickoff is at least 46.5 hours before cutoff.
Player components share a common state and are not updated between target
fixtures, including DGWs. Targets and candidate minutes are not evaluated.

Lossless parts include component rates, blocked roster rows and per-deadline
history summaries. The manifest preserves code/parameter/source hashes and
Core database checksum. The checker validates original-roster partition,
predeadline state, packed bytes, rate/probability bounds and DC exposure identity.
114 tests pass; all seven new causal/contract tests pass.

Team/keeper input verification is next. Source inspection shows the selected
Phase5E latent team-goal model is already grouped by prior GWs, unlike its
fixture-sequential raw baseline. No prior-GW source row lies after the target
cutoff+availability guard in this diagnostic period. This refines the earlier
general team-goal timing warning; the selected latent means need not be
replaced merely because the raw baseline is sequential.

The original keeper CSV uses attacking `team_id` and defending `opp`. The old
paired-input loader joined `team_id` as keeper team. Keep that diagnostic
unchanged; the new input version must make defending-team mapping explicit.
Keeper state must also be batched at deadline with its original frozen SOT/save
parameters. Transfer/chip strategy, simulator, adapter and scoring stay fixed.

Reproduce: `PYTHONPATH=src python scripts/check_deadline_player_components.py`.
Next: finish common team/keeper inputs and preflight an explicit complete-fixture
paired cohort; the 32 unverified roster rows remain a concrete full-period gap.
GW22–38 remains reused diagnostic, not a new holdout.
