'use strict';

const byId = id => document.getElementById(id);
const number = new Intl.NumberFormat('da-DK', { maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat('da-DK', { style: 'percent', maximumFractionDigits: 1 });
const format = (value, formatter) => Number.isFinite(value) ? formatter.format(value) : '—';

function render(forecast) {
  const gw = Number(byId('round').value);
  const query = byId('search').value.trim().toLocaleLowerCase('da-DK');
  const players = forecast.players
    .filter(player => (player.name + ' ' + player.team).toLocaleLowerCase('da-DK').includes(query))
    .map(player => ({ player, week: player.weeks.find(item => item.gw === gw) }))
    .filter(({ week }) => week)
    .sort((a, b) => b.week.xpts - a.week.xpts || a.player.name.localeCompare(b.player.name));
  const rows = document.createDocumentFragment();
  for (const { player, week } of players) {
    const row = document.createElement('tr');
    for (const value of [player.name, player.team, format(week.xpts, number),
      format(week.xmins, number), format(week.p_play, percent)]) {
      row.insertCell().textContent = value;
    }
    const fixtures = row.insertCell();
    if (!week.fixtures.length) fixtures.textContent = 'Ingen kamp';
    for (const fixture of week.fixtures) {
      const stats = document.createElement('span');
      const law = fixture.distribution;
      stats.textContent = law
        ? 'Start: ' + format(law.p_start, percent) + ' · 60+ min.: ' + format(law.p_60_plus, percent) +
          ' · 80 % pointinterval: ' + law.points_interval80.map(value => format(value, number)).join('–')
        : 'Fordeling ikke tilgængelig';
      fixtures.append(stats);
    }
    rows.append(row);
  }
  byId('rows').replaceChildren(rows);
}

async function load() {
  const [source, data] = await Promise.all(['./receipt.json', './forecast.json'].map(path => fetch(path)));
  if (!source.ok || !data.ok) throw new Error('Arkivet kunne ikke hentes.');
  const receipt = await source.json();
  const bytes = await data.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    byte => byte.toString(16).padStart(2, '0')).join('');
  const forecast = JSON.parse(new TextDecoder().decode(bytes));
  if (digest !== receipt.forecast_file_sha256 || forecast.forecast_sha256 !== receipt.forecast_sha256 ||
      forecast.model !== 'B-MM-PM-TS-v1') throw new Error('Prognosens identitet kunne ikke verificeres.');
  const issued = new Intl.DateTimeFormat('da-DK', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Copenhagen',
  }).format(new Date(forecast.data_asof));
  byId('status').textContent = 'GW ' + forecast.gws.join(', ') + ' · udstedt ' + issued + ' dansk tid.';
  for (const gw of forecast.gws) byId('round').add(new Option('GW ' + gw, gw));
  byId('round').addEventListener('change', () => render(forecast));
  byId('search').addEventListener('input', () => render(forecast));
  render(forecast);
  byId('projections').hidden = false;
  byId('original').hidden = false;
}

load().catch(error => { byId('status').textContent = error.message; });
