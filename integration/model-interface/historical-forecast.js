'use strict';

document.addEventListener('DOMContentLoaded', async () => {
  const app = window.FplBExistingApp;
  if (!app || !window.FplForecastWindow || !document.querySelector('main')) return;
  try {
    const responses = await Promise.all(['current-players.json', 'vfinal-diagnostic.json']
      .map(path => fetch(path, { cache: 'no-store' })));
    if (responses.some(response => !response.ok)) return;
    const [official, forecast] = await Promise.all(responses.map(response => response.json()));
    const status = FplForecastWindow.check(forecast, official);
    if (status.usable || !FplModelContractV1.validateOfficialCompatibility(forecast, official).ok) return;

    const panel = document.createElement('aside');
    panel.className = 'panel';
    const heading = document.createElement('h2');
    heading.textContent = 'Historisk prognose · GW ' + forecast.gws[0];
    const reason = document.createElement('p');
    const cutoff = new Intl.DateTimeFormat('da-DK', {
      dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Copenhagen',
    }).format(new Date(forecast.data_asof));
    reason.textContent = status.reason + ' Datacutoff ' + cutoff + '.';
    panel.append(heading, reason);
    const state = FplManagerStore.read();
    if (state?.season === forecast.season && Array.isArray(state.squad)) {
      const owned = new Set(state.squad.map(player => player.id));
      const list = document.createElement('ul');
      for (const player of forecast.players.filter(player => owned.has(player.id))) {
        const entry = document.createElement('li');
        const week = player.weeks[0];
        entry.textContent = player.name + ' · ' + week.xpts.toFixed(1) + ' xP · ' + week.xmins.toFixed(0) + ' min.';
        list.append(entry);
      }
      if (list.children.length) panel.append(list);
    }
    const banner = document.getElementById('preview-data-info');
    if (banner) banner.after(panel);
    else document.body.prepend(panel);
  } catch {
    // The established app displays its connection or validation error.
  }
}, { once: true });
