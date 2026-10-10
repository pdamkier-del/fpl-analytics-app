# Current original TS and chip integration after GW7 v2

Continues the immutable GW7 v2 publication and branch HEAD `71da234996c834ac0ce21e4f6a393682c8307334`. Original mathematical model sources, coefficients, fitted development constants, TS configuration and TC policy remain unchanged. `locked_model_active=false`.

## Individual source investigation

Every one of the **334** incomplete BPS player-match records was reviewed against **223** historical revisions of the five Premier League player-stat files committed before the forecast cutoff. All 223 files were fetched, checksummed and parsed; no source fetch remains failed. No missing field was recovered in any reviewed revision. The readable individual ledger includes match ID, FPL player ID/name, GW, missing fields and revision count. It is retained with the revision URLs, commit dates and hashes in `analysis/results/live-manager-integration-20261010/`. The original 1,204 verified rows and 334 quarantined rows remain unchanged; absence is never replaced with zero.

The independently maintained StatsBomb public competition inventory does not contain 2026/27 Premier League coverage; its available Premier League seasons are 2003/04 and 2015/16. It cannot repair these matches. FotMob's ambiguous `matchstats.headers.tackles` remains unverified as a replacement for tackles won.

Historical MM registration coverage is 598/599, 614/616, 652/652, 656/656 and 659/659 for GW1–5. All 37 rejected source records have individual evidence. The three registered conflicts are Konsa (GW1, archived club 2 vs observation club 1, explicit zero minutes), Martinez (GW2, club 2 vs 6, 90 minutes), and N. Jackson (GW2, club 6 vs 2, 70 minutes). A zero observation from a different fixture does not prove a zero observation for the archived club. These three remain excluded. The other 34 players were absent from the archived registrations; they are not added retrospectively.

Repository capture times are recoverable, with earliest nonempty files on Aug22 (GW1), Aug29 (GW2), Sep5 (GW3), and later dates recorded in the receipt. These are observations of file versions, not exact first publication times for the provider's final statistics. Neither a final-whistle timestamp nor a Git commit establishes when every subsequently revised provider field first became available. The kickoff+4h proxy is therefore still explicitly unverified and is not silently replaced. This blocks full live certification of historical availability.

## Practical manager integration

Manager State requires a real legal 15-player squad, bank, 0–5 free transfers, each actual purchase price, all four chip histories, the current GW, and a documented state timestamp no later than forecast cutoff. No default test team is assigned to the user. Exported state is parsed as JSON data in Actions, never as shell text. Imported plans must match both the forecast cutoff/GW and the SHA-256 of the saved state.

The page renders original TS starting XI/captain/vice/bench, six-GW actions, official hit points, the locked paid-transfer uncertainty buffer, FT and bank after each action. It compares the original weighted objective with keeping the same squad. Only the first action is current; subsequent actions require replanning. Current FH/WC/BB gains and net threshold values are shown from the original functions. TC remains manual.

The original forecast deadline and the latest official next GW are checked in the browser. At or after the origin deadline, or if the official next GW differs, current manager planning is Not Available. Python manager planning also refuses an expired forecast. GW7 is never relabelled as GW8. No automatically refreshed original forecast is claimed: source capture and release still require a new source checkpoint, completed chain and validation. GitHub's default branch is `main`; workflows located only on this working branch do not establish a default-branch scheduled update service.

## TC scenarios and validation

TC inference uses the same checksummed cutoff snapshot and original models through the current half end (GW19). It uses the original 400 draws, original seed rule, float32 aggregation and top-20 candidates per GW. Future fixtures come from the official FPL snapshot at origin, not a realized later-season calendar. The ordinary six-GW checkpoint is restored after scenario construction and its hashes checked. Two scenario simulations must be exactly identical.

The scenario build produces **104,000** samples (13 GWs × 20 candidates × 400 draws) from 8,671 player-fixture rows across 130 fixtures. Two sample replays are exactly equal, and the GW7–12 simulator input subset equals the ordinary checkpoint exactly. Samples, candidates and receipt are permanently preserved in `model/checkpoints/live_tc_gw7_20261010_v1/`; archive SHA-256 `e2a9d2997fe43ecdf2284a4bfb447f3f772751213851429dc7269b5d5358dc62`. The receipt also links the exact ordinary six-GW input/output hashes. The manager workflow consumes this verified immutable scenario checkpoint.

The labelled synthetic squad integration produces a six-GW TS objective of 88.25657, versus 21.05495 for holding its deliberately cheap test squad. Its first action has five transfers, 12 official hit points and the unchanged 3-point uncertainty buffer. Expected first-GW XI plus captain rises from 9.03675 to 37.96092 before hits. Current chip gains are FH 22.53250, WC 56.37414 (weighted horizon), BB 0.00024; the original coordinator provisionally prefers WC. TC says **SAVE_TC**, 6.26000 use-now value versus 10.419375 save value, driven by its original anonymous DGW prior. Its best concrete future option is Brobbey in GW16 with discounted value 7.79790. This is an option from the original candidate pool, not an owned future player or a committed GW16 chip decision. FH and WC candidate XI/captain/bench are included in the output.

The full original manager-state and result files are saved beside the individual source ledgers. The desktop has a separate labelled validation-output page; it never assigns that squad to the user.

GitHub full regression run `38077145793` passed **385 tests** and all four browser deadline/GW checks despite the then-failing extended-input assembly. Subsequent integration and desktop run results are checked independently; a green regression step does not certify a failed chain. A synthetic legal manager state is used only for regression validation; personalized recommendations remain Not Available until actual state is provided.

A complete joint future four-chip calendar remains Not Available. Current threshold decisions and TC concrete/anonymous DGW option values are not a verified jointly optimized calendar for FH, WC, BB and TC. The original stopping policies require replanning; no invented future manager ownership, chip consumption or calendar is introduced.
