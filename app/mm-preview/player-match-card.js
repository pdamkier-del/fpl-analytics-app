'use strict';
// Presentation only: use the existing sealed forecast and verified FPL history.
(function(root){
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const val=(x,d=0)=>x===null||x===undefined||x===''||!Number.isFinite(Number(x))?'—':Number(x).toFixed(d);
 const clock=x=>new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen',dateStyle:'short',timeStyle:'short'});
 function table(labels,rows,cls){const wrap=el('div',undefined,'player-match-table '+cls),t=el('table'),head=el('thead'),hr=el('tr'),body=el('tbody');for(const label of labels){const th=el('th',label);th.scope='col';hr.append(th);}head.append(hr);for(const row of rows){const tr=el('tr');row.forEach((value,i)=>{const td=el('td');td.dataset.label=labels[i];if(value instanceof Node)td.append(value);else td.textContent=value;tr.append(td);});body.append(tr);}t.append(head,body);wrap.append(t);return wrap;}
 let history;
 function load(){if(!history)history=root.FplBExistingApp.history().catch(e=>{history=null;throw e});return history;}
 function create(player,data,options={}){
  const box=el('div',undefined,'player-match-overview'+(options.compact?' is-compact':'')),summary=el('div',undefined,'player-match-summary');
  for(const[label,value]of [['Næste GW · xP',val(player.weeks[0]?.xpts,2)],['6 GW · xP',val(player.weeks.reduce((s,w)=>s+w.xpts,0),2)],['Næste GW · xMin',val(player.weeks[0]?.xmins,1)]]){const c=el('div');c.append(el('span',label),el('strong',value));summary.append(c);}
  const future=el('section',undefined,'player-next-matches'),past=el('section',undefined,'player-past-matches');
  const nav=el('nav',undefined,'player-match-nav');nav.setAttribute('aria-label','Spillerkortets kampoversigter');for(const[label,target]of [['Næste kampe',future],['Tidligere kampe',past]]){const button=el('button',label);button.type='button';button.onclick=()=>target.scrollIntoView({block:'start',behavior:'smooth'});nav.append(button);}
  box.append(summary);if(!options.compact)box.append(nav);
  const archive=el('a','Tidligere sæsoner · spillerens kampstatistik','player-history-link');archive.href='history-classic.html?player='+encodeURIComponent(player.player_uuid);box.append(archive);
  box.append(future,past);past.append(el('h3','Tidligere kampe'),el('p','Henter verificeret kamphistorik …','prob-note'));
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
    return ['GW '+r.gw,opponent,val(r.stats?.minutes),val(r.total_points??r.stats?.total_points),val(r.stats?.goals_scored),val(r.stats?.assists),val(r.stats?.expected_goals,2),val(r.stats?.expected_assists,2)];
   });
   if(!rows.length)past.append(el('p','Ingen verificerede tidligere kampe for denne spiller.','prob-note'));
   else{const count=options.compact?3:6;past.append(table(['GW','Kamp','Min','Point','Mål','Assists','xG','xA'],rows.slice(0,count),'player-fixtures-past'));if(rows.length>count){const more=el('details'),s=el('summary','Vis '+(rows.length-count)+' ældre kampe');more.append(s,table(['GW','Kamp','Min','Point','Mål','Assists','xG','xA'],rows.slice(count),'player-fixtures-past'));past.append(more);}}
   if(root.FplPlayerMatchContext)box.append(root.FplPlayerMatchContext.create(player,h,options.compact));
   past.append(el('p','Resultatet er set fra spillerens hold. Officielle FPL-kampdata · hentet '+clock(h.observed_at)+'. — betyder, at tallet ikke findes pr. kamp; GW-totaler fordeles ikke kunstigt på dobbeltkampe.','prob-note'));
  }).catch(()=>{past.replaceChildren(el('h3','Tidligere kampe'),el('p','Kamphistorikken kunne ikke hentes. Prognosen ovenfor er stadig tilgængelig. Prøv at åbne kortet igen.','prob-note'));});
  return box;
 }
 root.FplPlayerMatchCard={create};
})(window);
