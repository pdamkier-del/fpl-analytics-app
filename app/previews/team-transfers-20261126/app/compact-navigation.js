'use strict';

// Unified navigation for the existing FPL Analytics app.
// Navigation only: preserve forecast, manager state, lineup and player detail behaviour.
(() => {
  const nav = document.querySelector('.fpl-primary-navigation');
  if (!nav) return;
  const filename = location.pathname.split('/').pop() || 'overview.html';
  const isTransfer = ['transfers-classic.html','transfer-planner.html','team-optimizer.html'].includes(filename);
  const isCatalogue = ['players-classic.html','clubs-classic.html','player.html','current-players.html'].includes(filename);
  const isAdvanced = filename === 'advanced.html';
  const section = isTransfer ? 'transfers' : isCatalogue ? 'catalogue' : isAdvanced ? 'advanced' : 'team';
  const items = [
    ['overview.html','Mit hold','team'],
    ['transfers-classic.html','Transfers','transfers'],
    ['players-classic.html','Spillere / klubber','catalogue'],
  ];
  nav.replaceChildren();
  nav.classList.add('fpl-unified-navigation');
  for (const [href,label,key] of items) {
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.textContent = label;
    if (section === key) anchor.setAttribute('aria-current','page');
    nav.append(anchor);
  }
  const advanced = document.createElement('a');
  advanced.href = 'advanced.html';
  advanced.textContent = 'Avanceret';
  advanced.className = 'fpl-advanced-link';
  if (isAdvanced) advanced.setAttribute('aria-current','page');
  nav.append(advanced);

  if (isCatalogue) {
    const sub = document.createElement('nav');
    sub.className = 'fpl-catalog-navigation';
    sub.setAttribute('aria-label','Spillere og klubber');
    const links = [
      ['players-classic.html','Spillere',filename === 'players-classic.html' || filename === 'player.html' || filename === 'current-players.html'],
      ['clubs-classic.html','Klubber',filename === 'clubs-classic.html'],
    ];
    for (const [href,label,active] of links) {
      const a = document.createElement('a');
      a.href = href;
      a.textContent = label;
      if (active) a.setAttribute('aria-current','page');
      sub.append(a);
    }
    nav.insertAdjacentElement('afterend',sub);
  }

  // Legacy dashboard adds a second set of links dynamically. Keep the
  // computation in the DOM but do not show its duplicated technical links.
  const main = document.getElementById('weekly-main');
  if (!main) return;
  const technical = 'a[href="forecast-history.html"],a[href="overview.html#model"],a[href="#model"],a[href="model-status.html"],a[href="models.html"]';
  const hideTechnicalLinks = () => {
    if (location.hash && location.hash !== '#dashboard') return;
    for (const link of main.querySelectorAll(technical)) link.dataset.fplHideTechnical = '';
  };
  hideTechnicalLinks();
  new MutationObserver(hideTechnicalLinks).observe(main,{childList:true,subtree:true});
})();
