'use strict';
// Presentation only: use the existing sealed forecast and verified FPL history.
(function(root){
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const val=(x,d=0)=>x===null||x===undefined||x===''||!Number.isFinite(Number(x))?'—':Number(x).toFixed(d);
 const clock=x=>new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen',dateStyle:'short',timeStyle:'short'});
 function table(labels,rows,cls){const wrap=el('div',undefined,'player-match-table '+cls),t=el('table'),head=el('thead'),hr=el('tr'),body=el('tbody');for(const label of labels){const th=el('th',label);th.scope='col';hr.append(th);}head.append(hr);for(const row of rows){const tr=el('tr');row.forEach((value,i)=>{const td=el('td');td.dataset.label=labels[i];if(value instanceof Node)td.append(value);else td.textContent=value;tr.append(td);});body.append(tr);}t.append(head,body);wrap.append(t);return wrap;}
 let history;
 function load(){if(!history)history=root.FplBExistingApp.history().catch(e=>{history=null;throw e});return history;}
 const inputAudits=new Map();
 function loadInputAudit(forecast){
  const seal=forecast.forecast_sha256;
  if(!inputAudits.has(seal))inputAudits.set(seal,(async()=>{
   const base=new URL('../input-audit/index.json',location.href),r=await fetch(base,{cache:'no-store'});
   if(!r.ok)throw Error('Audit index unavailable');const index=await r.json();
   if(index.schema!=='B-all-player-chain-audit-index-v2'||index.forecast_sha256!==seal)throw Error('Audit belongs to another forecast');
   const url=new URL(index.file,base);if(url.origin!==base.origin||!url.pathname.startsWith(base.pathname.slice(0,base.pathname.lastIndexOf('/')+1)))throw Error('Invalid audit path');
   const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error('Audit unavailable');const bytes=await response.arrayBuffer();
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
   if(digest!==index.sha256)throw Error('Audit checksum mismatch');const report=JSON.parse(new TextDecoder().decode(bytes));
   if(report.schema!=='B-all-player-chain-audit-v2'||report.forecast_sha256!==seal||report.players.length!==forecast.players.length)throw Error('Incomplete audit');
   return report;
  })().catch(e=>{inputAudits.delete(seal);throw e}));
  return inputAudits.get(seal);
 }
 function inputAuditPanel(player,data){
  const detail=el('details',undefined,'player-input-audit');detail.append(el('summary','Prognosens datagrundlag'));
  const body=el('div');body.append(el('p','Henter datakontrol for denne prognose …','prob-note'));detail.append(body);
  loadInputAudit(data.forecast).then(report=>{
   const p=report.players.find(x=>x.id===player.id&&x.player_uuid===player.player_uuid);if(!p)throw Error('Player audit missing');
   const rows=[
    ['Minutter og point',p.individual_numerical_checks_passed?'Afstemt mellem modellerne':'Der er fundet en afvigelse i modelkæden'],
    ['Udskiftninger og minutforløb',p.normal_match_timeline_verified===true?'Normal kamp verificeret: højst 5 indskiftninger. Fælles tidslinje er ikke verificeret ved udvisninger.':p.physical_team_minutes_verified===true?'Fælles tidslinje verificeret':p.physical_team_minutes_verified===false?'Normalgrænsen for udskiftninger overskrides i simuleringer':'Fælles tidslinje er ikke verificeret fra de tilgængelige data'],
    ['Belastning','De særskilte belastningsfelter bruger kun Premier League'],
    ['CL og pokal','Indgår i dele af rolle- og præstationsmodellen, men ikke i alle felter'],
    ['Trænerudtalelser','Indgår endnu ikke som et struktureret modelinput'],
    ['Sporbarhed',p.input_evidence_verified?'De aktuelle modelinput er gemt og verificeret':'De præcise modelinput kunne ikke efterkontrolleres'],
    ['Prognosekvalitet','Sandsynligheder og minutintervaller er ikke uafhængigt certificeret']
   ];
   body.replaceChildren(table(['Område','Datagrundlag'],rows,'player-input-audit-table'),el('p','Kontrollen gælder prognosen fra '+clock(report.data_asof)+'. FPL-registrerede minutter kan afvige fra den fysiske kampklokke. Afstemte beregninger er ikke en garanti for start, minutter eller point.','prob-note'));
   if(!report.technical_moment_contract_passed||report.published_selected_historical_evidence_matches===false)body.prepend(el('p','Datakontrollen har fundet en fejl i modelkæden eller dens kildedokumentation. Prognosen kræver gennemgang.','prob-note'));
   detail.dataset.forecast=report.forecast_sha256;detail.dataset.auditLoaded='true';
  }).catch(()=>{body.replaceChildren(el('p','Datakontrollen for denne prognose kunne ikke hentes. Dækningen er derfor ikke bekræftet.','prob-note'));detail.dataset.auditLoaded='false';});
  return detail;
 }
 let seasonReview;
 function seasonPanel(player,season){
  const detail=el('details',undefined,'player-model-season');detail.append(el('summary','Model mod faktiske resultater · fra GW6'));
  const body=el('div');detail.append(body);body.append(el('p','Åbn for at hente spillerens historiske prognoser og fejl.','prob-note'));
  detail.addEventListener('toggle',async()=>{if(!detail.open||detail.dataset.loaded)return;detail.dataset.loaded='loading';try{
   if(!seasonReview)seasonReview=fetch(new URL('../weekly-review/players.json',location.href),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Historik mangler');return r.json()}).catch(e=>{seasonReview=null;throw e});
   const report=await seasonReview;if(report.schema!=='fpl-player-season-review-v1'||report.season!==season)throw Error('Forkert format');const p=report.players.find(p=>p.id===player.id);if(!p)throw Error('Spiller mangler');
   const choice=el('select');choice.setAttribute('aria-label','Spillerens historiske modelserie');for(const[value,label]of [['backtest','Historisk B-backtest · genskabt nu'],['b','B · publiceret før deadline'],['original','Oprindelig model']]){const o=el('option',label);o.value=value;choice.append(o);}const content=el('div');body.replaceChildren(choice,content);
   function draw(){const weeks=p[{backtest:'backtest_weeks',b:'weeks',original:'original_weeks'}[choice.value]]||[];content.replaceChildren(el('p',choice.value==='backtest'?'Genskabt fra historiske input; senere valgte modelregler. Ikke en original prognose eller uafhængig test.':'Arkiverede prognoser publiceret før deadline.','prob-note'),table(['GW','P(start)','xM','Min','xM − min','xP','P','xP − P'],weeks.filter(w=>w.gw>=6).map(w=>['GW '+w.gw,w.p_start.map(x=>val(100*x)+' %').join(' / '),val(w.expected_minutes,1),val(w.actual_minutes,0),val(w.final?w.expected_minutes-w.actual_minutes:null,1),val(w.xp,2),val(w.actual_points,0),val(w.final?w.xp-w.actual_points:null,2)]),'player-model-errors'),el('p','Startchance → forventede minutter → forventede point. Positiv pointforskel betyder overvurdering. Gamle mål-/assistkomponenter og trænerudtalelser er ikke komplet arkiveret og erstattes ikke med nutidige oplysninger.','prob-note'));if(!weeks.some(w=>w.gw>=6))content.append(el('p','Ingen arkiveret prognose i denne serie.'))}
   choice.onchange=draw;draw();detail.dataset.loaded='true';
  }catch(e){body.replaceChildren(el('p','Sæsonhistorikken kunne ikke hentes. Ingen manglende resultater vises som nul.','prob-note'));delete detail.dataset.loaded;}});return detail;
 }
 function create(player,data,options={}){
  const box=el('div',undefined,'player-match-overview'+(options.compact?' is-compact':'')),summary=el('div',undefined,'player-match-summary');
  for(const[label,value]of [['Næste GW · xP',val(player.weeks[0]?.xpts,2)],['6 GW · xP',val(player.weeks.reduce((s,w)=>s+w.xpts,0),2)],['Næste GW · xMin',val(player.weeks[0]?.xmins,1)]]){const c=el('div');c.append(el('span',label),el('strong',value));summary.append(c);}
  const future=el('section',undefined,'player-next-matches'),past=el('section',undefined,'player-past-matches');
  const nav=el('nav',undefined,'player-match-nav');nav.setAttribute('aria-label','Spillerkortets kampoversigter');for(const[label,target]of [['Næste kampe',future],['Tidligere kampe',past]]){const button=el('button',label);button.type='button';button.onclick=()=>target.scrollIntoView({block:'start',behavior:'smooth'});nav.append(button);}
  box.append(summary);const review=el('a','Modellens sæsonresultater for '+player.name+' →','player-season-review-link');review.href='weekly-review.html?player='+player.id+'#player-review';box.append(review);if(root.FplPlayerTextContext)box.append(root.FplPlayerTextContext.liveStatus(player));if(!options.compact)box.append(nav);
  const archive=el('a','Tidligere sæsoner · spillerens kampstatistik','player-history-link');archive.href='history-classic.html?player='+encodeURIComponent(player.player_uuid);box.append(archive);
  box.append(future,inputAuditPanel(player,data),seasonPanel(player,data.forecast.season));if(root.FplPlayerTextContext)box.append(root.FplPlayerTextContext.create(player,options.compact,{includeLive:false}));box.append(past);past.append(el('h3','Tidligere kampe'),el('p','Henter verificeret kamphistorik …','prob-note'));
  function drawFuture(h){
   future.replaceChildren(el('h3',options.compact?'Næste 3 GW · modelprognose':'Næste kampe · modelprognose'));
   const matches=new Map((h?.historical_fixtures?.fixtures||[]).map(f=>[f.id,f])),teams=h?.historical_catalogue?.teams||{};
   const rows=(options.compact?player.weeks.slice(0,3):player.weeks).flatMap(w=>w.fixtures.length?w.fixtures.map(f=>{
    const match=matches.get(Number(f.fixture_uuid.split('-').pop())),home=match?.home===player.team_id;
    const other=data.forecast.players.find(p=>p.team_id!==player.team_id&&p.weeks.some(w=>w.fixtures.some(x=>x.fixture_uuid===f.fixture_uuid)));
    const name=match?(teams[home?match.away:match.home]?.name||other?.team):other?.team;
    const opponent=el('span',undefined,'player-match-opponent');opponent.append(el('strong',(name||'Modstander afventer')+(match?(home?' (H)':' (U)'):'')),el('small',clock(f.kickoff)));
    const m=data.mm.get(f.fixture_uuid+'|'+player.player_uuid),start=m?.p_start??f.p_start??f.distribution?.p_start;
    const goals=f.components?.goal_points,assists=f.components?.assist_points;
    return ['GW '+w.gw,opponent,val(f.xpts,2),val(f.xmins,1),val(Number.isFinite(goals)?goals/({1:10,2:6,3:5,4:4}[player.position]):null,2),val(Number.isFinite(assists)?assists/3:null,2),Number.isFinite(start)?val(start*100)+' %':'—'];
   }):[['GW '+w.gw,'Ingen kamp','—','—','—','—','—']]);
   future.append(table(['GW','Kamp','xP','xMin','xMål','xAssist','Start'],rows,'player-fixtures-future'),el('p','xMål og xAssist er modellens forventede mål og assists, afledt af PM-pointkomponenterne. xG og xA fra afsluttede kampe vises nedenfor. Prognose: '+clock(data.forecast.data_asof)+'.','prob-note'));
   const splitRows=(options.compact?player.weeks.slice(0,3):player.weeks).flatMap(w=>w.fixtures.filter(f=>f.penalty).map(f=>['GW '+w.gw,val(f.penalty.expected_nonpenalty_goals,2),val(f.penalty.expected_penalty_goals,2),val((f.penalty.team_simulated_p_at_least_one??f.penalty.team_p_at_least_one)*100,1)+' %',val(f.penalty.p_takes_penalty*100,1)+' %']));
   if(splitRows.length){const detail=el('details'),title=el('summary','Almindelige mål og straffespark');detail.append(title,table(['GW','xMål uden straffe','xStraffemål','Holdet får straffe','Spilleren tager straffe'],splitRows,'player-fixtures-penalty'),el('p','Målfaren beregnes adskilt. Procenterne gælder mindst ét straffespark og beregnes fra de samme 400 kampsimuleringer som xP. Spillerens chance inkluderer spilletid og skyttehierarki; små stikprøver giver udsving.','prob-note'));future.append(detail);}
  }
  drawFuture(null);
  load().then(h=>{
   if(h.observed_at!==h.historical_catalogue?.fetched_at||!Array.isArray(h.match_rows))throw Error('Historikkilderne stemmer ikke overens');
   drawFuture(h);past.replaceChildren(el('h3','Tidligere kampe · faktiske tal'));
   const matches=new Map(h.historical_fixtures.fixtures.map(f=>[f.id,f])),teams=h.historical_catalogue.teams;
   const rows=h.match_rows.filter(r=>r.player_id===player.id).sort((a,b)=>String(matches.get(b.fixture_id)?.kickoff||'').localeCompare(String(matches.get(a.fixture_id)?.kickoff||''))||b.gw-a.gw).map(r=>{
    const match=matches.get(r.fixture_id),home=typeof r.was_home==='boolean'?r.was_home:match?.home===r.team_id;
    const name=match?teams[home?match.away:match.home]?.name:null;
    const link=el('a',(name||'Kamp '+r.fixture_id)+(match?(home?' (H)':' (U)'):'')+(r.provisional?' · foreløbig':''));link.href='fixtures-classic.html?gw='+r.gw;
    const opponent=el('span',undefined,'player-match-opponent');opponent.append(link);if(match)opponent.append(el('small',clock(match.kickoff)+' · '+val(home?match.home_score:match.away_score)+'–'+val(home?match.away_score:match.home_score)));
    if(r.stats?.minutes===0&&root.FplPlayerMatchContext){const absence=el('small','Årsag til 0 minutter afventer …','match-context-inline-absence');opponent.append(absence);root.FplPlayerMatchContext.load().then(data=>{const context=data.rows.find(x=>x.player_id===player.id&&x.competition==='prem'&&x.fpl_fixture_id===r.fixture_id);if(context&&context.minutes>0){absence.textContent='Kilderne er uenige om spilletiden; årsag ikke afklaret.';}else absence.replaceChildren(root.FplPlayerMatchContext.reason(context));}).catch(()=>{absence.textContent='Årsag til fravær ikke dokumenteret';});}
    return ['GW '+r.gw,opponent,val(r.stats?.minutes),val(r.total_points??r.stats?.total_points),val(r.stats?.goals_scored),val(r.stats?.assists),val(r.stats?.expected_goals,2),val(r.stats?.expected_assists,2),val(r.stats?.red_cards)];
   });
   if(!rows.length)past.append(el('p','Ingen verificerede tidligere kampe for denne spiller.','prob-note'));
   else{const count=options.compact?3:6;past.append(table(['GW','Kamp','Min','Point','Mål','Assists','xG','xA','Røde'],rows.slice(0,count),'player-fixtures-past'));if(rows.length>count){const more=el('details'),s=el('summary','Vis '+(rows.length-count)+' ældre kampe');more.append(s,table(['GW','Kamp','Min','Point','Mål','Assists','xG','xA','Røde'],rows.slice(count),'player-fixtures-past'));past.append(more);}}
   if(root.FplPlayerMatchContext)box.append(root.FplPlayerMatchContext.create(player,h,options.compact));
   past.append(el('p','Resultatet er set fra spillerens hold. Officielle FPL-kampdata · hentet '+clock(h.observed_at)+'. — betyder, at tallet ikke findes pr. kamp; GW-totaler fordeles ikke kunstigt på dobbeltkampe.','prob-note'));
  }).catch(()=>{past.replaceChildren(el('h3','Tidligere kampe'),el('p','Kamphistorikken kunne ikke hentes. Prognosen ovenfor er stadig tilgængelig. Prøv at åbne kortet igen.','prob-note'));});
  return box;
 }
 root.FplPlayerMatchCard={create};
})(window);
