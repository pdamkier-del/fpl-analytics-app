// A saved team newer than the forecast must resume once, without another save.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

(async () => {
  const source = fs.readFileSync(process.env.MANAGER_SOURCE || 'app/classic-manager.js', 'utf8');
  const isPreview = source.includes('fpl-B-wait-for-forecast');
  const waitKey = isPreview ? 'fpl-B-wait-for-forecast' : 'fpl-wait-for-forecast';
  const players = Array.from({length: 15}, (_, i) => ({
    id: i + 1, position: i < 2 ? 1 : i < 7 ? 2 : i < 12 ? 3 : 4,
    team_id: Math.floor(i / 3) + 1,
  }));
  const state = {
    season: '2026-27', gw: 8, source: 'SYNTHETIC_RESUME_REGRESSION',
    observed_at: '2026-10-20T11:00:00Z', bank_tenths: 7, free_transfers: 2,
    squad: players.map(p => ({id: p.id, purchase_price_tenths: 50})),
    chips_used: {wildcard: [], free_hit: [], bench_boost: [], triple_captain: []},
  };
  let forecast = {
    model: isPreview ? 'B-MM-PM-TS-v1' : 'original_locked_vFinal_diagnostic', locked_model_active: false,
    season: state.season, gws: [8, 9, 10, 11, 12, 13], players,
    forecast_sha256: 'a'.repeat(64), data_asof: '2026-10-20T10:00:00Z',
  };
  const local = new Map([['fpl-manager-state-v1', JSON.stringify(state)]]);
  const session = new Map();
  const storage = map => ({getItem: k => map.get(k) ?? null,
    setItem: (k, v) => map.set(k, String(v)), removeItem: k => map.delete(k)});
  let posts = 0, receipt;
  const response = value => ({ok: true, json: async () => structuredClone(value)});
  const context = {
    crypto: webcrypto, TextEncoder, AbortController, Event, btoa,
    localStorage: storage(local), sessionStorage: storage(session),
    document: {getElementById: () => null, querySelectorAll: () => []},
    FplForecastWindow: {check: () => ({usable: true})},
    FplPlannerExperience: {diagnose: () => [], mount: () => {}},
    FplTeamNews: {load: async () => ({}), evaluate: () => ({aligned: true})},
    FplBExistingApp: {forecast: async () => forecast},
    FplPreviewCapacity: {submit: ({url, body, request}) => request(url, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
    })},
    setTimeout: (fn, ms) => {if (ms === 0 || ms === 10000) queueMicrotask(fn); return 1;},
    clearTimeout: () => {}, addEventListener: () => {}, dispatchEvent: () => {},
    fetch: async (url, options) => {
      if (url === 'vfinal-diagnostic.json') return response(forecast);
      if (url === 'current-players.json') return response({next_gw: 8});
      if (url === 'manager-service.json') return response({url: 'https://test.invalid'});
      if (url.endsWith('/health')) return response({runtime: 'original_locked_python',
        locked_model_active: false, supports_idempotent_submit: true,
        supports_mm_preview: true, supports_unified_B_chain: true});
      if (options?.method === 'POST') {
        posts++;
        receipt = JSON.parse(options.body);
        return response({id: receipt.request_id, key: receipt.request_key});
      }
      assert(url.includes('/plans/'));
      return response({status: 'completed', plan: {
        locked_model_active: false, ts_ran: true, gw: state.gw,
        forecast_sha256: forecast.forecast_sha256, forecast_cutoff: forecast.data_asof,
        manager_state_sha256: await context.FplManagerClient.hash(state),
        lineup: players, plan: {path: forecast.gws.map(gw => ({gw,
          official_hit_points: 0, projected_manager_score: 50, incoming: [], outgoing: []}))},
      }});
    },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context);
  const client = context.FplManagerClient;
  await client.load();
  client.bind(() => {});
  await client.compute();
  assert.equal(posts, 0);
  assert.equal(session.get(waitKey), '1');
  await client.load();
  assert.equal(posts, 0, 'Unchanged old forecast must not submit a job');
  forecast = {...forecast, data_asof: '2026-10-20T12:00:00Z', forecast_sha256: 'b'.repeat(64)};
  await client.load();
  for (let i = 0; i < 100 && !client.snapshot().plan; i++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  assert(client.snapshot().plan, 'Fresh forecast must resume and display the completed plan');
  assert.equal(posts, 1);
  assert.equal(session.has(waitKey), false);
  await client.load();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(posts, 1, 'Loading a completed plan must not start a duplicate');
  assert.equal(local.get('fpl-manager-state-v1'), JSON.stringify(state));
  console.log('PASS: waiting team automatically resumes once with fresh data; actual squad and prices stay unchanged.');
})().catch(error => {console.error(error); process.exitCode = 1;});
