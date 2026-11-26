'use strict';

(() => {
  const main = document.getElementById('weekly-main');
  if (!main) return;
  const links = 'a[href="forecast-history.html"],a[href="overview.html#model"],a[href="#model"],a[href="model-status.html"],a[href="models.html"]';
  function hideTechnicalLinks() {
    if (location.hash && location.hash !== '#dashboard') return;
    for (const link of main.querySelectorAll(links)) link.dataset.fplHideTechnical = '';
  }
  hideTechnicalLinks();
  new MutationObserver(hideTechnicalLinks).observe(main, { childList: true, subtree: true });
})();
