'use strict';
(async()=>{
const target=document.getElementById('transfer-content'),status=document.getElementById('transfer-status'),button=document.querySelector('[data-compute]');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>Number.isFinite(x)?x.toFixed(2):'Not Available';
function draw(){
 const c=FplManagerClient.snapshot();target.replaceChildren();button.disabled=c.busy;
 document.getElementById('appState').textContent='Diagnostisk · cutoff '+c.forecast.data_asof;
 const retry=document.getElementById('transfer-retry');if(retry)retry.hidden=true;
 if(!c.state){status.innerHTML='<strong>Dit faktiske hold mangler i denne browser.</strong><p><a href="overview.html#team">Genindlæs din private backup én gang</a></p>';return}
 const info=document.createElement('p');info.className='manager-context';info.textContent='Dit faktiske hold: '+c.state.squad.length+' spillere · bank £'+(c.state.bank_tenths/10).toFixed(1)+' · '+c.state.free_transfers+' gratis transfers · GW '+c.state.gw+'. Forslagene nedenfor ændrer ikke dit gemte hold.';target.append(info);
 if(!c.usable){status.textContent=c.reason;return}
 if(!c.stateValid){status.innerHTML='<strong>Dit private hold er bevaret, men oplysningerne kræver en opdatering.</strong><p><a href="manager-state.html">Redigér hold, priser, GW og observationstidspunkt</a></p>';return}
 if(!c.plan){status.textContent=c.busy?'Original Python-beregning er i gang. Jobstatus vises ovenfor; dit hold er bevaret.':'Dit hold er gemt. Forecastet eller holdet er ændret, eller der er endnu ingen gyldig plan. Tryk Genberegn original TS v3 + chips.';return}
 status.textContent='GW '+c.plan.gw+' · cutoff '+c.plan.forecast_cutoff+' · personlig diagnostisk TS v3';
 const p=c.plan,first=p.plan.path[0],hold=p.comparison?.hold_squad_without_transfers||[],total=p.plan.path.reduce((s,a)=>s+a.projected_manager_score-a.official_hit_points,0),keep=hold.reduce((s,a)=>s+a.expected_score,0);
 const summary=document.createElement('section');summary.className='planner-summary';summary.innerHTML=FplTransferCard.html(p,c.people);
 target.append(summary);
 const temp=document.createElement('div');FplPlanView.render(p,c.people,temp);
 for(const id of ['transferResult','teamResult','chipResult']){const section=temp.querySelector('#'+id);if(section){if(id==='transferResult'){const details=document.createElement('details');details.className='decision-detail';const heading=document.createElement('summary');heading.textContent='Detaljeret original TS v3-plan og beslutningsværdi';details.append(heading,section);target.append(details);continue}if(id==='teamResult'){const note=document.createElement('p');note.textContent='Modellens anbefalede hold efter de foreslåede transfers. Dit faktiske hold i My Team er uændret.';section.prepend(note)}target.append(section)}}
}
function failed(e){target.replaceChildren();status.textContent='Not Available: '+e.message;const retry=document.getElementById('transfer-retry');retry.hidden=false;retry.onclick=()=>location.reload()}
try{await FplManagerClient.load();draw();FplTransferPreview.render();FplManagerClient.bind(()=>{draw();FplTransferPreview.render()});setInterval(async()=>{try{await FplManagerClient.load();draw();FplTransferPreview.render()}catch(e){failed(e)}},300000)}catch(e){failed(e)}
})();
