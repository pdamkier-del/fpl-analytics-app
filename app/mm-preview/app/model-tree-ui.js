/* Interactive hierarchical model mathematics. No external runtime or math CDN. */
(function () {
  'use strict';
  const payload = window.FPL_MODEL_TREE;
  if (!payload || !Array.isArray(payload.nodes)) return;
  const nodes = payload.nodes, index = new Map(nodes.map(n => [n.id, n]));
  const kids = new Map();
  for (const n of nodes) {
    if (n.parent) {
      if (!kids.has(n.parent)) kids.set(n.parent, []);
      kids.get(n.parent).push(n);
    }
  }
  const main = document.getElementById('model-detail');
  const nav = document.getElementById('model-nav-tree');
  const roadmap = document.getElementById('model-roadmap');
  const search = document.getElementById('model-tree-search');
  const searchResults = document.getElementById('model-search-results');
  const currentCounter = document.getElementById('model-node-count');
  if (!main || !nav || !roadmap || !search || !searchResults) return;
  const expanded = new Set(['root']);
  let current = 'root';
  const groups = { mm: 'minutes', pm: 'points', ts: 'strategy', chips: 'chips', data: 'evidence', root: 'overview' };
  const order = nodes.map(n => n.id);

  const escapeHtml = input => String(input == null ? '' : input)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const getPath = id => {
    const out = [], seen = new Set();
    while (id && index.has(id) && !seen.has(id)) {
      seen.add(id); out.unshift(index.get(id)); id = index.get(id).parent;
    }
    return out;
  };
  const nodeGroup = id => {
    const path = getPath(id);
    return path.length > 1 ? groups[path[1].id] || 'overview' : 'overview';
  };
  const childNodes = id => kids.get(id) || [];
  const textBlob = n => [n.title, n.summary, n.idea, ...n.details,
    ...n.formulas.flatMap(f => [f.expression, f.meaning]), ...n.sources]
    .join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('da-DK');

  function renderRoadmap() {
    const entries = childNodes('root');
    roadmap.innerHTML = entries.map((n, i) => `
      <button type="button" class="roadmap-node category-${escapeHtml(nodeGroup(n.id))}"
        data-open-node="${escapeHtml(n.id)}" aria-label="Åbn ${escapeHtml(n.title)}">
        <span class="roadmap-index">0${i + 1}</span>
        <span class="roadmap-label">${escapeHtml(n.title)}</span>
        <span class="roadmap-sub">${escapeHtml(n.summary)}</span>
        <span class="roadmap-count">${countDescendants(n.id)} emner <span aria-hidden="true">↘</span></span>
      </button>`).join('');
    updateRoadmap();
  }
  function countDescendants(id) {
    return childNodes(id).reduce((total, n) => total + 1 + countDescendants(n.id), 0);
  }
  function updateRoadmap() {
    const activeGroup = getPath(current)[1]?.id;
    roadmap.querySelectorAll('[data-open-node]').forEach(el => {
      el.classList.toggle('is-branch-active', el.dataset.openNode === activeGroup);
    });
  }
  function renderTree() {
    const branch = (node, depth = 0) => {
      const children = childNodes(node.id);
      const isOpen = expanded.has(node.id);
      const isActive = node.id === current;
      const label = `<button type="button" class="model-tree-label ${isActive ? 'active' : ''}"
       data-open-node="${escapeHtml(node.id)}" ${isActive ? 'aria-current="page"' : ''}
       title="${escapeHtml(node.summary)}">${escapeHtml(node.title)}</button>`;
      const toggle = children.length ?
        `<button type="button" class="tree-toggle" aria-label="${isOpen ? 'Luk' : 'Åbn'} ${escapeHtml(node.title)}"
        aria-expanded="${isOpen}" data-toggle-node="${escapeHtml(node.id)}">${isOpen ? '−' : '+'}</button>`
        : '<span class="tree-leaf" aria-hidden="true">·</span>';
      const sub = children.length && isOpen ?
        `<div class="model-tree-children">${children.map(c => branch(c, depth + 1)).join('')}</div>` : '';
      return `<div class="model-tree-branch depth-${Math.min(depth, 4)}">
         <div class="model-tree-row category-${escapeHtml(nodeGroup(node.id))}">${toggle}${label}</div>
         ${sub}</div>`;
    };
    nav.innerHTML = branch(index.get('root'));
    currentCounter.textContent = nodes.length + ' emner';
  }
  function renderSearch() {
    const q = search.value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('da-DK');
    if (!q) { searchResults.hidden = true; searchResults.innerHTML = ''; return; }
    const terms = q.split(/\s+/).filter(Boolean);
    const hits = nodes.filter(n => terms.every(t => textBlob(n).includes(t))).slice(0, 18);
    searchResults.hidden = false;
    searchResults.innerHTML = `<div class="result-title">${hits.length ? hits.length + ' match' : 'Ingen match'}</div>` +
      hits.map(n => `<button type="button" class="search-hit" data-open-node="${escapeHtml(n.id)}">
       <span class="search-hit-title">${escapeHtml(n.title)}</span>
       <span class="search-hit-path">${escapeHtml(getPath(n.id).slice(1, -1).map(x => x.title).join(' / ') || 'FPL-modellen')}</span>
       </button>`).join('');
  }
  function sourceHref(path) {
    // Only repository-owned files; never take an external URL from data.
    if (!/^(analysis|config|src|scripts|tests)\/[\w./-]+$/.test(path) || path.includes('..')) return null;
    return `https://github.com/${payload.repository}/blob/${payload.checkpoint}/${path.split('/').map(encodeURIComponent).join('/')}`;
  }
  function renderDetail(id) {
    const n = index.get(id);
    if (!n) return;
    const path = getPath(id);
    const children = childNodes(id);
    const category = nodeGroup(id);
    const crumbs = path.map((p, i) => i === path.length - 1 ?
      `<span aria-current="page">${escapeHtml(p.title)}</span>` :
      `<button type="button" data-open-node="${escapeHtml(p.id)}">${escapeHtml(p.title)}</button><span aria-hidden="true">/</span>`).join('');
    const eqs = n.formulas.length ? `<section class="detail-section">
      <h3>Matematikken</h3><p class="detail-hint">De centrale formler fra implementeringen, med forklaringer.</p>
      <div class="formula-list">${n.formulas.map((f, i) =>
        `<div class="formula-block"><div class="formula-head"><span>Ligning ${i + 1}</span>
           <button class="copy-formula" type="button" data-copy-formula="${escapeHtml(n.id)}:${i}">Kopiér</button></div>
           <div class="formula-math" role="math" aria-label="${escapeHtml(f.expression)}">${escapeHtml(f.expression)}</div>
           <p class="formula-explanation">${escapeHtml(f.meaning)}</p></div>`).join('')}</div></section>` : '';
    const details = n.details.length ? `<section class="detail-section"><h3>Vigtige detaljer</h3>
        <ul class="key-list">${n.details.map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul></section>` : '';
    const sub = children.length ? `<section class="detail-section"><h3>Gå et niveau dybere</h3>
      <div class="detail-child-grid">${children.map(c => `<button type="button" class="detail-child"
        data-open-node="${escapeHtml(c.id)}"><strong>${escapeHtml(c.title)}</strong>
        <span>${escapeHtml(c.summary)}</span><b aria-hidden="true">↗</b></button>`).join('')}</div></section>` : '';
    const sources = n.sources.map(source => {
      const url = sourceHref(source);
      return url ? `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">
        <span aria-hidden="true">↗</span>${escapeHtml(source)}</a>` : '';
    }).join('');
    const position = order.indexOf(id);
    const previousId = order[position - 1], nextId = order[position + 1];
    main.innerHTML = `<div class="detail-inner category-${escapeHtml(category)}">
      <nav class="model-breadcrumb" aria-label="Sti gennem modellen">${crumbs}</nav>
      <div class="detail-eyebrow"><span class="group-indicator"></span>
       ${escapeHtml(category === 'overview' ? 'Samlet model' : category === 'minutes' ? 'Minutmodel' : category === 'points' ? 'Pointmodel' : category === 'strategy' ? 'Transferstrategi' : category === 'chips' ? 'Chipstrategi' : 'Data og kontrol')}
       <span class="detail-depth">Niveau ${path.length - 1}</span></div>
      <h2 id="detail-title" tabindex="-1">${escapeHtml(n.title)}</h2>
      <p class="detail-lead">${escapeHtml(n.summary)}</p>
      <section class="detail-section detail-idea"><h3>Idéen</h3><p>${escapeHtml(n.idea)}</p></section>
      ${eqs}${details}${sub}
      ${sources ? `<section class="detail-section"><h3>I den låste kildekode</h3>
       <div class="source-links">${sources}</div></section>` : ''}
      <div class="detail-bottom-nav">
        ${previousId ? `<button type="button" data-open-node="${escapeHtml(previousId)}">← Forrige emne</button>` : '<span></span>'}
        ${nextId ? `<button type="button" data-open-node="${escapeHtml(nextId)}">Næste emne →</button>` : '<span></span>'}
      </div></div>`;
  }
  function selectNode(id, updateUrl = true, focus = true) {
    if (!index.has(id)) id = 'root';
    current = id;
    getPath(id).forEach(n => expanded.add(n.id));
    renderTree();
    renderDetail(id);
    updateRoadmap();
    if (updateUrl) history.replaceState(null, '', '#model=' + encodeURIComponent(id));
    if (focus) {
      main.querySelector('#detail-title')?.focus({ preventScroll: true });
      document.getElementById('model-workspace')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
  }
  function fromHash() {
    const hash = location.hash || '';
    const id = hash.startsWith('#model=') ? decodeURIComponent(hash.slice(7)) :
      ({'#minutes': 'mm', '#points': 'pm', '#transfers': 'ts', '#chips': 'chips'})[hash] || 'root';
    selectNode(id, false, false);
  }
  document.addEventListener('click', event => {
    const select = event.target.closest('[data-open-node]');
    if (select) { selectNode(select.dataset.openNode); return; }
    const toggle = event.target.closest('[data-toggle-node]');
    if (toggle) {
      const id = toggle.dataset.toggleNode;
      if (expanded.has(id)) expanded.delete(id); else expanded.add(id);
      renderTree();
      return;
    }
    const copy = event.target.closest('[data-copy-formula]');
    if (copy) {
      const [id, ix] = copy.dataset.copyFormula.split(':');
      const text = index.get(id)?.formulas[Number(ix)]?.expression;
      if (!text) return;
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          copy.textContent = 'Kopieret ✓';
        }).catch(() => {
          copy.textContent = 'Kan ikke kopiere';
        });
      } else {
        copy.textContent = 'Markér ligningen manuelt';
      }
    }
  });
  document.getElementById('expand-model-tree')?.addEventListener('click', () => {
    for (const n of nodes) expanded.add(n.id);
    renderTree();
  });
  document.getElementById('collapse-model-tree')?.addEventListener('click', () => {
    expanded.clear(); expanded.add('root');
    renderTree();
  });
  search.addEventListener('input', renderSearch);
  search.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const first = searchResults.querySelector('[data-open-node]');
      if (first) selectNode(first.dataset.openNode);
    }
    if (e.key === 'Escape') { search.value = ''; renderSearch(); search.focus(); }
  });
  window.addEventListener('hashchange', fromHash);
  window.FPL_MODEL_EXPLORER = Object.freeze({ getPath, childNodes, countDescendants, getNode: id => index.get(id) });
  renderRoadmap();
  fromHash();
})();
