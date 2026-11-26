'use strict';

const assert = require('node:assert/strict');
const readFileSync = require('node:fs').readFileSync;
const test = require('node:test');
const { runInNewContext } = require('node:vm');
const FplModelContractV1 = require('./contract-v1');

const now = Date.parse('2026-11-21T10:00:00Z');
const forecast = {
  model: 'model-v1', season: '2026-27', forecast_sha256: 'a'.repeat(64),
  data_asof: '2026-11-21T09:00:00Z', origin_deadline: '2026-11-21T11:00:00Z',
  gws: [11, 12], players: [{
    id: 20, price_tenths: 51, team_id: 2, position: 2,
    weeks: [
      { gw: 11, xpts: 9, xmins: 157, fixtures: [{ id: 1 }, { id: 2 }] },
      { gw: 12, xpts: 0, xmins: 0, fixtures: [] },
    ],
  }],
};
const official = {
  season: forecast.season, next_gw: 11, players: [{ id: 20, team: 2, position: 2, price: 5.1 }],
  live_window: { gw: 11, deadline: forecast.origin_deadline, observed_at: forecast.data_asof, catalogue_matches: true },
};
const FplForecastWindow = { check: () => ({ usable: true }) };
runInNewContext(readFileSync(require.resolve('./forecast-gate'), 'utf8'), {
  FplForecastWindow, FplModelContractV1,
});

test('accepts a matching verified live window with a double and blank GW', () => {
  assert.equal(FplForecastWindow.check(forecast, official, now).usable, true);
});

test('historical and changed deadlines or official rounds cannot activate a forecast', () => {
  for (const live_window of [
    null,
    { ...official.live_window, catalogue_matches: false },
    { ...official.live_window, gw: 12 },
    { ...official.live_window, deadline: '2026-11-21T12:00:00Z' },
    { ...official.live_window, observed_at: '2026-11-20T00:00:00Z' },
  ]) assert.equal(FplForecastWindow.check(forecast, { ...official, live_window }, now).usable, false);
  assert.equal(FplForecastWindow.check(forecast, official, Date.parse(forecast.origin_deadline)).usable, false);
  assert.equal(FplForecastWindow.check(forecast, official, Date.parse(forecast.data_asof) - 1).usable, false);
});
