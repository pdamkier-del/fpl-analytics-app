'use strict';

const historyBackend = 'https://fpl-analytics-private-manager.onrender.com';
const chipNames = { wildcard: 'wildcard', freehit: 'free_hit', bboost: 'bench_boost', '3xc': 'triple_captain' };

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

if (typeof module !== 'undefined') module.exports = { fromOfficialHistory };

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
