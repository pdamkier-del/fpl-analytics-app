# Existing before-deadline capture: verified coverage and C2 requirements

Read-only observation, 22 November 2026, 22:29 Copenhagen. No workflow triggered,
private manager payload inspected, application edited or new pipeline developed.
Receipts and exact public workflow/source copies: [capture_evidence/](capture_evidence/).
This refresh supplements PR41/42/49; it does not rescore their old outcomes.

## What exists

The current public chain still identifies source `161b67b6`, forecast
`7a890e936b6622b4af5bb417491c8ee534cb5b7170b3a6dcf558515a71c7894d`,
and publication run44892997536. Its source cutoff is21November10:23:05UTC,
deadline11:00UTC; manifest recorded_at10:38:03UTC; GitHub's successful publication
job ends10:43:29UTC. That is consistent with before-deadline GW11 publication.
GW11 is now underway, so these are **not fresh registered outcome holdouts**.

| Contract | Observed evidence | Remaining qualification |
| --- | --- | --- |
| Model/source identity | B-MM-PM-TS-v1; integrated-source-event-repair-v2; component names, MMversion, sourcecommit, code/input hashes | Friendly labels alone are insufficient; retain exact hashes/config and rulebook per issue. MMdocument still says deadline_correct=false, independently_validated=false; provenance is not full scientific certification. |
| Forecast bytes | Current forecast12,787,287bytes and MM4,436,264bytes match both index SHA256 values | Current paths are mutable; retain original issue files separately for future research. |
| Player/fixture identity |672unique playerIDs, no missing UUID;4,032player-fixture rows; public ledger4,032unique keys,0missing stable FPLcodes | Persist origin-specific official fixture/element/code mapping; prove postponed/DGW/blank and transferred-club mappings, not just this regular horizon. |
| Six-GW input | All672players have exactly GW11–16; forecast has shared points/minutes scenarios, contract400draws | Field presence and claimed shared alignment checked; no new full probabilistic/rule certification or complete per-draw BPS ledger inferred. |
| Marginal evaluation ledger |4,032rows, sixGW, p_start/p_play/P60/P90/xmins/xP/components, original hash and timestamp; compressed payload matches manifest SHA256 | Ledger does not preserve full scenario arrays or private TS plans. Reuse original forecast for distributions/decision replay. |
| External timing witness | GitHub metadata lists ledger artifact14704310132created21Nov10:42:34UTC,90-day retention; successful run before deadline | Redirected artifact body could not be downloaded here. Current Pages ledger hash verified, but original artifact contents were **not** independently matched to those bytes. Do not upgrade self-reported clocks into fully verified original-vintage certification. |
| Repeated collection | Existing hourly Bpublication and hourly sourcecapture; weekly report workflow | Three latest publication runs failed; latest45061627661computed successfully but preview failed. Pages still GW11. Three sourcecapture runs succeeded, but that workflow explicitly captures **sources, not Bforecasts**. Weekly report's latest three runs failed. Success of sourcecapture does not imply forecast/evaluation success. |
| Private TS decisions | PR42logger exists; PR43/44still open drafts at unchanged recorded heads | No durable private before-deadline end-to-end capture demonstrated. PR43original-worker bench-label gate remains failed in its recorded evidence. No genuine relevant private states available to this study; no realistic-state or realized-policy comparison performed. |

The existing `analysis/archive_prospective_player_forecast.py` already exports
public marginal rows with a real clock, hashes and eligibility. It overwrites a
single output filename; mutable Pages plus90-day artifacts do not themselves
guarantee permanent, append-only, every-GW retention. Its exact observed source
is retained here. `build_preview_history_archive.py` exports historical actuals;
that is not a substitute for original forecast vintages. PR41's GW8–10archives
remain seen development data, not newly obtained validation. The separate older
diagnostic workflow is not evidence of complete B/shared-scenario TS capture.

## Concrete C2 delivery contract — reuse existing producer and private logger

1. **Immutable issue manifest and availability gate.** Save original MM/PMfull
   forecast, scenarios and index under unique season/origin/issue/hash; preserve
   all revisions. Include actual computation/record/publication clocks, official
   deadline, sourcecommit, full TSconfig hash, model/rule/schema versions, input
   hashes and identity mapping. Verify bytehashes and original immutable artifact
   body/publication witness before marking eligible. Retain beyond artifact expiry;
   failed/stale/missing origins must be visible, never silently reconstructed.
2. **Private state and plan capture.** At successful original before-deadline TS
   calculation reuse its exact forecast/state/plan, with sixGW, all15players,
   purchase/current/selling prices, bank, FT, C/VC, XI/orderedbench, chip status,
   recommendation and same-state keep-squad control. Separate intention and verified
   executed transfers with independent event/timestamps. Store privately with
   tested permissions, durability and replay; fail closed if absent. Resolve and
   retest the documented original-worker bench-role mismatch. No private exports
   to repository, Pages or public CI artifacts; public reports need aggregation.
3. **Final labels and original-origin joins.** Reuse existing outcome/report
   code, require final&&data_checked, retain result revisions, fixture-level
   identity and rulebook. Test blank/DGW/postponement and missing inputs. Six-GW
   targets overlap: prospective uncertainty needs whole-GW/appropriate temporal
   blocks; recommended, intended and executed policies are distinct estimands.
4. **Operational evidence, not just code.** Demonstrate an eligible original
   capture, recover/replay it after restart, reject late/partial captures, and
   produce a finalized report with no private leak. Neither an open PR nor a
   scheduled job is sufficient evidence these gates passed.

Public forecast input is already substantially available; **private relevant
manager states and certified durable vintages are the blockers**, not a reason
to invent a replacement collector. C2implementation/review remains separate.
Estimated engineering order:1–3days for retention/provenance verification and
private replay gates, contingent on storage access; calendar time for fresh final
GWs is additional. This is an estimate, not measured work or authorized deployment.
