'use strict';
// Presentation only: original manager client, TS result and private state are retained.
(async()=>{
const target=document.getElementById('transfer-content'),status=document.getElementById('transfer-status'),button=document.querySelector('[data-compute]');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const expanded=new Set();let fetchingLatest=false;
function disclosure(id,title,description,content){
 const d=document.createElement('details');d.id=id;d.className='transfer-disclosure';d.open=expanded.has(id);
 d.innerHTML='<summary><span><strong>'+esc(title)+'</strong><small>'+esc(description)+'</small></span><span class="disclosure-chevron" aria-hidden="true">⌄</span></summary><div class="disclosure-body"></div>';
 d.querySelector('.disclosure-body').append(content);d.addEventListener('toggle',()=>{if(d.isConnected){if(d.open)expanded.add(id);else expanded.delete(id);}});return d;
}
function draw(){
 const c=FplManagerClient.snapshot();document.querySelector('.transfer-workspace').dataset.planReady=String(!!c.plan&&c.usable&&c.stateValid&&!c.busy);target.replaceChildren();button.disabled=c.busy;FplPlannerExperience.mount(c);
 document.getElementById('appState').textContent='B-preview · forecast '+c.forecast.data_asof;
 document.getElementById('transfer-retry').hidden=true;document.querySelector('[data-recompute-plan]').hidden=!c.plan;
 document.getElementById('transfer-gw').textContent='GW '+c.forecast.gws[0]+'–'+c.forecast.gws.at(-1);
 const metrics=document.getElementById('transfer-squad');
 metrics.innerHTML=c.state?'<div><small>Dit hold</small><strong>'+esc(c.state.squad.length)+' spillere</strong></div><div><small>I banken nu</small><strong>£'+(c.state.bank_tenths/10).toFixed(1)+'</strong></div><div><small>Gratis transfers nu</small><strong>'+esc(c.state.free_transfers)+'</strong></div><a href="my-team-classic.html">Se mit hold →</a>':'<p>Indlæs dit hold for at få en personlig transferplan.</p>';
 if(!c.state){status.innerHTML='<strong>Start med dit hold</strong><p><a href="overview.html#team">Indlæs din private backup →</a></p>';return;}
 if(!c.usable){status.textContent=c.reason;return;}
 if(!c.stateValid){const issues=FplPlannerExperience.diagnose(c.state,c.forecast);status.innerHTML='<strong>'+esc(issues.length?'Holdoplysninger skal opdateres':'Venter på nye modeldata')+'</strong><p>'+esc(issues.join(' ')||c.reason)+'</p>';return;}
 if(!c.plan){status.textContent=c.busy?'Din plan beregnes. Du kan blive på siden og følge status her.':'Klar til din første plan. Vælg Beregn for at finde transfers, startopstilling og chips over seks gameweeks.';return;}
 const p=c.plan,first=p.plan.path[0];
 status.textContent='Personlig plan klar · GW '+p.gw+' · forslagene ændrer ikke dit gemte hold.';
 const hero=document.createElement('section');hero.className='planner-summary';hero.innerHTML='<div class="workspace-eyebrow">Anbefalet til næste gameweek</div>'+FplTransferCard.html(p,c.people);
 const title=hero.querySelector('.transfer-card-head h3');if(title)title.textContent=first.incoming.length?'Dit anbefalede træk':'Behold holdet denne uge';
 const why=hero.querySelector('.planner-why');if(why){why.remove();hero.append(disclosure('transfer-player-evidence','Spillernes tal og usikkerhed','xP, minutter og startsandsynlighed for de foreslåede spillere',why));}
 FplTransferResultSummary.enhance(hero,c);
 const grid=document.createElement('div');grid.className='result-ready-grid';grid.append(hero,FplTransferResultSummary.lineup(c));target.append(grid,FplTransferResultSummary.insights(c),FplTransferResultSummary.risks(c),FplTransferResultSummary.horizon(c));
 const temp=document.createElement('div');FplPlanView.render(p,c.people,temp);
 for(const [id,key,title,description]of [
  ['teamResult','transfer-lineup','Anbefalet startopstilling','Se kaptajn, startellever og bænk efter de foreslåede transfers'],
  ['transferResult','transfer-path','Planen over seks gameweeks','Transfers, point, budget og beslutningsværdi uge for uge'],
  ['chipResult','transfer-chips','Chips og timing','Se den originale models chipforslag']]){
  const section=temp.querySelector('#'+id);if(section){if(id==='teamResult'){const note=document.createElement('p');note.className='workspace-note';note.textContent='Modellens forslag efter transfers. Dit faktiske hold i My Team er uændret.';section.prepend(note);}target.append(disclosure(key,title,description,section));}
 }
 const data=document.createElement('section');data.id='transfer-result-data';data.className='result-data';for(const id of ['planner-context','latest-snapshot-info']){const node=document.getElementById(id);if(node)data.append(node);}target.append(data);
}
function failed(e){target.replaceChildren();status.textContent='Planen kunne ikke hentes: '+e.message;const retry=document.getElementById('transfer-retry');retry.hidden=false;retry.onclick=()=>location.reload();}
document.querySelector('[data-open-alternatives]').addEventListener('click',()=>{const panel=document.getElementById('transfer-alternatives');panel.open=true;panel.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});panel.querySelector('summary').focus();});
async function latest(force=false){
 if(fetchingLatest||FplManagerClient.snapshot().busy)return;
 fetchingLatest=true;button.disabled=true;button.setAttribute('aria-busy','true');button.textContent='Henter nyeste plan…';status.textContent='Henter de nyeste modeldata og din gemte transferplan…';
 try{
  // Invalidate the adapter's short-lived cache before refreshing the client.
  await FplBExistingApp.forecast();await FplManagerClient.load();draw();FplTransferPreview.render();
  if(force||!FplManagerClient.snapshot().plan)await FplManagerClient.compute();
  else {target.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
 }catch(e){failed(e);}finally{fetchingLatest=false;button.removeAttribute('aria-busy');button.disabled=FplManagerClient.snapshot().busy;button.textContent=button.disabled?'Beregning i gang…':'Vis nyeste transferplan';}
}
try{await FplManagerClient.load();draw();FplTransferPreview.render();FplManagerClient.bind(()=>{draw();FplTransferPreview.render();});button.onclick=()=>latest();document.querySelector('[data-recompute-plan]').onclick=()=>latest(true);setInterval(async()=>{try{await FplManagerClient.load();draw();FplTransferPreview.render();}catch(e){failed(e);}},300000);}catch(e){failed(e);}
})();
