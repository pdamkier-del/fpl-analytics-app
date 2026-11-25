'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { fromOfficialHistory } = require('./manager-import');

const forecast = { season: '2026-27', gws: [12, 13] };
const entry = 11;
function history() {
  return {
    schema: 'fpl-official-entry-history-v1', entry_id: entry, season: forecast.season,
    availability: { next_gw: 12 }, chips: [{ name: 'bboost', event: 9 }],
    weeks: [
      {
        gw: 11, active_chip: null, entry_history: { bank: 10 },
        picks: Array.from({ length: 15 }, (_, i) => ({ element: i + 1, position: i + 1 })).reverse(),
      },
      { gw: 10, picks: [] },
    ],
    free_transfers: 3,
  };
}

test('official history preserves the latest 15 public picks and leaves economics blank', () => {
  const draft = fromOfficialHistory(history(), entry, forecast);
  assert.deepEqual(draft.squad, Array.from({ length: 15 }, (_, i) => ({ id: i + 1 })));
  assert.deepEqual(draft.chips_used.bench_boost, [9]);
  assert.equal(draft.source_gw, 11);
  assert.equal(draft.gw, 12);
  assert.equal(draft.draft_only, true);
  assert.equal(draft.bank_tenths, undefined);
  assert.equal(draft.free_transfers, undefined);
});

test('official draft rejects wrong entry, stale round, duplicate picks and Free Hit', () => {
  assert.throws(() => fromOfficialHistory(history(), entry + 1, forecast), /matcher ikke/);
  for (const alter of [
    doc => { doc.weeks[0].gw = 9; },
    doc => { doc.weeks[0].picks[0].element = doc.weeks[0].picks[1].element; },
    doc => { doc.weeks[0].active_chip = 'freehit'; },
  ]) {
    const doc = history();
    alter(doc);
    assert.throws(() => fromOfficialHistory(doc, entry, forecast));
  }
});
