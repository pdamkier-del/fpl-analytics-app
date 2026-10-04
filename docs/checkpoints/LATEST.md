# Latest continuation checkpoint

Read [complete legacy rolling recovery](2026-10-04-legacy-rolling-recovery.md).
Continues 223d5de261d5d86b862695f4f5a73f4178f47fe6; no restart or active model change.

Original Phase 5T/5W/5Y forecasts and builder are recovered with checksums:
163,459 player/GW rows, 165,900 player/fixture rows, 38 origins and 213 legacy
horizon cells. 191 integrity checks pass and recovery reproduces byte-for-byte.
All original estimated deadlines match the recovered calendar.

The old builder uses same-GW historical metadata and final-season schedules.
All 32 unverified roster rows occur in its own-GW forecasts. These are legacy
Phase5Q outputs, not v4; no forecast is promoted and no missing v4 horizon cell
is resolved. The selected-v4 coverage audit still has 196 missing horizon cells.

The completed 144-fixture control/v4 paired diagnostic, original adapter and
simulator, Core and transfer/chip policy remain unchanged; saved model tests
remain 125 passed. GW22–38 is reused diagnostic, never a new holdout.

Next: recover timestamped early-season player/price/schedule snapshots and
prepare v4 fixed-origin generation from verified as-of histories. Preserve the
32-row/26-fixture roster gap; do not use quarantined legacy metadata or later
forecasts to fill it. Separately controlled mechanics integration and the
existing scoring audit remain gates before full-season decision replay.
