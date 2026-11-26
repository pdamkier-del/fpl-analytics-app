'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { create } = require('./manager-store-v1');

const squad = Array.from({ length: 15 }, (_, index) => ({
  id: index + 1, purchase_price_tenths: 50, position: index + 1,
}));
const state = { squad, gw: 14, bank_tenths: 10, free_transfers: 2, captain: 1, vice_captain: 2 };

function storage() {
  const records = new Map();
  return { getItem: key => records.get(key) ?? null, setItem: (key, value) => records.set(key, value) };
}

test('legacy state is shared across clients and retains optional fields', () => {
  const browser = storage();
  browser.setItem('fpl-manager-state-v1', JSON.stringify(state));
  const dashboard = create(browser);
  const transfers = create(browser);
  assert.deepEqual(dashboard.read(), state);
  dashboard.save({ ...state, bank_tenths: 12 });
  assert.deepEqual(transfers.read(), { ...state, bank_tenths: 12 });
});

test('invalid and draft inputs leave the confirmed squad intact', () => {
  const store = create(storage());
  store.save(state);
  for (const rejected of [
    { ...state, squad: squad.slice(1) },
    { ...state, squad: [...squad.slice(1), squad[1]] },
    { ...state, draft_only: true },
    { ...state, validation_only: true },
  ]) assert.throws(() => store.save(rejected));
  assert.deepEqual(store.read(), state);
});
