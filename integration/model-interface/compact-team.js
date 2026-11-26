'use strict';

(() => {
  const root = document.getElementById('compact-team');
  const legacy = document.getElementById('weekly-main');
  if (!root || !legacy) return;

  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const format = new Intl.NumberFormat('da-DK', { maximumFractionDigits: 1 });
  const number = value => Number.isFinite(value) ? format.format(value) : '–';
  const labels = { d: 'Tvivlsom', i: 'Skadet', s: 'Karantæne', u: 'Ude', n: 'Ude' };
  let news;
  let rendered = '';

  function render() {
    const dashboard = !location.hash || location.hash === '#dashboard';
    document.body.classList.toggle('fpl-team-dashboard', dashboard);
    root.hidden = !dashboard;
    if (!dashboard) return;
    const context = window.FplDashboardContext?.();
    const state = context?.state || window.FplManagerStore?.read();
    const forecast = context?.forecast;
    const gw = forecast?.gws?.[0];
    const heading = '<header class="compact-team-heading"><h1>Mit hold</h1>' +
      '<a href="manager-state.html">Importér eller redigér hold</a></header>';
    let html = heading;
    if (!state?.squad?.length) {
      html += '<p>Importér dit FPL-hold for at se truppen her.</p>';
    } else {
      const players = new Map((forecast?.players || []).map(player => [player.id, player]));
      const official = new Map((context?.official?.players || []).map(player => [player.id, player]));
      const availability = new Map(news && news.next_gw === gw ? news.players.map(player => [player.id, player]) : []);
      const ids = state.squad.map(player => player.id);
      const selection = context?.selection;
      const lineup = selection?.ids?.length === 15 && new Set(selection.ids).size === 15 &&
        selection.ids.every(id => ids.includes(id)) ? selection : null;
      const projections = context?.usable && state.gw === gw;
      const week = id => projections ? players.get(id)?.weeks?.find(row => row.gw === gw) : undefined;
      const starters = lineup?.ids.slice(0, 11) || [];
      const values = [...starters, lineup?.captain].map(id => week(id)?.xpts);
      const points = starters.includes(lineup?.captain) && values.every(Number.isFinite)
        ? values.reduce((total, value) => total + value, 0) : undefined;
      html += '<p class="compact-team-summary">' +
        '<span>Bank <strong>' + number(Number.isInteger(state.bank_tenths) ? state.bank_tenths / 10 : NaN) + '</strong></span>' +
        '<span>Gratis transfers <strong>' + number(state.free_transfers) + '</strong></span>' +
        '<span>Forventede point <strong>' + number(points) + '</strong></span></p>';
      if (!lineup) html += '<p class="compact-team-note">Opstilling og kaptajn er ikke gemt for denne trup.</p>';
      const table = (title, rows) => '<table class="compact-team-table"><caption>' + title +
        '</caption><thead><tr><th scope="col">Spiller</th><th scope="col">xP</th><th scope="col">xM</th></tr></thead><tbody>' +
        rows.map(id => {
          const player = players.get(id);
          const flag = availability.get(id);
          const label = labels[flag?.status] || (flag?.recent_red_cards?.length ? 'Kort' : '');
          const role = lineup?.captain === id ? 'K' : lineup?.vice === id ? 'VK' : '';
          return '<tr data-player-id="' + Number(id) + '"><th scope="row"><a href="player.html?id=' + Number(id) + '">' +
            escape(player?.name || official.get(id)?.web_name || 'Spiller ' + id) + '</a>' +
            (role ? ' <abbr title="' + (role === 'K' ? 'Kaptajn' : 'Vicekaptajn') + '">' + role + '</abbr>' : '') +
            (label ? '<details class="compact-player-alert"><summary>' + label + '</summary><p>' +
              escape(flag.news || 'Se spillerstatus hos FPL.') + '</p></details>' : '') +
            '</th><td>' + number(week(id)?.xpts) + '</td><td>' + number(week(id)?.xmins) + '</td></tr>';
        }).join('') + '</tbody></table>';
      html += lineup ? table('Startopstilling', starters) + table('Bænk', lineup.ids.slice(11)) : table('Trup', ids);
    }
    if (html !== rendered) {
      const openAlerts = new Set([...root.querySelectorAll('details[open]')].map(item => item.closest('th').querySelector('a').href));
      root.innerHTML = html;
      for (const item of root.querySelectorAll('details')) {
        item.open = openAlerts.has(item.closest('th').querySelector('a').href);
      }
      rendered = html;
    }
  }

  const observer = new MutationObserver(render);
  observer.observe(legacy, { childList: true, subtree: true });
  window.addEventListener('hashchange', render);
  window.addEventListener('storage', render);
  render();
  window.FplTeamNews?.load().then(value => { news = value; render(); }).catch(() => {});
})();
