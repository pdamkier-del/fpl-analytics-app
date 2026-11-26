'use strict';
// Read-only official FPL manager-ID -> verified private TS state.
// Never infer prices/FT or activate the optimiser on incomplete public data.
(function(root) {
  const DEFAULT_ENTRY_ID = 7647524;
  const KEY = 'fpl-transfer-manager-id-sync-v1';
  const status = document.getElementById('transfer-manager-sync');
  const retry = document.getElementById('transfer-manager-sync-retry');
  const setStatus = (message, state = 'working') => {
    if (!status) return;
    status.hidden = false;
    status.dataset.state = state;
    status.textContent = message;
  };
  const validId = value => /^[1-9][0-9]{0,8}$/.test(String(value || ''));
  let busy = false;
  async function sync(force = false) {
    if (busy) return;
    const entryId = Number(localStorage.getItem('fpl-history-entry-id') ||
      localStorage.getItem('fpl-transfer-entry-id') || DEFAULT_ENTRY_ID);
    if (!validId(entryId)) { setStatus('FPL-manager-ID mangler eller er ugyldigt.', 'error'); return; }
    if (!root.FplManagerClient || !root.FplOfficialManagerImport || !root.FplHistoryRefreshClient) {
      setStatus('Den officielle holdimport kan ikke indlæses.', 'error'); return;
    }
    busy = true;
    if (retry) retry.hidden = true;
    try {
      await root.FplManagerClient.load();
      const snapshot = root.FplManagerClient.snapshot();
      const forecast = snapshot.forecast;
      if (!forecast || !Array.isArray(forecast.gws) || !forecast.gws.length)
        throw Error('Aktuelt forecast er ikke indlæst.');
      const oldState = root.FplManagerStore.read();
      const marker = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      // Reuse a completed verified ID import for this target GW. The normal
      // model freshness guards continue to block stale model predictions.
      if (!force && marker?.entryId === entryId && marker?.gw === forecast.gws[0] &&
          marker?.season === forecast.season && oldState?.gw === forecast.gws[0] &&
          oldState?.season === forecast.season && marker?.stateStamp === oldState.observed_at) {
        setStatus('Hold fra FPL-ID ' + entryId + ' er indlæst til GW ' + oldState.gw +
          '. Transfers bruger disse 15 spillere og de verificerede købsoplysninger.', 'ready');
        return;
      }
      setStatus('Henter officielt hold og transferhistorik for FPL-ID ' + entryId + ' …');
      const history = await root.FplHistoryRefreshClient.run({
        entryId, season: forecast.season,
        onProgress: progress => {
          if (progress.stage === 'capacity') setStatus('FPL-importen venter på den private datatjeneste …');
          else if (progress.stage === 'history') setStatus('Henter de offentliggjorte GW-hold og transfers …');
          else if (progress.stage === 'model') setStatus('Afstemmer den officielle historik …');
        }
      });
      const importer = root.FplOfficialManagerImport;
      const draft = importer.fromOfficialHistory(history, entryId, forecast);
      const initialPrices = await importer.loadInitialPrices();
      const state = importer.reconcileOfficialHistory(draft, history, forecast, initialPrices);
      const problems = root.FplPlannerExperience.diagnose(state, forecast);
      if (problems.length) throw Error('Officielle holdoplysninger kunne ikke valideres: ' + problems.join(' '));
      // No manual confirmation is needed: all source features have been
      // reconciled against official transfer history and historical prices.
      root.FplManagerStore.save(state);
      localStorage.setItem('fpl-history-entry-id', String(entryId));
      localStorage.setItem('fpl-transfer-entry-id', String(entryId));
      sessionStorage.setItem(KEY, JSON.stringify({
        entryId, gw: state.gw, season: state.season, stateStamp: state.observed_at
      }));
      root.FplHistoryRefreshClient.acknowledge();
      setStatus('FPL-ID ' + entryId + ': alle 15 spillere, købspriser, bank, gratis transfers og chips er indlæst automatisk. Opdaterer Transfers …','ready');
      // Refresh the adapter's cached private manager state and make the
      // existing TS UI re-render; no official FPL actions are taken.
      location.reload();
    } catch (error) {
      setStatus('Officiel holdimport for ID ' + entryId + ' kunne ikke fuldføres: ' +
        error.message + '. Ingen spillerpriser eller gratis transfers er blevet gættet.', 'error');
      if (retry) retry.hidden = false;
    } finally { busy = false; }
  }
  if (retry) retry.addEventListener('click', () => sync(true));
  window.addEventListener('DOMContentLoaded', () => sync(false));
})(window);
