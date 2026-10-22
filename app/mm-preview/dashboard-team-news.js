'use strict';
(function(root){
 const SOURCE='https://fantasy.premierleague.com/api/bootstrap-static/',MAX_AGE=3600000;
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const clock=x=>Number.isFinite(Date.parse(x))?new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'}):'Ukendt tidspunkt';
 const labels={a:'Tilgængelig ifølge FPL',d:'Tvivlsom',i:'Skadet',s:'Suspenderet',u:'Utilgængelig',n:'Utilgængelig'};
 const order={i:0,s:1,u:2,n:2,d:3,a:4};
 const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
 const identity=p=>[p?.team,p?.position,p?.price_tenths??Math.round(p?.price*10),p?.status,p?.news||'',p?.news_added||null,p?.chance_of_playing_next_round??null,p?.chance_of_playing_this_round??null];
 function validate(news,now=Date.now()){
  if(news?.schema!=='fpl-dashboard-availability-v1'||news.source_url!==SOURCE||!Number.isInteger(news.next_gw)||news.next_gw<1||news.next_gw>38||!Number.isFinite(Date.parse(news.deadline))||Date.parse(news.deadline)<=now||!Array.isArray(news.players)||!news.players.length||new Set(news.players.map(p=>p.id)).size!==news.players.length)throw Error('Officiel statuskilde kan ikke verificeres');
  const at=Date.parse(news.observed_at);if(!Number.isFinite(at)||at>now+30000||now-at>MAX_AGE)throw Error('Spillerstatus er for gammel; afventer ny opdatering');
  for(const p of news.players){if(!Number.isInteger(p.id)||!labels[p.status]||!Number.isInteger(p.team)||!Number.isInteger(p.position)||!Number.isInteger(p.price_tenths)||(p.chance_of_playing_next_round!=null&&![0,25,50,75,100].includes(p.chance_of_playing_next_round))||(p.news_added&&(!Number.isFinite(Date.parse(p.news_added))||Date.parse(p.news_added)>at)))throw Error('Ugyldig officiel spillermelding');}
  return news;
 }
 async function load(fetcher=fetch,now=Date.now()){
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),15000);
  try{const r=await fetcher(new URL('../news/availability.json',location.href),{cache:'no-store',signal:abort.signal});if(!r.ok)throw Error('Spillerstatus kan ikke hentes');const n=await r.json(),{content_sha256,...body}=n;const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(body)))))].map(x=>x.toString(16).padStart(2,'0')).join('');if(hash!==content_sha256)throw Error('Checksumfejl i spillerstatus');return validate(n,now);}finally{clearTimeout(timer);}
 }
 function evaluate({news,official,forecast,state,plan,stateValid=false,usable=false,busy=false,error},now=Date.now()){
  let issue;try{validate(news,now);}catch(e){issue=error||e.message;}
  const latest=new Map((!issue?news?.players:[]).map(p=>[p.id,p])),baseline=new Map((official?.players||[]).map(p=>[p.id,p]));
  const rows=(state?.squad||[]).map(p=>{const fresh=latest.get(p.id),old=baseline.get(p.id);return {...fresh,id:p.id,name:fresh?.name||old?.web_name||'Ukendt spiller',verified:!!fresh,label:fresh?labels[fresh.status]:'Status kan ikke verificeres'};}).sort((a,b)=>(order[a.status]??-1)-(order[b.status]??-1)||a.name.localeCompare(b.name,'da'));
  const changedPlayers=!issue?news.players.filter(p=>JSON.stringify(identity(p))!==JSON.stringify(identity(baseline.get(p.id)))):[];
  const changed=!issue&&((news.players.length!==baseline.size)||changedPlayers.length>0);
  const owned=new Set((state?.squad||[]).map(p=>p.id)),named=state?changedPlayers.filter(p=>owned.has(p.id)):changedPlayers;
  const names=named.slice(0,3).map(p=>p.name||p.web_name||'spiller '+p.id).join(', ');
  const alignmentReason=issue||(news.next_gw!==forecast?.gws?.[0]?'Afventer opdaterede prognoser til næste gameweek.':changed?'Nye FPL-oplysninger'+(names?' om '+names+(named.length>3?' og '+(named.length-3)+' andre':''):' om spillere i transferberegningen')+'. Afventer prognoser, der tager højde for den nye status.':!usable?'Afventer opdaterede prognoser til næste gameweek.':'');
  const aligned=!issue&&!changed&&news.next_gw===forecast?.gws?.[0]&&usable;
  let phase,message;
  if(!state){phase='missing_team';message='Indlæs dit faktiske hold for at få personlige nyheder og næste GW’s forslag.';}
  else if(issue){phase='news_unavailable';message=issue;}
  else if(forecast?.gws?.[0]!==news.next_gw||(!usable&&!changed)){phase='waiting_forecast';message='Afventer et opdateret forecast til næste officielle GW.';}
  else if(state.gw!==news.next_gw||!stateValid){phase='update_state';message=typeof FplPlannerExperience==='undefined'?'Opdatér holdets oplysninger.':FplPlannerExperience.diagnose(state,forecast).join(' ');}
  else if(changed){phase='waiting_forecast';message=alignmentReason;}
  else if(Date.parse(state.observed_at)>Date.parse(forecast.data_asof)){phase='waiting_forecast';message='Dit hold er gemt efter prognosen. Afventer nyere prognoser; du skal ikke bekræfte holdet igen.';}
  else if(busy){phase='calculating';message='Næste GW’s forslag beregnes med dit aktuelle hold. Der udføres ingen transfers.';}
  else if(plan?.ts_ran&&plan.locked_model_active===false&&plan.forecast_sha256===forecast.forecast_sha256&&plan.gw===news.next_gw){phase='ready';message='Forslaget er klart til næste officielle GW og matcher det aktuelle forecast.';}
  else{phase='can_compute';message='Klar til at beregne næste GW’s forslag med dit gemte hold.';}
  const canCompute=aligned&&stateValid&&state?.gw===news?.next_gw&&Date.parse(state.observed_at)<=Date.parse(forecast?.data_asof)&&!busy;
  return {state,forecast,phase,message,aligned,alignmentReason,canCompute,planReady:phase==='ready',rows,issue,changed,gw:news?.next_gw??forecast?.gws?.[0],observed_at:news?.observed_at};
 }
 function row(p){return '<article class="team-news-item '+(p.status==='a'?'is-available':'is-flagged')+'" data-news-player="'+p.id+'"><div><a href="player.html?id='+p.id+'"><strong>'+esc(p.name)+'</strong></a><span class="team-news-status">'+esc(p.label)+'</span></div><p>'+esc(p.news||(!p.verified?'Seneste status mangler.':'Ingen aktuel FPL-melding.'))+'</p>'+(p.chance_of_playing_next_round!=null?'<small>FPL-tilgængelighed: '+p.chance_of_playing_next_round+' % · dette er ikke P(start).</small>':'')+'<small>Meldingens tidspunkt: '+clock(p.news_added)+'</small></article>';}
 function html(status,enabled=true){const urgent=status.rows.filter(p=>p.status!=='a'),others=status.rows.filter(p=>p.status==='a');return '<section class="panel dashboard-team-news" id="dashboard-team-news"><div class="team-news-heading"><div><h2>Mit hold · nyheder og status</h2><p>Kun spillerne på dit gemte hold · næste officielle GW '+esc(status.gw??'—')+'</p></div><button id="refresh-team-news" type="button">Opdatér status</button></div>'+(!status.rows.length?'<p>Indlæs dit gemte hold i My Team for at se dine spilleres status.</p>':'')+(status.issue?'<p role="status">'+esc(status.issue)+'</p>':'')+urgent.map(p=>row(p)+(typeof FplPlannerExperience==='undefined'?'':FplPlannerExperience.impact(p,status.state,status.forecast))).join('')+(others.length?'<details><summary>Øvrige '+others.length+' spillere · tilgængelige ifølge FPL</summary>'+others.map(row).join('')+'</details>':'')+'<div class="team-news-plan" data-plan-phase="'+status.phase+'"><h3>Næste forslag · GW '+esc(status.gw??'—')+'</h3><p role="status">'+esc(status.message)+'</p><label><input id="auto-team-plan" type="checkbox" '+(enabled?'checked':'')+'> Hold næste GW’s forslag opdateret automatisk</label><p><small>Genberegner, når dashboardet er åbent og nye verificerede data er klar. Dit faktiske hold ændres ikke.</small></p></div><p class="team-news-source">Kilde: <a href="'+SOURCE+'" target="_blank" rel="noopener">Officielle FPL-meldinger</a> · hentet '+clock(status.observed_at)+'. Status er ikke en bekræftet startopstilling.</p></section>';}
 function planMessage(status){return '<p class="notice">'+esc(status.message)+'</p>'+(status.canCompute?'<button id="compute" type="button">Beregn / opdatér næste GW’s forslag</button>':'<a href="'+(status.phase==='update_state'||status.phase==='missing_team'?'manager-state.html':'#dashboard')+'">'+(status.phase==='update_state'||status.phase==='missing_team'?'Opdatér mit hold':'Afventer nye modeldata')+'</a>')+'<div data-compute-feedback class="compute-feedback"></div><p id="compute-status" role="status" class="compute-technical"></p>';}
 function shouldRequest({status,enabled,busy,hasJob,signature,attempt,now=Date.now()}){return enabled&&status.canCompute&&!status.planReady&&!busy&&!hasJob&&(!attempt||attempt.signature!==signature||now-attempt.at>=600000);}
 function controller({get,compute,render,hash,hasJob,storage=localStorage,session=sessionStorage}){
  let news=null,error=null,pending=false;const preference='fpl-B-news-auto-plan-v1',attemptKey='fpl-B-news-plan-attempt-v1';
  const enabled=()=>{try{return storage.getItem(preference)!=='false';}catch{return false;}};
  const status=()=>root.FplTeamNews.evaluate({...get(),news,error});
  async function refresh(){try{news=await load();error=null;}catch(e){news=null;error=e.name==='AbortError'?'Spillerstatus kunne ikke hentes inden for tidsgrænsen.':e.message;}}
  function afterRender(){document.getElementById('auto-team-plan')?.addEventListener('change',e=>{storage.setItem(preference,String(e.target.checked));render();});document.getElementById('refresh-team-news')?.addEventListener('click',async()=>{await refresh();render();});
   if(pending||(location.hash&&location.hash!=='#dashboard'))return;
   pending=true;setTimeout(async()=>{try{if(location.hash&&location.hash!=='#dashboard')return;const context=get(),signature=await hash({forecast:context.forecast?.forecast_sha256,state:context.state});let attempt;try{attempt=JSON.parse(session.getItem(attemptKey));}catch{}if(shouldRequest({status:status(),enabled:enabled(),busy:context.busy,hasJob:!!hasJob(),signature,attempt})){session.setItem(attemptKey,JSON.stringify({signature,at:Date.now()}));await compute();}}finally{pending=false;}},1500);
  }
  return {refresh,status,html:()=>html(status(),enabled()),planMessage:()=>planMessage(status()),afterRender};
 }
 const api={validate,load,evaluate,html,planMessage,shouldRequest,controller,identity};root.FplTeamNews=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);

if(typeof FplLatestSnapshot!=='undefined')FplLatestSnapshot.installNews();
