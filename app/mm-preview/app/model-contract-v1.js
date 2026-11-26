'use strict';

/**
 * FPL Analytics external-model boundary, v1.
 * This is a standalone, side-effect-free compatibility gate. It does not
 * activate a model, fetch data, alter localStorage, or select a TS engine.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root && typeof window !== 'undefined') root.FplModelContractV1 = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const isObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const timestamp = x => typeof x === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x));
  const sha = x => typeof x === 'string' && /^[0-9a-f]{64}$/i.test(x);
  const ids = a => Array.isArray(a) && a.every(Number.isInteger) && new Set(a).size === a.length;
  const fail = (code, message) => ({ ok: false, code, message });

  function validateForecast(f) {
    if (!isObject(f)) return fail('missing_forecast', 'Forecast is missing.');
    if (!Array.isArray(f.gws) || !f.gws.length || f.gws.length > 6 ||
        !ids(f.gws) || !f.gws.every((g, i) => g >= 1 && g <= 38 &&
          (!i || g === f.gws[i - 1] + 1)))
      return fail('invalid_horizon', 'Forecast GW sequence must be consecutive and contain 1–6 rounds.');
    if (!timestamp(f.data_asof) || !timestamp(f.origin_deadline) ||
        Date.parse(f.data_asof) >= Date.parse(f.origin_deadline))
      return fail('invalid_cutoff', 'Forecast cutoff must precede the original deadline.');
    if (!sha(f.forecast_sha256)) return fail('invalid_identity', 'Forecast requires a SHA-256 identity.');
    if (typeof f.season !== 'string' || !f.season ||
        typeof f.model !== 'string' || !f.model)
      return fail('invalid_model_metadata', 'Forecast season and model identity are required.');
    if (!Array.isArray(f.players) || !f.players.length)
      return fail('missing_players', 'Forecast player catalogue is missing.');
    const seen = new Set();
    for (const p of f.players) {
      if (!isObject(p) || !Number.isInteger(p.id) || seen.has(p.id) ||
          !Number.isInteger(p.team_id) || ![1, 2, 3, 4].includes(p.position) ||
          !Number.isInteger(p.price_tenths) || p.price_tenths <= 0)
        return fail('invalid_player', 'Player identities, teams, positions and prices must be valid and unique.');
      seen.add(p.id);
      if (!Array.isArray(p.weeks) || p.weeks.length !== f.gws.length ||
          p.weeks.some((w, i) => !isObject(w) || w.gw !== f.gws[i] ||
            !finite(w.xpts) || w.xpts < -10 || w.xpts > 100 ||
            !finite(w.xmins) || w.xmins < 0 || w.xmins > 180))
        return fail('invalid_player_weeks', 'Each player must contain xP and xM for every forecast GW.');
    }
    return { ok: true, code: 'compatible_forecast_v1', model: f.model,
      forecast_sha256: f.forecast_sha256, origin_gw: f.gws[0], horizon: f.gws.length };
  }

  function validateOfficialCompatibility(f, official) {
    const valid = validateForecast(f);
    if (!valid.ok) return valid;
    if (!isObject(official) || official.next_gw !== f.gws[0] ||
        !Array.isArray(official.players))
      return fail('official_mismatch', 'Official catalogue or next GW does not match.');
    const catalogue = new Map(official.players.map(p => [p.id, p]));
    if (catalogue.size !== official.players.length ||
        catalogue.size !== f.players.length)
      return fail('player_catalogue_mismatch', 'Forecast and official player sets differ.');
    for (const p of f.players) {
      const q = catalogue.get(p.id);
      if (!q || q.team !== p.team_id || q.position !== p.position ||
          !finite(q.price) || Math.abs(10 * q.price - p.price_tenths) > 1e-6)
        return fail('player_catalogue_mismatch', 'Team, price or position differs from official catalogue.');
    }
    return valid;
  }

  function validatePlanIdentity(f, stateHash, plan) {
    const valid = validateForecast(f);
    if (!valid.ok) return valid;
    if (!isObject(plan) || !sha(stateHash) || plan.forecast_sha256 !== f.forecast_sha256 ||
        plan.forecast_cutoff !== f.data_asof || plan.manager_state_sha256 !== stateHash ||
        plan.gw !== f.gws[0])
      return fail('stale_or_wrong_team', 'Plan must match forecast, cutoff, GW and exact manager-state hash.');
    if (!plan.ts_ran || plan.validation_only ||
        !Array.isArray(plan.plan?.path) || plan.plan.path.length !== f.gws.length ||
        plan.plan.path.some((entry, i) => entry.gw !== f.gws[i]))
      return fail('invalid_plan', 'TS result must contain an evaluated plan for the full horizon.');
    return { ok: true, code: 'compatible_plan_v1', forecast_sha256: f.forecast_sha256 };
  }

  return Object.freeze({ validateForecast, validateOfficialCompatibility, validatePlanIdentity });
});
