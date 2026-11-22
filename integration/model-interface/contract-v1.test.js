'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { validateForecast, validateOfficialCompatibility, validatePlanIdentity } = require('./contract-v1');
const id = 'a'.repeat(64), stateHash = 'b'.repeat(64);
function fixture() {
  const f = { season: '2026-27', model: 'independent_candidate',
    forecast_sha256: id, data_asof: '2026-11-20T10:00:00Z',
    origin_deadline: '2026-11-21T11:00:00Z', gws: [12, 13],
    players: [{ id: 17, team_id: 1, position: 3, price_tenths: 75,
      weeks: [{ gw: 12, xpts: 5, xmins: 78 }, { gw: 13, xpts: 4.2, xmins: 81 }] }] };
  const official = { next_gw: 12, players: [{ id: 17, team: 1, position: 3, price: 7.5 }] };
  const plan = { forecast_sha256: id, forecast_cutoff: f.data_asof,
    manager_state_sha256: stateHash, gw: 12, ts_ran: true, validation_only: false,
    plan: { path: [{ gw: 12 }, { gw: 13 }] } };
  return { f, official, plan };
}
test('accepts model-independent point-and-minutes adapter shape', () => {
  const { f, official, plan } = fixture();
  assert.equal(validateForecast(f).ok, true);
  assert.equal(validateOfficialCompatibility(f, official).ok, true);
  assert.equal(validatePlanIdentity(f, stateHash, plan).ok, true);
});
test('rejects stale plan after model switch', () => {
  const { f, plan } = fixture();
  f.forecast_sha256 = 'c'.repeat(64);
  assert.equal(validatePlanIdentity(f, stateHash, plan).code, 'stale_or_wrong_team');
});
test('rejects plan computed on another squad', () => {
  const { f, plan } = fixture();
  assert.equal(validatePlanIdentity(f, 'c'.repeat(64), plan).code, 'stale_or_wrong_team');
});
test('rejects official catalog mismatch', () => {
  const { f, official } = fixture();
  official.players[0].price = 7.6;
  assert.equal(validateOfficialCompatibility(f, official).code, 'player_catalogue_mismatch');
});
test('rejects invalid horizon and future cutoff', () => {
  const { f } = fixture();
  f.gws = [12, 14];
  assert.equal(validateForecast(f).code, 'invalid_horizon');
  f.gws = [12, 13];
  f.data_asof = '2026-11-22T10:00:00Z';
  assert.equal(validateForecast(f).code, 'invalid_cutoff');
});
test('rejects incomplete player projections and invalid model metadata', () => {
  const { f } = fixture();
  f.players[0].weeks.pop();
  assert.equal(validateForecast(f).code, 'invalid_player_weeks');
  f.players[0].weeks.push({ gw: 13, xpts: 4.2, xmins: 81 });
  f.model = '';
  assert.equal(validateForecast(f).code, 'invalid_model_metadata');
});
