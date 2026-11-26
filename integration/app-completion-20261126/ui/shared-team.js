'use strict';
(function(root){
 const M=root.FplSharedTeamModel,KEY='fpl-official-team-source-v2',ENTRY=7647524;
 let history=null,context=null,actual=null,selection=null,draft=null,tab='actual',period=null,error='',working=false;
 const host=document.querySelector('[data-shared-team]');if(!host)return;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=n=>Number.isFinite(n)?n.toLocaleString('da-DK',{maximumFractionDigits:1}):'–';
 const emit=()=>root.dispatchEvent(new Event('fpl-official-team-ready'));
 function cached(){try{const v=JSON.parse(localStorage.getItem(KEY));return v?.entry_id===ENTRY?v:null;}catch{return null;}}
 function install(h){
  if(h.entry_id!==ENTRY||h.season!==context.forecast.season||!Array.isArray(h.weeks))throw Error('Den officielle holdkilde matcher ikke manager eller sæson.');
  const weeks=[...h.weeks].sort((a,b)=>b.gw-a.gw),latest=weeks[0];
  const permanent=latest?.active_chip==='freehit'?weeks.find(w=>w.gw<latest.gw&&w.active_chip!=='freehit'):latest;
  if(!permanent)throw Error('Permanent trup efter Free Hit er ikke offentliggjort.');
  const picks=permanent.nominated_picks||permanent.picks;selection=M.lineup(picks,context.people);
  if(!selection)throw Error('De officielle 15 spillere eller opstillingen kan ikke valideres mod spillerkataloget.');
  history=h;actual={season:h.season,gw:context.forecast.gws[0],source_gw:permanent.gw,squad:selection.ids.map(id=>({id})),source:'Senest offentliggjorte FPL-trup',observed_at:h.observed_at};
  try{
   const d=root.FplOfficialManagerImport.fromOfficialHistory(h,ENTRY,context.forecast);
   const prices=root.FplSharedTeam.initialPrices;
   if(prices){const state=root.FplOfficialManagerImport.reconcileOfficialHistory(d,h,context.forecast,prices);actual={...state,source_gw:permanent.gw};root.FplManagerStore.save(state);}
  }catch(e){error='Truppen er hentet. Bank, købspriser eller gratis transfers kan ikke afstemmes: '+e.message;}
  draft=[...selection.ids];render();emit();
 }
 function current(){return tab==='draft'&&draft?draft:selection?.ids||[];}
 function card(id,bench){
  const p=context.people.get(id),week=period==='all'?null:p?.weeks.find(w=>w.gw===Number(period));
  const weeks=period==='all'?p?.weeks:[week];const valid=context.usable&&weeks?.length&&weeks.every(Boolean);
  const xp=valid?weeks.reduce((s,w)=>s+w.xpts,0):null,xm=valid?weeks.reduce((s,w)=>s+w.xmins,0):null;
  const start=valid&&weeks.length===1&&weeks[0].fixtures.length===1?weeks[0].fixtures[0].p_start:null;
  const snapshotOfficial=context.official.players.find(q=>q.id===id),fresh=history?.availability?.next_gw===context.forecast.gws[0]?history.availability.players.find(q=>q.id===id):null,official={...snapshotOfficial,...(fresh?{status:fresh.status,news:fresh.news}:{})},team=context.official.teams?.[p?.team_id];
  const code=team?.code,shirt=code?'https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_'+code+(p?.position===1?'_1':'')+'-110.png':null;
  return '<article class="team-player" data-player-id="'+id+'"><button class="team-player-button" data-choose="'+id+'" '+''+' aria-label="Udskift '+esc(p?.name)+'">'+(shirt?'<img src="'+shirt+'" alt="" loading="lazy">':'<span class="team-shirt" aria-hidden="true">'+esc(team?.short_name||'FPL')+'</span>')+(id===selection.captain?'<b class="captain">C</b>':id===selection.vice?'<b class="captain">V</b>':'')+'<span>'+esc(p?.name||official?.web_name||id)+'</span><strong>'+num(xp)+' xP</strong></button><a href="player.html?id='+id+'">Detaljer</a><small title="Forventede minutter og startchance">'+num(xm)+' min'+(start!==null?' · '+num(100*start)+'% start':'')+'</small>'+(official?.status&&official.status!=='a'?'<small class="team-warning">'+esc(official.news||({d:'Tvivlsom',i:'Skadet',s:'Karantæne',u:'Ude'}[official.status])||'Kontrollér status')+'</small>':'')+'</article>';
 }
 function render(){
  if(!context){host.innerHTML='<h1>'+ (host.dataset.sharedTeam==='transfers'?'Transfers':'Mit hold')+'</h1><p role="status">'+esc(error||'Henter verificerede prognoser og dit officielle hold …')+'</p><button data-start-retry>Prøv igen</button>';host.querySelector('button').onclick=()=>load(true);return;}
  if(!period)period=context.forecast.gws[0];
  let html='<div class="team-heading"><div><p class="eyebrow">FPL ANALYTICS</p><h1>'+ (host.dataset.sharedTeam==='transfers'?'Transfers':'Mit hold')+'</h1></div><button type="button" data-refresh-team '+(working?'disabled':'')+'>Opdatér hold</button></div>';
  html+='<p class="team-status" role="status">'+esc(error||(working?'Henter officielt hold og verificerer historik …':history?'Senest offentliggjorte FPL-hold · nyere transfers efter deadline kan endnu mangle.':'Henter dit hold fra FPL-ID '+ENTRY+' …'))+'</p>';
  if(selection){
   const ids=current(),comparison=M.compare(actual,ids,context.people);
   html+='<div class="team-facts"><span>Bank <b>'+num((tab==='draft'?comparison.bank:actual.bank_tenths)/10*(Number.isInteger(tab==='draft'?comparison.bank:actual.bank_tenths)?1:NaN))+' mio.</b></span><span>Gratis transfers <b>'+num(actual.free_transfers)+'</b></span><span>Prognose <b>GW '+context.forecast.gws[0]+'–'+context.forecast.gws.at(-1)+'</b></span></div>';
   html+='<div class="team-controls"><div role="tablist"><button role="tab" data-tab="actual" aria-selected="'+(tab==='actual')+'">Mit faktiske hold</button><button role="tab" data-tab="draft" aria-selected="'+(tab==='draft')+'">Prøv transfers</button></div><label>Vis <select data-team-period aria-label="Prognoseperiode">'+context.forecast.gws.map(g=>'<option value="'+g+'" '+(String(period)===String(g)?'selected':'')+'>GW '+g+'</option>').join('')+'<option value="all" '+(period==='all'?'selected':'')+'>Samlet seks GW</option></select></label></div>';
   if(!context.usable&&host.dataset.sharedTeam!=='transfers')html+='<p class="team-note">'+esc(context.reason||'Den seneste prognose er udløbet. Holdet er bevaret; forventede point afventer en gyldig prognose.')+'</p>';
   const xi=ids.slice(0,11);html+='<div class="team-pitch" aria-label="11 startere"><div class="pitch-circle"></div>'+[1,2,3,4].map(pos=>'<div class="team-row">'+xi.filter(id=>context.people.get(id).position===pos).map(id=>card(id,false)).join('')+'</div>').join('')+'</div><h2 class="bench-label">Bænk</h2><div class="team-bench" aria-label="4 udskiftere">'+ids.slice(11).map(id=>card(id,true)).join('')+'</div>';
   html+='<p class="team-note">Officiel opstilling fra GW '+actual.source_gw+' · '+esc(new Date(history.observed_at).toLocaleString('da-DK'))+'. Spiller-xP inkluderer ikke kaptajn eller automatiske indskiftninger.</p>';
   if(tab==='draft')html+='<section class="draft-comparison"><h2>Dit midlertidige alternativ</h2><button data-reset-team>Nulstil</button><p>'+comparison.incoming.length+' transfers · hit '+num(comparison.hits)+' point · '+esc(comparison.reason)+'</p><p>Marginal spiller-xP: '+comparison.deltas.map((v,i)=>num(context.usable?v:null)+' ('+[1,3,6][i]+' GW)').join(' · ')+'</p><p>Før kaptajn, bænk og ændret opstilling; ikke en TS v3-optimering. Originalholdet ændres ikke.</p></section>';
   const control=context.plan?.comparison?.hold_squad_without_transfers;if(context.usable&&Array.isArray(control)){const selected=control.filter(w=>period==='all'||w.gw===Number(period));if(selected.length===(period==='all'?context.forecast.gws.length:1)&&selected.every(w=>Number.isFinite(w.expected_score)))html+='<p class="team-note"><strong>Hold-xP uden transfers: '+num(selected.reduce((s,w)=>s+w.expected_score,0))+'</strong> · TS v3-kontrol med modellens kaptajn og indskiftninger, ikke den officielle opstilling.</p>';}
   html+='<section class="team-chips" aria-label="Chips">'+[['wildcard','Wildcard'],['free_hit','Free Hit'],['bench_boost','Bench Boost'],['triple_captain','Triple Captain']].map(([key,label])=>{const uses=actual.chips_used?.[key],half=context.forecast.gws[0]<=19?0:1;return '<div><b>'+label+'</b><span>'+(!uses?'Ikke verificeret':uses.some(g=>(g<=19?0:1)===half)?'Brugt':'Til rådighed')+'</span></div>';}).join('')+'</section>';
  }
  host.innerHTML=html;
  host.querySelector('[data-refresh-team]').onclick=()=>load(true);
  host.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render();});
  host.querySelector('[data-team-period]')?.addEventListener('change',e=>{period=e.target.value;render();});
  host.querySelector('[data-reset-team]')?.addEventListener('click',()=>{draft=[...selection.ids];render();});
  host.querySelectorAll('[data-choose]').forEach(b=>b.onclick=()=>tab==='draft'?choose(Number(b.dataset.choose)):location.assign('player.html?id='+b.dataset.choose));
 }
 function choose(id){
  const player=context.people.get(id),dialog=document.createElement('dialog');dialog.className='replacement-dialog';
  dialog.innerHTML='<form method="dialog"><button aria-label="Luk">Luk</button></form><h2>Erstat '+esc(player.name)+'</h2><label>Søg <input data-replacement-search type="search"></label><label>Klub <select data-replacement-club><option value="">Alle klubber</option>'+Object.values(context.official.teams).map(t=>'<option value="'+t.id+'">'+esc(t.name)+'</option>').join('')+'</select></label><label>Sortér <select data-replacement-sort><option value="xp">Seks-GW xP</option><option value="price">Pris</option><option value="name">Navn</option></select></label><div data-replacement-list></div>';
  document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());
  function list(){const search=dialog.querySelector('input').value.toLocaleLowerCase(),club=dialog.querySelector('[data-replacement-club]').value,sort=dialog.querySelector('[data-replacement-sort]').value;const xp=p=>p.weeks.reduce((s,w)=>s+w.xpts,0);
   dialog.querySelector('[data-replacement-list]').innerHTML=[...context.people.values()].filter(p=>p.position===player.position&&!draft.includes(p.id)&&p.name.toLocaleLowerCase().includes(search)&&(!club||String(p.team_id)===club)).sort((a,b)=>sort==='name'?a.name.localeCompare(b.name):sort==='price'?a.price_tenths-b.price_tenths:xp(b)-xp(a)).map(p=>{const next=draft.map(x=>x===id?p.id:x),c=M.compare(actual,next,context.people);return '<button type="button" data-replace="'+p.id+'" '+(!c.valid?'disabled':'')+'>'+esc(p.name)+' · £'+(p.price_tenths/10).toFixed(1)+' · '+num(context.usable?xp(p):null)+' xP'+(!c.valid?' · '+esc(c.reason):'')+'</button>';}).join('');
   dialog.querySelectorAll('[data-replace]').forEach(b=>b.onclick=()=>{draft=draft.map(x=>x===id?Number(b.dataset.replace):x);dialog.close();render();});}
  dialog.querySelector('input').oninput=list;dialog.querySelectorAll('select').forEach(s=>s.onchange=list);list();dialog.showModal();
 }
 async function load(force=false){
  if(working)return;working=true;error='';render();
  try{
   await root.FplManagerClient.load();context=root.FplManagerClient.snapshot();
   const saved=cached();if(saved){try{root.FplSharedTeam.initialPrices=await root.FplOfficialManagerImport.loadInitialPrices();}catch(e){error=e.message;}install(saved);await root.FplManagerClient.load();context=root.FplManagerClient.snapshot();emit();}
   if(!force&&saved&&Date.now()-Date.parse(saved.observed_at)<600000){working=false;render();return;}
   const h=await root.FplHistoryRefreshClient.run({entryId:ENTRY,season:context.forecast.season,officialOnly:true,onProgress:()=>{}});
   try{root.FplSharedTeam.initialPrices=await root.FplOfficialManagerImport.loadInitialPrices();}catch(e){error='Købspriser kan ikke verificeres: '+e.message;}
   install(h);localStorage.setItem(KEY,JSON.stringify(h));root.FplHistoryRefreshClient.acknowledge();
   await root.FplManagerClient.load();context=root.FplManagerClient.snapshot();emit();
   if(host.dataset.sharedTeam==='transfers'&&context.usable&&context.stateValid&&Number.isInteger(actual.bank_tenths)&&context.state.squad.every(p=>actual.squad.some(q=>q.id===p.id))&&!context.plan&&!context.busy){const k='fpl-shared-auto-'+context.forecast.forecast_sha256+':'+actual.observed_at;if(!sessionStorage.getItem(k)){sessionStorage.setItem(k,'1');root.FplManagerClient.compute();}}
  }catch(e){error=e.message;}finally{working=false;render();}
 }
 root.FplSharedTeam={load,status:()=>({history,actual,selection,draft:current(),context}),initialPrices:null};
 root.addEventListener('fpl-plan-updated',()=>{if(context){context=root.FplManagerClient.snapshot();render();}});
 root.addEventListener('DOMContentLoaded',()=>load());
})(window);
