'use strict';

const historyBackend = 'https://fpl-analytics-private-manager.onrender.com';
const chipNames = { wildcard: 'wildcard', freehit: 'free_hit', bboost: 'bench_boost', '3xc': 'triple_captain' };

const initialPriceArchive = 'https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/ff42171dd14ff184eb667c2c28d9a8f59ec9722f/analysis/results/history-refresh-public-20261029/initial-bootstrap.json.gz';
const initialPriceChecksum = '170e619d86117da4f70f12f682f371cf31684f3c964e974a43f795e210c9baba';

async function loadInitialPrices() {
  const response = await fetch(initialPriceArchive, { credentials: 'omit', cache: 'no-store' });
  if (!response.ok) throw new Error('Sæsonens startpriser kunne ikke hentes.');
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    byte => byte.toString(16).padStart(2, '0')).join('');
  if (digest !== initialPriceChecksum) throw new Error('Sæsonens startpriser kunne ikke verificeres.');
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  return (await new Response(stream).json()).elements;
}

function reconcileOfficialHistory(draft, history, forecast, initialPrices) {
  const reject = () => { throw new Error('FPL-historikken kan ikke afstemmes automatisk.'); };
  // Only this season has the pinned launch catalogue. The standard FT rule
  // applies to GW2–12; later rounds may have an exceptional allocation.
  if (forecast.season !== '2026-27' || draft.gw > 12 || !Array.isArray(history.transfers)) reject();
  const weeks = new Map(history.weeks.map(week => [week.gw, week]));
  const moves = history.transfers;
  if (weeks.size !== draft.source_gw || !weeks.has(1) ||
      moves.some(move => !Number.isInteger(move.event) || move.event < 2 || move.event > draft.source_gw)) reject();
  const prices = new Map(initialPrices.map(player => [player.id, player.now_cost]));
  const owned = new Map(weeks.get(1).picks.map(pick => [pick.element, prices.get(pick.element)]));
  const validPrice = price => Number.isInteger(price) && price > 0 && price <= 1000;
  if (owned.size !== 15 || [...owned.values()].some(price => !validPrice(price))) reject();
  let bank = 1000 - [...owned.values()].reduce((sum, price) => sum + price, 0);
  let freeTransfers = 1;
  for (let gw = 1; gw <= draft.source_gw; gw++) {
    const week = weeks.get(gw);
    if (!week || ['wildcard', 'freehit'].includes(week.active_chip)) reject();
    const roundMoves = moves.filter(move => move.event === gw);
    for (const move of roundMoves) {
      if (!owned.delete(move.element_out) || !validPrice(move.element_out_cost)) reject();
      bank += move.element_out_cost;
    }
    for (const move of roundMoves) {
      if (owned.has(move.element_in) || !validPrice(move.element_in_cost)) reject();
      owned.set(move.element_in, move.element_in_cost);
      bank -= move.element_in_cost;
    }
    const official = week.entry_history;
    const picks = new Set(week.picks.map(pick => pick.element));
    if (bank < 0 || bank !== official?.bank || roundMoves.length !== official.event_transfers ||
        4 * Math.max(0, roundMoves.length - freeTransfers) !== official.event_transfers_cost ||
        picks.size !== 15 || owned.size !== 15 || [...owned.keys()].some(id => !picks.has(id))) reject();
    if (gw > 1) freeTransfers = Math.min(5, Math.max(0, freeTransfers - roundMoves.length) + 1);
  }
  const observedAt = history.observed_at;
  if (!Number.isFinite(Date.parse(observedAt)) || Date.parse(observedAt) > Date.now()) reject();
  return {
    season: forecast.season, gw: draft.gw,
    source: 'Officiel FPL-historik · senest offentliggjorte hold uden senere ændringer',
    observed_at: observedAt, bank_tenths: bank, free_transfers: freeTransfers,
    squad: draft.squad.map(player => ({ ...player, purchase_price_tenths: owned.get(player.id) })),
    chips_used: draft.chips_used,
  };
}

function fromOfficialHistory(history, entryId, forecast) {
  const target = forecast.gws[0];
  if (history?.schema !== 'fpl-official-entry-history-v1' || history.entry_id !== entryId ||
      history.season !== forecast.season || history.availability?.next_gw !== target ||
      !Array.isArray(history.weeks) || !Array.isArray(history.chips)) {
    throw new Error('Den officielle historik matcher ikke hold, sæson eller gameweek.');
  }
  const latest = history.weeks.reduce((best, week) => best?.gw > week.gw ? best : week, null);
  if (latest?.gw !== target - 1 || latest.active_chip === 'freehit') {
    throw new Error('Seneste offentlige hold kan ikke bruges som permanent kladde. Kontrollér truppen i FPL.');
  }
  const picks = [...(latest.nominated_picks || latest.picks || [])].sort((a, b) => a.position - b.position);
  const ids = picks.map(pick => pick.element);
  if (picks.length !== 15 || new Set(ids).size !== 15 ||
      !picks.every((pick, index) => pick.position === index + 1 && Number.isInteger(pick.element) && pick.element > 0)) {
    throw new Error('Den officielle holdopstilling indeholder ikke 15 entydige spillere.');
  }
  const chips = Object.fromEntries(Object.values(chipNames).map(name => [name, []]));
  for (const chip of history.chips) {
    const name = Object.hasOwn(chipNames, chip.name) ? chipNames[chip.name] : null;
    if (name && Number.isInteger(chip.event) && chip.event > 0 && chip.event < target) chips[name].push(chip.event);
  }
  return {
    draft_only: true, source_gw: latest.gw, gw: target,
    source: 'Officiel GW' + latest.gw + '-trup bekræftet i FPL',
    squad: ids.map(id => ({ id })), chips_used: chips,
  };
}

if (typeof module !== 'undefined') module.exports = { fromOfficialHistory, reconcileOfficialHistory };

if (typeof window !== 'undefined') window.addEventListener('DOMContentLoaded', async () => {
  const button = document.getElementById('import-manager');
  if (!button) return;
  const legacy = document.getElementById('onlineStatus');
  if (legacy) legacy.textContent = 'Denne preview beregner kun via Transfers og sender ikke holdet til GitHub Actions.';
  let config;
  try {
    const response = await fetch('manager-service.json', { cache: 'no-store' });
    if (!response.ok) return;
    config = await response.json();
  } catch {
    return;
  }
  const localImport = config.url === '/preview-api' && config.supports_public_squad_import === true;
  const historyImport = config.url === historyBackend && window.FplHistoryRefreshClient;
  if (!localImport && !historyImport) return;
  button.closest('section').hidden = false;
  if (historyImport) button.textContent = 'Brug senest offentliggjorte hold';
  const message = document.getElementById('manager-import-status');
  const entry = document.getElementById('manager-import-entry');
  button.addEventListener('click', async () => {
    if (!window.FplManagerOnline?.canImport()) {
      message.textContent = 'Afventer det verificerede spillerkatalog.';
      return;
    }
    if (!/^[1-9][0-9]{0,8}$/.test(entry.value.trim())) {
      message.textContent = 'Angiv et gyldigt FPL-manager-ID.';
      return;
    }
    button.disabled = true;
    message.textContent = 'Henter den seneste offentlige holdopstilling …';
    try {
      const entryId = Number(entry.value.trim());
      let data;
      if (localImport) {
        const response = await fetch('/preview-api/squad/' + entryId, { cache: 'no-store' });
        data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Holdet kunne ikke hentes.');
      } else {
        const forecast = window.FplManagerOnline.getForecast();
        const history = await historyImport.run({
          entryId, season: forecast.season,
          onProgress: progress => {
            if (progress.stage === 'capacity') message.textContent = 'Venter på den private tjeneste …';
            if (progress.stage === 'model') message.textContent = 'Den private tjeneste kontrollerer holdhistorikken …';
          },
        });
        data = fromOfficialHistory(history, entryId, forecast);
        historyImport.acknowledge();
        try {
          const reconciled = reconcileOfficialHistory(data, history, forecast, await loadInitialPrices());
          window.FplManagerOnline.saveOfficialState(reconciled);
          message.textContent = 'Hold, køb, bank, gratis transfers og chips er afstemt. Åbn Transfers for at beregne.';
          return;
        } catch {
          // Leave unverified finances blank and preserve any previously saved team.
        }
      }
      window.FplManagerOnline.importDraft(data);
      message.textContent = 'Kladde fra GW ' + data.source_gw + '. Kontrollér ændringer i FPL, og udfyld aktuelle købspriser, bank og gratis transfers før bekræftelse.';
    } catch (error) {
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
});
