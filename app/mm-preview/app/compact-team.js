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
      const playerCard = (id, starter = true) => {
        const player = players.get(id);
        const known = official.get(id);
        const flag = availability.get(id);
        const label = labels[flag?.status] || (flag?.recent_red_cards?.length ? 'Kort' : '');
        const role = lineup?.captain === id ? 'C' : lineup?.vice === id ? 'V' : '';
        const name = escape(player?.name || known?.web_name || 'Spiller ' + id);
        const shortName = escape((known?.web_name || player?.name || 'Spiller').slice(0, 16));
        const club = escape((context?.official?.teams || []).find(team => team.id === known?.team)?.short_name || player?.team || 'FPL');
        const description = flag?.news ? escape(flag.news) : 'Se spillerstatus hos FPL.';
        return '<div class="fpl-pitch-player' + (!starter ? ' is-bench' : '') + '">' +
          '<a class="fpl-pitch-player-link" href="player.html?id=' + Number(id) + '" aria-label="' + name + ', ' + number(week(id)?.xpts) + ' forventede point">' +
          '<span class="fpl-pitch-shirt" aria-hidden="true"><span>' + club + '</span></span>' +
          (role ? '<span class="fpl-pitch-role" title="' + (role === 'C' ? 'Kaptajn' : 'Vicekaptajn') + '">' + role + '</span>' : '') +
          '<span class="fpl-pitch-name">' + shortName + '</span>' +
          '<span class="fpl-pitch-points">' + number(week(id)?.xpts) + ' xP <span>· ' + number(week(id)?.xmins) + ' min</span></span></a>' +
          (label ? '<details class="fpl-pitch-alert"><summary>' + escape(label) + '</summary><p>' + description + '</p></details>' : '') + '</div>';
      };
      if (lineup) {
        const groups = [1, 2, 3, 4].map(pos => starters.filter(id =>
          (official.get(id)?.element_type || players.get(id)?.position) === pos));
        html += '<div class="fpl-team-pitch" role="group" aria-label="Startopstilling på fodboldbane">' +
          '<div class="fpl-pitch-markings" aria-hidden="true"></div>' +
          groups.map((group, index) => '<div class="fpl-team-pitch-row fpl-team-position-' + (index + 1) + '">' +
            group.map(id => playerCard(id)).join('') + '</div>').join('') + '</div>' +
          '<div class="fpl-pitch-bench-heading">Bænk</div><div class="fpl-pitch-bench">' +
          lineup.ids.slice(11).map(id => playerCard(id, false)).join('') + '</div>' +
          '<p class="compact-team-note fpl-team-footnote">xP og forventede minutter fra vores model. Opstillingen er din gemte plan, ikke et automatisk gennemført FPL-skifte.</p>';
      } else {
        html += '<p class="compact-team-note">Bekræft din opstilling og kaptajn for at se dine 11 startere på banen.</p>' +
          '<div class="fpl-unconfirmed-squad">' + ids.map(id => playerCard(id, false)).join('') + '</div>';
      }
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
