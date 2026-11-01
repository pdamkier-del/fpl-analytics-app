# Transfer waiting-state recovery

The saved manager observation can be newer than the published model capture. The
existing client and Python manager contract then refuse a plan until a later,
verified forecast is published. Saving the team again advances the observation
and can prolong this wait; it is not a repair.

Recovery uses the existing `mm-current-preview-publication.yml` on `main`.
Run 39667840800 completed its numerical job but correctly failed its final live
readiness gate: Saka changed from available to doubtful (thigh injury, official
FPL availability 75%) at 20:30:09 UTC / 22:30 Danish time, after the model's
20:27:29 UTC capture. Its news document captured the change at 20:39 UTC. That
candidate was never published. Run 39673003091 rebuilds with the newer evidence.
No model parameters, production forecasts, actual manager state, purchase prices,
bank or transfers are changed by this recovery.

UI source 6017ea5bb6c8e46b4582833233d9a9e41226728f distinguishes a newer manager
observation from changed official player information. It also reports a source
alignment problem before the unrelated missing-team message in publication
diagnostics. Dashboard and transfer messages use the actual cause. Owned-player
news still excludes other players; off-squad candidates are described separately.

The B-only wrapper update dd225fe087ea661b1181278db3f16eefa228cf39 preserves the
reviewed news UI asset when copying numerical artifacts. It permits reuse only
after the numerical job completed successfully, checks the immutable originating
workflow and exact numerical source and rejects foreign, missing or ambiguous
artifacts. A redundant later UI job may be cancelled; the new publisher reruns
all regression, browser, live-news alignment and production-integrity gates.
Numerical source remains f492be4795bfd630ba91377d71497e68c1d85934.

The new state-machine regression executes the actual manager JavaScript: an old
forecast produces zero submissions, the waiting request survives another load,
a new forecast resumes exactly one private job, a completed six-GW result is
displayed, subsequent loads do not submit again, and the saved state remains
byte-identical. It also supports testing downloaded published B JavaScript via
`MANAGER_SOURCE`; the deployed B version passed the same test.

Validation:

- `pytest -q tests`: 789 passed.
- Targeted manager, refresh and private-service tests: 21 passed.
- Existing B job, catalog adapter, classic manager and team-news JavaScript checks passed.
- Both original manager source and downloaded public B manager passed the new resume regression.
- Five desktop/mobile browser suites passed, including separate changed-news and
  newer-team waiting cases. They retain the request and state and issue zero
  real private POSTs while blocked. Synthetic news is explicitly mocked only in
  these isolated tests; the publication's final live alignment gate is unmocked.

The public catalog and current official FPL source agree: Ødegaard is element 15
and Groß is element 124. No player-ID collision was found. The actual private
browser roster is unavailable to this environment; no Groß-to-Ødegaard swap or
purchase price has been invented.

Full private test receipts and plans stay under `/tmp`. A synthetic remote test
does not establish that the user's own plan has completed.

Identical same-GW team confirmations now retain the original factual observation and state hash. Changed GW, bank or FT still establish a new observation. The six desktop/mobile waiting cases cover both causes and the actual confirmation-dialog/reload flow without reseeding state on reload.

Verified release completed at 23:24 Danish time. Publication run 39677368594
succeeded using the successful numerical job of run 39673003091. The redundant
old UI job was cancelled only after numerical completion. The published model
capture is 23:02:47 and news capture 23:14:04 Danish time. Forecast identity is
`cd1cb5dcb7b16fb46f8ae556e8b6f6adebcce5548c733d34e6b44918cee4d260`.
All 88 production assets remain byte-identical. Served planner/news UI assets
were independently compared byte-for-byte with the reviewed UI source.

An actual private Render six-GW computation completed with a synthetic legal
team; its captain/vice and projected scores independently match the shared PM
scenarios. Its result was then verified on the public desktop and mobile app,
including dashboard-ready state, unchanged synthetic state, identical six-GW
numbers, zero additional jobs and zero page errors. Validation-only results
remain rejected as real personal plans. This does not certify the user's
private roster or claim that their own plan has run.

The rejected pre-injury candidate had Saka at 84.7038 xM, P(start) 0.936673 and
5.73 xP; refreshed public inputs produce 65.5176 xM, P(start) 0.723677 and
4.295 xP. The official FPL 75% availability flag is separate from model P(start).
No individual player parameters were tuned.

Public aggregate receipts are in
`analysis/results/unified-b-chain-20261021/transfer-wait-recovery/`.
Private state, job capabilities and full numerical private plans are excluded.
