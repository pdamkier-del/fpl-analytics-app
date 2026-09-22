(()=>{
  const D=window.FPL_DATA;
  if(!D||!Array.isArray(D.forecasts)) return;
  const css=`
  .brand-link{color:inherit;text-decoration:none}.global-player-jump{margin:0 8px 20px;position:relative}.global-player-jump .jump-label{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#6f8797;margin:0 2px 6px}.global-player-jump input{width:100%;border:1px solid #2a3a45;background:#13232e;color:#fff;border-radius:9px;padding:9px 10px;font-size:12px;outline:none}.global-player-jump input:focus{border-color:#58d6a3;box-shadow:0 0 0 2px rgba(88,214,163,.12)}.global-player-jump input::placeholder{color:#8296a3}.global-results{display:none;position:absolute;left:0;right:0;top:56px;z-index:100;background:#fff;color:#17212a;border:1px solid #dfe5e8;border-radius:11px;box-shadow:0 14px 35px rgba(0,0,0,.18);max-height:330px;overflow:auto}.global-results.open{display:block}.jump-result{display:flex;justify-content:space-between;gap:10px;padding:10px 11px;border-bottom:1px solid #edf0f2;cursor:pointer}.jump-result:last-child{border-bottom:0}.jump-result:hover,.jump-result.active{background:#f3faf7}.jump-name{font-size:12px;font-weight:800}.jump-meta{font-size:10px;color:#6a747d;margin-top:2px}.jump-xp{font-size:11px;color:#0b7a53;font-weight:850;white-space:nowrap}.player-jumpable{cursor:pointer;transition:transform .12s ease,box-shadow .12s ease}.player-jumpable:hover{transform:translateY(-1px);box-shadow:0 7px 18px rgba(17,31,44,.10)}.player-link-hint{font-size:10px;color:#0b7a53;font-weight:750;margin-left:4px}.player-nav-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.player-nav-actions a{display:inline-flex;align-items:center;gap:5px;text-decoration:none}.club-inline-link{color:#3156d8;text-decoration:none;font-weight:750}.club-inline-link:hover{text-decoration:underline}.clickable[title]{position:relative}.clickable[title] td:first-child .player:after{content:'Open';font-size:9px;color:#0b7a53;background:#e8f6f0;border-radius:999px;padding:3px 6px;margin-left:3px;font-weight:800;opacity:0}.clickable[title]:hover td:first-child .player:after{opacity:1}
  @media(max-width:980px){.global-player-jump{display:none}}
  `;
  const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);

  // Make the brand a reliable way home.
  const brand=document.querySelector('.brand');
  if(brand && brand.parentElement?.tagName!=='A'){
    const a=document.createElement('a');a.href='overview.html';a.className='brand-link';
    brand.parentNode.insertBefore(a,brand);a.appendChild(brand);
  }

  // Global player search in sidebar.
  const sidebar=document.querySelector('.sidebar');
  if(sidebar && !document.getElementById('globalPlayerSearch')){
    const box=document.createElement('div');box.className='global-player-jump';
    box.innerHTML=`<div class="jump-label">Jump to player</div><input id="globalPlayerSearch" autocomplete="off" placeholder="Search 562 players…"><div id="globalPlayerResults" class="global-results"></div>`;
    const brandLink=sidebar.querySelector('.brand-link')||sidebar.querySelector('.brand');
    brandLink.insertAdjacentElement('afterend',box);
    const input=box.querySelector('input'), results=box.querySelector('.global-results');
    let shown=[];let active=-1;
    const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const render=()=>{
      const q=norm(input.value.trim());
      if(!q){results.classList.remove('open');results.innerHTML='';shown=[];active=-1;return;}
      shown=D.forecasts.filter(p=>norm(`${p.player} ${p.full_name||''} ${p.club}`).includes(q)).sort((a,b)=>(b.xpts6||0)-(a.xpts6||0)).slice(0,8);
      results.innerHTML=shown.length?shown.map((p,i)=>`<div class="jump-result" data-i="${i}"><div><div class="jump-name">${p.player}</div><div class="jump-meta">${p.club} · ${p.pos} · £${Number(p.price||0).toFixed(1)}m</div></div><div class="jump-xp">${Number(p.xpts6||0).toFixed(1)} xPts</div></div>`).join(''):`<div class="jump-result"><div class="jump-meta">No players found</div></div>`;
      results.classList.add('open');active=-1;
      results.querySelectorAll('[data-i]').forEach(el=>el.addEventListener('click',()=>location.href=`player.html?id=${shown[Number(el.dataset.i)].id}`));
    };
    input.addEventListener('input',render);
    input.addEventListener('keydown',e=>{
      const els=[...results.querySelectorAll('[data-i]')];
      if(e.key==='ArrowDown'&&els.length){e.preventDefault();active=Math.min(active+1,els.length-1)}
      else if(e.key==='ArrowUp'&&els.length){e.preventDefault();active=Math.max(active-1,0)}
      else if(e.key==='Enter'&&shown.length){e.preventDefault();const i=active>=0?active:0;location.href=`player.html?id=${shown[i].id}`;return}
      else if(e.key==='Escape'){results.classList.remove('open');input.blur();return}
      else return;
      els.forEach((x,i)=>x.classList.toggle('active',i===active));
    });
    document.addEventListener('click',e=>{if(!box.contains(e.target))results.classList.remove('open')});
    document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();input.focus();input.select()}});
  }

  // Make already-clickable table rows visibly discoverable.
  document.querySelectorAll('tr.clickable').forEach(r=>{if(!r.title)r.title='Open player profile'});

  // Turn My Team player cards / bench items into profile links when we can match a player.
  const alias={'dcl':'Calvert-Lewin','b fernandes':'B.Fernandes','bruno fernandes':'B.Fernandes'};
  const normalizeName=s=>String(s||'').replace(/\b[CcVv]\b/g,'').replace(/[^A-Za-zÀ-ÿ. -]/g,' ').replace(/\s+/g,' ').trim().toLowerCase();
  const findPlayer=name=>{
    let q=normalizeName(name); if(alias[q]) q=normalizeName(alias[q]);
    return D.forecasts.find(p=>normalizeName(p.player)===q)||D.forecasts.find(p=>normalizeName(p.full_name)===q)||D.forecasts.find(p=>normalizeName(p.player).includes(q)||q.includes(normalizeName(p.player)));
  };
  document.querySelectorAll('.player-card').forEach(card=>{
    const nameEl=card.querySelector('.name'); if(!nameEl)return;
    const clone=nameEl.cloneNode(true);clone.querySelectorAll('.tag').forEach(x=>x.remove());
    const p=findPlayer(clone.textContent);
    if(p){card.classList.add('player-jumpable');card.title=`Open ${p.player}`;card.addEventListener('click',()=>location.href=`player.html?id=${p.id}`)}
  });
  document.querySelectorAll('.bench-item').forEach(item=>{
    const name=(item.querySelector('span')?.textContent||'').split('·')[0].trim();const p=findPlayer(name);
    if(p){item.classList.add('player-jumpable');item.title=`Open ${p.player}`;item.addEventListener('click',()=>location.href=`player.html?id=${p.id}`)}
  });

  // On any player profile, add previous/next navigation and club shortcut.
  const playerName=document.getElementById('playerName');
  if(playerName){
    const id=Number(new URLSearchParams(location.search).get('id')||411);const current=D.forecasts.find(x=>x.id===id)||D.forecasts[0];
    const ordered=[...D.forecasts].sort((a,b)=>(b.xpts6||0)-(a.xpts6||0));const idx=ordered.findIndex(x=>x.id===current.id);
    const prev=ordered[(idx-1+ordered.length)%ordered.length], next=ordered[(idx+1)%ordered.length];
    const pageHead=document.querySelector('.page-head');const oldBack=pageHead?.querySelector('a.ghost');
    if(pageHead){
      const actions=document.createElement('div');actions.className='player-nav-actions';
      actions.innerHTML=`<a class="ghost" href="player.html?id=${prev.id}" title="Previous in 6GW ranking">← ${prev.player}</a><a class="ghost" href="index.html?club=${current.club}">${current.club} club</a><a class="ghost" href="rankings.html">All players</a><a class="ghost" href="player.html?id=${next.id}" title="Next in 6GW ranking">${next.player} →</a>`;
      if(oldBack)oldBack.replaceWith(actions);else pageHead.appendChild(actions);
    }
    const meta=document.getElementById('playerMeta');
    if(meta){
      const html=meta.innerHTML;meta.innerHTML=html.replace(new RegExp(`^${current.club}`),`<a class="club-inline-link" href="index.html?club=${current.club}">${current.club}</a>`);
    }
  }
})();
(()=>{
  const file=(location.pathname.split('/').pop()||'overview.html').toLowerCase();
  const sidebar=document.querySelector('.sidebar'); if(!sidebar)return;
  const titles=[...sidebar.querySelectorAll('.nav-title')];
  const modelTitle=titles.find(x=>x.textContent.trim().toLowerCase()==='model');
  if(modelTitle){
    const nav=modelTitle.nextElementSibling;
    if(nav?.classList.contains('nav') && !nav.querySelector('a[href="model-lab.html"]')){
      const lab=document.createElement('a');lab.href='model-lab.html';lab.innerHTML='<span>Model Lab</span>';
      const replay=nav.querySelector('a[href="replay.html"]'); if(replay)nav.insertBefore(lab,replay); else nav.appendChild(lab);
    }
  }
  sidebar.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('active',(a.getAttribute('href')||'').toLowerCase()===file));
  const foot=sidebar.querySelector('.sidebar-foot'); if(foot && location.protocol.startsWith('http')) foot.innerHTML='Local desktop app<br/>Real 2026/27 data connected.<br/>Model versions saved locally.';
})();
(()=>{
 if((location.pathname.split('/').pop()||'').toLowerCase()!=='model-status.html')return;
 const main=document.querySelector('.main'); if(!main||document.getElementById('modelLabCTA'))return;
 const panel=document.createElement('div'); panel.id='modelLabCTA'; panel.className='panel'; panel.style.marginTop='16px';
 panel.innerHTML='<div class="panel-head">Editable mathematics</div><div class="panel-body"><div style="font-size:13px;color:var(--muted);line-height:1.55;margin-bottom:12px">Model parameters and versions now live outside the frontend. Changes can be saved as new versions and compared in replay rather than overwriting the baseline.</div><a class="ghost" href="model-lab.html">Open Model Lab →</a></div>';
 main.appendChild(panel);
})();
