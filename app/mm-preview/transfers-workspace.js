'use strict';
// Presentation only: original manager client, TS result and private state are retained.
(async()=>{
const target=document.getElementById('transfer-content'),status=document.getElementById('transfer-status'),button=document.querySelector('[data-compute]');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const expanded=new Set();let fetchingLatest=false;
// The official manager-ID dashboard and the manual TS squad live in different
// browser stores. Never pretend the official GW history updated TS itself.
function officialSquadDrift(c){
 try{
  const archive=JSON.parse(localStorage.getItem('fpl-season-team-history-v1')||'null');
  const bucket=archive?.seasons?.[c.forecast.season];
  const latest=Object.values(bucket?.actual||{}).filter(w=>w?.source_kind==='official_export'&&Array.isArray(w.picks)&&w.picks.length===15&&Number.isInteger(w.gw)).sort((a,b)=>b.gw-a.gw)[0];
  if(!latest)return null;
  const officialIds=new Set(latest.picks.map(p=>Number(p.element)));
  if(officialIds.size!==15)return null;
  const savedIds=new Set((c.state?.squad||[]).map(p=>Number(p.id)));
  const missing=[...officialIds].filter(id=>!savedIds.has(id));
  const extra=[...savedIds].filter(id=>!officialIds.has(id));
  const needsConfirmation=!c.state?.squad?.length||missing.length>0||extra.length>0;
  return {gw:latest.gw,missing,extra,needsConfirmation,
   confirmed:!needsConfirmation||localStorage.getItem('fpl-ts-history-drift-confirmed-v1')===JSON.stringify([c.forecast.season,c.forecast.gws[0],latest.gw,[...officialIds].sort((a,b)=>a-b),[...savedIds].sort((a,b)=>a-b)])};
 }catch{return null;}
}
function squadDriftMessage(c,drift){
 const names=ids=>ids.map(id=>c.people.get(id)?.name||'Spiller '+id).join(', ');
 const box=document.createElement('section');box.className='panel';box.id='transfer-squad-drift';box.setAttribute('role','alert');
 box.style.cssText='border:2px solid #b76b17;background:#fffaf0;padding:18px;margin:12px 0;border-radius:12px';
 const heading=document.createElement('h2');heading.textContent='Dit officielle FPL-hold og transferholdet er ikke synkroniseret';
 const msg=document.createElement('p');msg.textContent=c.state?'Dashboardets offentliggjorte hold fra GW '+drift.gw+' afviger fra de 15 spillere, som transferberegningen bruger. Manager-ID henter historik, men opdaterer ikke automatisk de private købspriser og gratis transfers.':'Dit officielle FPL-hold fra GW '+drift.gw+' er hentet via manager-ID, men transfermodellen mangler endnu et bekræftet hold. Importér spillerne som kladde, kontrollér købspriser, bank, gratis transfers og chips, og gem derefter dit aktuelle hold.';
 const detail=document.createElement('p');detail.textContent='Kun i officielt hold: '+(names(drift.missing)||'ingen')+' · Kun i transferhold: '+(names(drift.extra)||'ingen')+'.';
 const advice=document.createElement('p');advice.textContent='Kontrollér dit aktuelle hold i FPL og opdatér det i Mit gemte hold. GW '+drift.gw+' er historik; nyere transfers efter deadline fremgår ikke nødvendigvis. Den gamle Wildcard-plan er skjult indtil du bekræfter forskellen.';
 const link=document.createElement('a');link.href='my-team-classic.html';link.textContent='Åbn Mit gemte hold →';
 const importDraft=document.createElement('button');importDraft.type='button';importDraft.className='btn primary';importDraft.style.marginLeft='12px';importDraft.textContent='Overfør officielt hold som kladde';
 importDraft.onclick=()=>{
  // Official GW picks are past observations, never silently the current live
  // squad. Purchase prices for NEW players cannot be inferred from history.
  const saved=new Map((c.state?.squad||[]).map(p=>[Number(p.id),p]));
  const extra=new Set(drift.extra);
  const ids=[...drift.missing,...(c.state?.squad||[]).map(p=>Number(p.id)).filter(id=>!extra.has(id))];
  const squad=ids.map(id=>({id,...(Number.isInteger(saved.get(id)?.purchase_price_tenths)?{purchase_price_tenths:saved.get(id).purchase_price_tenths}:{})}));
  const draft={gw:c.forecast.gws[0],source:'Kontrollér officielt GW '+drift.gw+'-hold og eventuelle nyere transfers i FPL',observed:'',bank_tenths:undefined,free_transfers:undefined,squad,chips_used:c.state?.chips_used||{wildcard:[],free_hit:[],bench_boost:[],triple_captain:[]}};
  localStorage.setItem('fpl-manager-draft-v1',JSON.stringify(draft));
  location.href='manager-state.html';
 };
 const acknowledge=document.createElement('button');acknowledge.type='button';acknowledge.className='btn secondary';acknowledge.style.marginLeft='12px';acknowledge.textContent='Jeg har verificeret, at transferholdet er aktuelt';
 acknowledge.hidden=!c.state?.squad?.length;acknowledge.onclick=()=>{const extra=new Set(drift.extra),officialIds=[...drift.missing,...c.state.squad.map(p=>p.id).filter(id=>!extra.has(id))].sort((a,b)=>a-b);const savedIds=c.state.squad.map(p=>p.id).sort((a,b)=>a-b);localStorage.setItem('fpl-ts-history-drift-confirmed-v1',JSON.stringify([c.forecast.season,c.forecast.gws[0],drift.gw,officialIds,savedIds]));draw();};
 box.append(heading,msg,detail,advice,link,importDraft,acknowledge);return box;
}
function disclosure(id,title,description,content){
 const d=document.createElement('details');d.id=id;d.className='transfer-disclosure';d.open=expanded.has(id);
 d.innerHTML='<summary><span><strong>'+esc(title)+'</strong><small>'+esc(description)+'</small></span><span class="disclosure-chevron" aria-hidden="true">⌄</span></summary><div class="disclosure-body"></div>';
 d.querySelector('.disclosure-body').append(content);d.addEventListener('toggle',()=>{if(d.isConnected){if(d.open)expanded.add(id);else expanded.delete(id);}});return d;
}
function researchComparison(c){
 const p=c.plan,r=p.research_ts,box=document.createElement('section');box.className='planner-summary';box.id='ts-model-comparison';
 const valid=r?.schema==='ts-v4.1-pr66-v1'&&r.status==='complete'&&r.rho===.9&&r.shortlist_rho===.6&&r.chips_enabled===false&&r.gw===p.gw&&r.forecast_sha256===p.forecast_sha256&&r.manager_state_sha256===p.manager_state_sha256&&Array.isArray(r.plan?.path)&&typeof p.manager_state_sha256==='string'&&typeof p.forecast_sha256==='string'&&r.plan.path.length===p.plan.path.length&&r.plan.path.every((a,i)=>a.gw===p.plan.path[i].gw&&Array.isArray(a.incoming)&&Array.isArray(a.outgoing)&&[a.projected_manager_score,a.official_hit_points,a.bank_after,a.free_transfers_after].every(Number.isFinite));
 const head=document.createElement('h2');head.textContent='Sammenlign TS v3 og TS v4.1';box.append(head);
 const note=document.createElement('p');note.textContent='Samme hold, priser og PM-scenarier. Begge nedenstående transferplaner er uden chips. TS v3 er standard; TS v4.1 er forskning (ρ = 0,90, shortlist ρ = 0,60).';box.append(note);
 if(!valid){const status=document.createElement('p');status.setAttribute('role','status');status.textContent='TS v4.1 er ikke tilgængelig i denne beregning. TS v3 er bevaret. Genberegn, når den nye serverversion er aktiv.';box.append(status);return box;}
 const player=id=>c.people.get(Number(id))?.name||'Spiller '+id,fmt=n=>n.toFixed(2),net=a=>a.projected_manager_score-a.official_hit_points;
 const grid=document.createElement('div');grid.className='ts-comparison-grid';
 for(const [label,model] of [['TS v3 · ρ = 0,60',p],['TS v4.1 · ρ = 0,90 (forsøg)',r]]){
  const card=document.createElement('section');card.className='result-horizon';
  const h=document.createElement('h3');h.textContent=label;card.append(h);
  const a=model.plan.path[0],summary=document.createElement('p');summary.textContent=a.incoming.length?'Ud: '+a.outgoing.map(player).join(', ')+' · Ind: '+a.incoming.map(player).join(', '):'Behold holdet';card.append(summary);
  const totals=document.createElement('p');totals.textContent='GW '+a.gw+': '+fmt(net(a))+' xP efter '+a.official_hit_points+' hitpoint · '+model.plan.path.length+' GW: '+fmt(model.plan.path.reduce((sum,w)=>sum+net(w),0))+' xP efter hits';card.append(totals);
  const lineup=document.createElement('p');lineup.textContent='Kaptajn: '+player(model.lineup?.find(x=>x.role==='C')?.id)+' · Bank £'+(a.bank_after/10).toFixed(1)+'m · '+a.free_transfers_after+' FT næste GW';card.append(lineup);
  const details=document.createElement('details'),title=document.createElement('summary');title.textContent='Se hele transferforløbet';details.append(title);
  for(const w of model.plan.path){const row=document.createElement('p');row.textContent='GW '+w.gw+' · '+(w.incoming.length?w.outgoing.map(player).join(', ')+' → '+w.incoming.map(player).join(', '):'Roll / behold')+' · '+fmt(net(w))+' xP · '+w.official_hit_points+' hitpoint · Bank £'+(w.bank_after/10).toFixed(1)+'m';details.append(row);}
  card.append(details);grid.append(card);
 }
 box.append(grid);return box;
}
function draw(){
 const c=FplManagerClient.snapshot(),drift=officialSquadDrift(c);status.style.removeProperty('display');document.querySelector('.transfer-workspace').dataset.planReady=String(!!c.plan&&c.usable&&c.stateValid&&!c.busy);target.replaceChildren();button.disabled=c.busy;FplPlannerExperience.mount(c);
 document.getElementById('appState').textContent='B-preview · holdsynkronisering v2 · forecast '+c.forecast.data_asof;
 document.getElementById('transfer-retry').hidden=true;document.querySelector('[data-recompute-plan]').hidden=!c.plan;
 document.getElementById('transfer-gw').textContent='GW '+c.forecast.gws[0]+'–'+c.forecast.gws.at(-1);
 const metrics=document.getElementById('transfer-squad');
 metrics.innerHTML=c.state?'<div><small>Dit hold</small><strong>'+esc(c.state.squad.length)+' spillere</strong></div><div><small>I banken nu</small><strong>£'+(c.state.bank_tenths/10).toFixed(1)+'</strong></div><div><small>Gratis transfers nu</small><strong>'+esc(c.state.free_transfers)+'</strong></div><a href="my-team-classic.html">Se mit hold →</a>':'<p>Indlæs dit hold for at få en personlig transferplan.</p>';
 if(drift?.needsConfirmation&&!drift.confirmed){button.disabled=true;document.querySelector('[data-recompute-plan]').hidden=true;document.querySelector('.transfer-workspace').dataset.planReady='false';status.textContent='Der er forskel på dit officielle historiske hold og transfermodellens gemte hold. Kontrollér forskellen nedenfor.';target.append(squadDriftMessage(c,drift));return;}
 if(!c.state){status.innerHTML='<strong>Start med dit hold</strong><p><a href="overview.html#team">Indlæs din private backup →</a></p>';return;}
 if(!c.usable){status.textContent=c.reason;return;}
 if(!c.stateValid){const issues=FplPlannerExperience.diagnose(c.state,c.forecast);status.innerHTML='<strong>'+esc(issues.length?'Holdoplysninger skal opdateres':'Venter på nye modeldata')+'</strong><p>'+esc(issues.join(' ')||c.reason)+'</p>';return;}
 if(!c.plan){status.textContent=c.busy?'Din plan beregnes. Du kan blive på siden og følge status her.':'Klar til din første plan. Vælg Beregn for at finde transfers, startopstilling og chips over seks gameweeks.';return;}
 if(window.FplSeasonCompare)FplSeasonCompare.capture(c).catch(e=>{status.style.display='block';status.textContent='Planen er klar, men GW-arkivet kunne ikke gemmes: '+e.message});
 const p=c.plan,first=p.plan.path[0],chipAdvice=FplTransferResultSummary.chipAdvice(c),chipActive=chipAdvice.dataset.chip!=='none';target.append(chipAdvice,researchComparison(c));
 status.textContent='Personlig plan klar · GW '+p.gw+' · forslagene ændrer ikke dit gemte hold.';
 const hero=document.createElement('section');hero.className='planner-summary';hero.innerHTML='<div class="workspace-eyebrow">Anbefalet til næste gameweek</div>'+FplTransferCard.html(p,c.people);
 const title=hero.querySelector('.transfer-card-head h3');if(title)title.textContent=chipActive?'Alternativ uden chip':first.incoming.length?'Dit anbefalede træk':'Behold holdet denne uge';if(chipActive)hero.querySelector('.workspace-eyebrow').textContent='Normal transferplan · uden chip';
 const why=hero.querySelector('.planner-why');if(why){why.remove();hero.append(disclosure('transfer-player-evidence','Spillernes tal og usikkerhed','xP, minutter og startsandsynlighed for de foreslåede spillere',why));}
 FplTransferResultSummary.enhance(hero,c);
 const grid=document.createElement('div');grid.className='result-ready-grid';const normalLineup=FplTransferResultSummary.lineup(c);if(chipActive)normalLineup.querySelector('h3').prepend('Uden chip · ');grid.append(hero,normalLineup);let detailTarget=target;
 if(chipAdvice.dataset.chip==='wildcard'){
  target.append(FplTransferResultSummary.wildcardHorizon(c));
  const alternative=document.createElement('details');alternative.id='transfer-normal-alternative';alternative.className='transfer-disclosure';alternative.innerHTML='<summary><strong>Alternativ uden Wildcard · normale transfers</strong></summary>';const body=document.createElement('div');body.className='disclosure-body';const normalHorizon=FplTransferResultSummary.horizon(c);normalHorizon.querySelector('h3').textContent='Uden Wildcard · seks-GW-alternativ';body.append(grid,FplTransferResultSummary.insights(c),FplTransferResultSummary.risks(c),normalHorizon);alternative.append(body);target.append(alternative);detailTarget=body;
 }else target.append(grid,FplTransferResultSummary.insights(c),FplTransferResultSummary.risks(c),FplTransferResultSummary.horizon(c));
 const temp=document.createElement('div');FplPlanView.render(p,c.people,temp);
 for(const [id,key,title,description]of [
  ['teamResult','transfer-lineup','Anbefalet startopstilling','Se kaptajn, startellever og bænk efter de foreslåede transfers'],
  ['transferResult','transfer-path','Planen over seks gameweeks','Transfers, point, budget og beslutningsværdi uge for uge'],
  ['chipResult','transfer-chips','Chips og timing','Se den originale models chipforslag']]){
  const section=temp.querySelector('#'+id);if(section){if(id==='teamResult'){const note=document.createElement('p');note.className='workspace-note';note.textContent='Modellens forslag efter transfers. Dit faktiske hold i My Team er uændret.';section.prepend(note);}(id==='chipResult'?target:detailTarget).append(disclosure(key,chipAdvice.dataset.chip==='wildcard'&&id!=='chipResult'?'Uden WC · '+title:title,description,section));}
 }
 const data=document.createElement('section');data.id='transfer-result-data';data.className='result-data';for(const id of ['planner-context','latest-snapshot-info']){const node=document.getElementById(id);if(node)data.append(node);}target.append(data);
}
function failed(e){target.replaceChildren();status.textContent='Planen kunne ikke hentes: '+e.message;const retry=document.getElementById('transfer-retry');retry.hidden=false;retry.onclick=()=>location.reload();}
document.querySelector('[data-open-alternatives]').addEventListener('click',()=>{const panel=document.getElementById('transfer-alternatives');panel.open=true;panel.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});panel.querySelector('summary').focus();});
async function latest(force=false){
 const snap=FplManagerClient.snapshot(),drift=officialSquadDrift(snap);
 if(drift?.needsConfirmation&&!drift.confirmed){draw();return;}
 if(fetchingLatest||snap.busy)return;
 fetchingLatest=true;button.disabled=true;button.setAttribute('aria-busy','true');button.textContent='Henter nyeste plan…';status.textContent='Henter de nyeste modeldata og din gemte transferplan…';
 try{
  // Invalidate the adapter's short-lived cache before refreshing the client.
  await FplBExistingApp.forecast();await FplManagerClient.load();draw();FplTransferPreview.render();
  const current=FplManagerClient.snapshot().plan;
  if(force||!current||current.research_ts?.schema!=='ts-v4.1-pr66-v1')await FplManagerClient.compute({replaceExisting:!!current});
  else {target.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
 }catch(e){failed(e);}finally{fetchingLatest=false;button.removeAttribute('aria-busy');button.disabled=FplManagerClient.snapshot().busy;button.textContent=button.disabled?'Beregning i gang…':'Vis nyeste transferplan';}
}
try{await FplManagerClient.load();draw();FplTransferPreview.render();FplManagerClient.bind(()=>{draw();FplTransferPreview.render();});button.onclick=()=>latest();document.querySelector('[data-recompute-plan]').onclick=()=>latest(true);setInterval(async()=>{try{await FplManagerClient.load();draw();FplTransferPreview.render();}catch(e){failed(e);}},300000);}catch(e){failed(e);}
})();
