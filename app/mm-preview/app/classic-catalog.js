'use strict';
(()=>{
const $=id=>document.getElementById(id),D=FplCatalogData,esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=2)=>D.number(v)===null?'Not Available':Number(v).toFixed(d),pct=v=>D.number(v)===null?'Not Available':Math.round(v*100)+'%';
const clubPage=!!$('clubSelect'),query=new URLSearchParams(location.search);let official,forecast,fixtures,expectations,lineups,historyData,usable=false,mode=['forecast','recent'].includes(query.get('mode'))?query.get('mode'):'stats',horizon=[1,3,6].includes(Number(query.get('horizon')))?Number(query.get('horizon')):6;
let sort={stats:{key:'points',dir:-1},forecast:{key:'xp',dir:-1},clubs:{key:'name',dir:1},recent:{key:'recentPoints',dir:-1}};
let clubView='history',clubHistoryWindow=0,clubForecastWindow=6;let club=Number(query.get('team'))||null;let recentCount=[0,1,3,6].includes(Number(query.get('recent')))?Number(query.get('recent')):3;
const status={a:'Available',d:'Doubtful',i:'Injured',s:'Suspended',u:'Unavailable',n:'Unavailable'};
const base=[['name','Player'],['club','Club'],['positionName','Pos'],['price','Price'],['status','Status']];
const actual=[...base,['points','FPL points'],['minutes','Minutes'],['starts','Starts'],['goals','Goals'],['xg','xG'],['assists','Assists'],['xa','xA'],['xgi','xGI'],['cs','Clean sheets'],['xgc','xGC'],['defcon','DefCon'],['saves','Saves'],['bonus','Bonus'],['bps','BPS'],['selected','Selected %']];
const recentColumns=[...base,['lastGwPoints','Seneste GW-point'],['lastPoints','Point pr. GW'],['recentPoints','Point i perioden'],['recentMinutes','Minutter'],['recentGoals','Mål'],['recentAssists','Assists'],['recentXg','xG'],['recentXa','xA'],['recentBonus','Bonus'],['recentBps','BPS'],['recentDefcon','DefCon']];
const predicted=[...base,['xp','xP'],['xmins','xMins'],['pstart','Avg P(start)'],['pplay','P(spiller) næste GW'],['value','xP / £m'],['goalPoints','Goal xPts'],['assistPoints','Assist xPts'],['bonusPoints','Bonus xPts']];
const playerSortChoices={
  stats:[['points','FPL-point'],['xg','xG'],['xa','xA'],['xgi','xG + xA'],['goals','Mål'],['assists','Assists'],['minutes','Spilleminutter'],['cs','Clean sheets'],['bonus','Bonuspoint'],['bps','BPS'],['price','Pris']],
  forecast:[['xp','Forventede FPL-point (xP)'],['xmins','Forventede minutter (xM)'],['pstart','Startchance'],['pplay','Spillechance'],['value','xP pr. £m'],['goalPoints','Forventede målpoint'],['assistPoints','Forventede assistpoint'],['bonusPoints','Forventede bonuspoint']],
  recent:[['recentPoints','FPL-point i perioden'],['recentXg','xG i perioden'],['recentXa','xA i perioden'],['recentGoals','Mål i perioden'],['recentAssists','Assists i perioden'],['recentMinutes','Minutter i perioden'],['recentBonus','Bonus i perioden']],
};
const playerSortDefault={stats:'points',forecast:'xp',recent:'recentPoints'};
function syncPlayerSort(){
  const select=$('playerSort');if(!select)return;
  const choices=playerSortChoices[mode]||playerSortChoices.stats;
  const current=sort[mode]?.key;
  const key=choices.some(([id])=>id===current)?current:playerSortDefault[mode];
  if(sort[mode].key!==key){sort[mode].key=key;sort[mode].dir=-1;}
  select.innerHTML=choices.map(([id,label])=>'<option value="'+id+'">'+esc(label)+'</option>').join('');
  select.value=key;
}
const clubSortChoices=[
  ['name:asc','Klubnavn A–Å'],
  ['points:desc','Flest ligapoint'],['pointsPerGame:desc','Flest point pr. kamp'],
  ['gf:desc','Flest scorede mål'],['gfPerGame:desc','Flest mål pr. kamp'],
  ['ga:desc','Flest indkasserede mål'],['ga:asc','Færrest indkasserede mål'],
  ['gaPerGame:desc','Flest indkasserede mål pr. kamp'],['gaPerGame:asc','Færrest indkasserede mål pr. kamp'],
  ['gd:desc','Bedste målforskel'],['gd:asc','Dårligste målforskel'],
  ['cs:desc','Flest clean sheets'],['cleanSheetPct:desc','Højeste clean sheet-andel'],
  ['wins:desc','Flest sejre'],['draws:desc','Flest uafgjorte'],['losses:desc','Flest nederlag'],
  ['xg:desc','Højest forventet xG · næste 6 GW'],
  ['xga:desc','Højest forventet xGA · næste 6 GW'],
  ['xga:asc','Lavest forventet xGA · næste 6 GW'],
  ['xgd:desc','Bedste forventede xG-forskel · næste 6 GW'],
  ['xgPerFixture:desc','Højest forventet xG pr. kamp'],
  ['xgaPerFixture:desc','Højest forventet xGA pr. kamp'],
  ['xgaPerFixture:asc','Lavest forventet xGA pr. kamp'],
  ['players:desc','Flest registrerede spillere']
];
function syncClubSort(){
  const select=$('clubSort');if(!select)return;
  const historyKeys=new Set(['name','points','pointsPerGame','gf','gfPerGame','ga','gaPerGame','gd','cs','cleanSheetPct','wins','draws','losses','players']);
  const choices=clubSortChoices.filter(([value])=>clubView==='history'?historyKeys.has(value.split(':')[0]):!historyKeys.has(value.split(':')[0])||value.startsWith('name:'));
  const selected=sort.clubs.key+':'+(sort.clubs.dir<0?'desc':'asc');
  if(!choices.some(([value])=>value===selected))sort.clubs=clubView==='history'?{key:'points',dir:-1}:{key:'xg',dir:-1};
  select.innerHTML=choices.map(([value,label])=>'<option value="'+value+'">'+esc(label)+'</option>').join('');
  select.value=sort.clubs.key+':'+(sort.clubs.dir<0?'desc':'asc');
}

const badge=t=>Number(t?.code)>0?'<img class="catalog-crest" loading="lazy" alt="" src="https://resources.premierleague.com/premierleague/badges/70/t'+Number(t.code)+'.png">':'';
const face=p=>Number(p.code)>0?'<img class="catalog-face" loading="lazy" alt="" onerror="this.hidden=true" src="https://resources.premierleague.com/premierleague25/photos/players/110x140/'+Number(p.code)+'.png">':'';
const link=p=>'<a class="player" href="player.html?id='+p.id+'">'+face(p)+'<span>'+esc(p.name)+'</span></a>';
function setQuery(){const u=new URL(location.href);for(const [k,v] of Object.entries({team:club||'',mode,horizon,recent:recentCount})){if(v)u.searchParams.set(k,v);else u.searchParams.delete(k)}history.replaceState(null,'',u)}
function bindTable(table,cols,rows,type){const state=sort[type],head=table.createTHead();head.innerHTML='<tr>'+cols.map(([key,label])=>key==='lastPoints'?'<th scope="col">'+esc(label)+'</th>':'<th scope="col" aria-sort="'+(state.key===key?(state.dir<0?'descending':'ascending'):'none')+'"><button type="button" data-sort="'+key+'">'+esc(label)+(state.key===key?(state.dir<0?' ▼':' ▲'):' ⇅')+'</button></th>').join('')+'</tr>';const body=table.tBodies[0]||table.createTBody();rows.sort((a,b)=>D.compare(a,b,state.key,state.dir));body.innerHTML=rows.map(p=>'<tr>'+cols.map(([key])=>'<td>'+cell(p,key,type)+'</td>').join('')+'</tr>').join('')||'<tr><td colspan="'+cols.length+'">Ingen resultater.</td></tr>';head.querySelectorAll('button').forEach(b=>b.onclick=()=>{const key=b.dataset.sort;state.dir=state.key===key?-state.dir:(['name','club','positionName','status'].includes(key)?1:-1);state.key=key;render()})}
function cell(p,key,type){if(type==='clubs'&&key==='name')return '<a class="player" href="clubs-classic.html?team='+p.id+'">'+badge(p)+'<span>'+esc(p.name)+'</span></a>';if(key==='name')return link(p);if(key==='club')return '<a href="clubs-classic.html?team='+p.team+'">'+esc(p.club)+'</a>';if(key==='positionName')return '<span class="pos">'+esc(p.positionName)+'</span>';if(key==='status')return '<span class="status '+(p.status==='a'?'available':'doubtful')+'">'+esc(status[p.status]||'Not Available')+'</span>';if(key==='lastPoints')return esc(p[key]||'Not Available');if(key==='price')return D.number(p.price)===null?'Not Available':'£'+num(p.price,1);if(key==='pstart'||key==='pplay')return pct(p[key]);return num(p[key],key.startsWith('gwPoints')?0:['points','minutes','starts','goals','assists','cs','defcon','saves','bonus','bps','players','played','gf','ga','lastGwPoints','recentPoints','recentMinutes','recentGoals','recentAssists','recentBonus','recentBps','recentDefcon'].includes(key)?0:2)}
function list(q,teamFilter){let xs=D.players(official,forecast,usable,horizon);const text=(q||'').toLocaleLowerCase('da');return xs.filter(p=>(!teamFilter||p.team===teamFilter)&&(!text||(p.name+' '+p.first_name+' '+p.second_name+' '+p.club).toLocaleLowerCase('da').includes(text)))}
function playerPage(){syncPlayerSort();let xs=list($('search').value,Number($('clubFilter').value));const recentGws=mode==='recent'?(historyData?.available_gws||historyData?.completed_gws||[]).slice(-recentCount).reverse():[];const columns=recentColumns.filter(([key])=>key!=='lastPoints');columns.splice(base.length+1,0,...recentGws.map(g=>['gwPoints'+g,'GW '+g+' point']));if(mode==='recent')xs=xs.map(p=>{const r=FplMatchData.recent(historyData,official,p.id,recentCount),t=r?.totals;return {...p,...Object.fromEntries((r?.gws||[]).map((g,i)=>['gwPoints'+g,D.number(r.rows[i]?.stats?.total_points)])),lastPoints:r?.lastPoints,lastGwPoints:D.number(r?.rows?.[0]?.stats?.total_points),recentPoints:t?.total_points??null,recentMinutes:t?.minutes??null,recentGoals:t?.goals_scored??null,recentAssists:t?.assists??null,recentXg:t?.expected_goals??null,recentXa:t?.expected_assists??null,recentBonus:t?.bonus??null,recentBps:t?.bps??null,recentDefcon:t?.defensive_contribution??null}});const position=$('posFilter').value,st=$('statusFilter').value,max=Number($('priceFilter').value);xs=xs.filter(p=>(!position||p.positionName===position)&&(!st||status[p.status]===st)&&(max===99||D.number(p.price)!==null&&p.price<=max));$('statsPanel').classList.toggle('active',mode!=='forecast');$('forecastPanel').classList.toggle('active',mode==='forecast');if($('recentControls'))$('recentControls').hidden=mode!=='recent';$('horizonControls').style.display=mode==='forecast'?'flex':'none';document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));document.querySelectorAll('[data-h]').forEach(b=>b.classList.toggle('active',Number(b.dataset.h)===horizon));bindTable($(mode==='forecast'?'forecastTable':'statsTable'),mode==='recent'?columns:mode==='stats'?actual:predicted,xs,mode);$('rankSummary').innerHTML='<div class="card"><div class="card-label">Spillere</div><div class="card-value">'+xs.length+'</div><div class="card-note">af '+official.players.length+'</div></div><div class="card"><div class="card-label">Periode</div><div class="card-value">'+(mode==='recent'?(recentCount?'Seneste '+recentCount+' GW':'Alle tilgængelige GW'):mode==='stats'?'Sæsonstatistik':horizon+' GW')+'</div><div class="card-note">'+(mode==='recent'?'Officielle GW med afsluttede kampe: '+((historyData?.available_gws||historyData?.completed_gws)?.slice(-recentCount).join(', ')||'Not Available'):mode==='stats'?'Officielle FPL-totaler':'GW '+forecast?.gws?.slice(0,horizon).join(', '))+'</div></div>';$('podium').innerHTML='';const help=$('statsPanel').querySelector('.table-help');if(help)help.textContent=mode==='recent'?'Faktiske point og statistik i den valgte periode. Nye spillere eller manglende afsluttede kampe viser Not Available. Klik på en numerisk kolonne for stigende/faldende sortering.':'Officielle sæsontotaler ved det viste hentetidspunkt. Klik på en kolonne for stigende/faldende sortering.';setQuery()}
function fixtureCards(id,container){const xs=fixtures.fixtures.filter(f=>f.home===id||f.away===id).sort((a,b)=>(a.gw??99)-(b.gw??99)||String(a.kickoff).localeCompare(String(b.kickoff)));container.innerHTML=xs.map(f=>{const home=f.home===id,other=official.teams[home?f.away:f.home],exp=usable&&expectations?.cutoff===forecast.data_asof?expectations.fixtures.find(x=>x.id===f.id):null;return '<div class="fixture-card-v2"><div class="fixture-card-top">GW '+esc(f.gw??'Not Available')+' · '+(home?'Hjemme':'Ude')+' · FDR '+esc((home?f.difficulty_home:f.difficulty_away)??'Not Available')+'</div><div class="fixture-teams">'+badge(other)+'<strong>'+esc(other?.name||'Not Available')+'</strong></div><p>'+esc(f.kickoff?new Date(f.kickoff).toLocaleString('da-DK'):'Tidspunkt: Not Available')+'</p><p>'+(f.finished?'Resultat '+esc(f.home_score??'Not Available')+'–'+esc(f.away_score??'Not Available'):'Forventede mål '+num(home?exp?.home_xg:exp?.away_xg)+' · imod '+num(home?exp?.away_xg:exp?.home_xg))+'</p>'+FplMatchData.view(historyData,official,fixtures).fixtureDetails(f)+'</div>'}).join('')}
function clubPageRender(){
  syncClubSort();
  $('clubHistoryMode').setAttribute('aria-pressed',String(clubView==='history'));
  $('clubForecastMode').setAttribute('aria-pressed',String(clubView==='forecast'));
  $('clubHistoryWindowLabel').hidden=clubView!=='history';
  $('clubForecastWindowLabel').hidden=clubView!=='forecast';
  $('clubsTable').parentElement.hidden=!!club;
  $('clubSearch').hidden=!!club;
  const q=$('clubSearch').value.toLocaleLowerCase('da');
  const historyCols=[['name','Klub'],['played','Kampe'],['points','Point'],['pointsPerGame','Point/kamp'],['gf','Mål'],['ga','Indkasserede'],['gfPerGame','Mål/kamp'],['gaPerGame','Indk./kamp'],['gd','Målforskel'],['cs','Clean sheets'],['cleanSheetPct','CS %'],['wins','Sejre'],['draws','Uafgjorte'],['losses','Nederlag']];
  const forecastCols=[['name','Klub'],['expectedMatches','Kampe'],['xg','Forventede mål (xG)'],['xga','Forventede mål imod (xGA)'],['xgd','xG-forskel'],['xgPerFixture','xG/kamp'],['xgaPerFixture','xGA/kamp']];
  const cols=clubView==='forecast'?forecastCols:historyCols;
  const rows=D.clubs(official,fixtures,forecast,expectations,usable,clubForecastWindow,clubHistoryWindow)
    .filter(t=>(t.name+' '+t.short_name).toLocaleLowerCase('da').includes(q));
  bindTable($('clubsTable'),cols,rows,'clubs');
const t=official.teams[club];$('clubDetails').hidden=!t;if(!t)return;$('crest').innerHTML=badge(t);$('clubName').textContent=t.name;$('crumb').textContent='Clubs / '+t.name;$('modelStamp').textContent='vFinal diagnostisk · cutoff '+forecast?.data_asof;$('nextFix').textContent='Officielle trupper · '+official.fetched_at;const xi=D.clubLineup(official,forecast,lineups,usable,club);
const card=p=>'<a class="player-node catalog-node" href="player.html?id='+p.id+'">'+face(p)+'<strong>'+esc(p.name)+'</strong><span>'+num(p.xp)+' xP</span><small><strong>'+pct(p.nextStart)+'</strong> P(start)</small><small>'+esc(p.role==='UNKNOWN'?p.positionName:p.role)+(p.status!=='a'?' · '+esc(status[p.status]||'Not Available'):'')+'</small></a>';
$('formationBadge').textContent=xi?.formation||'Not Available';$('lineupSub').textContent=xi?'Individuel MM B · forventet XI i næste kamp · GW '+xi.gw+' · '+new Date(xi.kickoff).toLocaleString('da-DK'):'Not Available: en verificeret MM-opstilling til dette forecast mangler.';
$('xiMinutes').textContent=num(xi?D.sum(xi.layers.flat().map(p=>p.xmins)):null,0);$('uncertainty').textContent='Not Available';$('roleBattles').textContent='XI og roller kommer direkte fra den låste MM. P(start) er modellens startchance, ikke en bekræftet opstilling. De øvrige spillere er ikke valgt i model-XI; officiel kampbænk er endnu ikke kendt.';
$('clubRoleCandidates').innerHTML=FplRolesView.battles(xi);
$('pitch').innerHTML=xi?xi.layers.map(layer=>'<div class="catalog-position"><div class="catalog-line">'+layer.map(card).join('')+'</div></div>').join(''):'<p class="catalog-position">Not Available · aktuelt MM-XI mangler.</p>';
$('clubBench').innerHTML=xi?xi.bench.map(card).join('')||'<p>Ingen øvrige tilgængelige spillere.</p>':'<p>Not Available</p>';
$('clubUnavailable').innerHTML=xi?xi.unavailable.map(card).join('')||'<p>Ingen utilgængelige spillere i prognosen.</p>':'<p>Not Available</p>';bindTable($('forecastTable'),predicted,list($('forecastSearch').value,club),'forecast');bindTable($('statsTable'),actual,list($('statsSearch').value,club),'stats');$('forecastSummary').textContent='Original vFinal · '+horizon+' GW · P(start) er gennemsnit af enkeltkampe; ved blank/dobbelt-GW: Not Available.';fixtureCards(club,$('fixtureBody'));setQuery()}
function render(){if(!official)return;if(clubPage)clubPageRender();else playerPage();document.querySelectorAll('[data-h]').forEach(b=>b.classList.toggle('active',Number(b.dataset.h)===horizon));}
async function get(name,optional=false){const c=new AbortController(),timer=setTimeout(()=>c.abort(),45000);try{const r=await fetch(name,{cache:'no-store',signal:c.signal});if(!r.ok)throw Error(name+' HTTP '+r.status);return await r.json()}catch(e){if(optional)return null;throw e}finally{clearTimeout(timer)}}
async function load(){try{const [o,f,fx,ex,xi,hist]=await Promise.all([get('current-players.json'),get('vfinal-diagnostic.json',true),get('live-fixtures.json'),get('fixture-expectations.json',true),get('club-lineups.json',true),get('match-results.json',true)]);if(o.snapshot_sha256!==fx.snapshot_sha256)throw Error('Spillere og kampe tilhører forskellige opdateringer. Prøv igen.');official=o;fixtures=fx;forecast=f;expectations=ex;lineups=xi;historyData=hist;const check=FplForecastWindow.check(f,o);usable=f?.model==='B-MM-PM-TS-v1'&&f.locked_model_active===false&&check.usable;const message=(usable?check.reason:'Not Available: aktuelt originalt forecast mangler eller er udløbet.')+' · Forecast-cutoff '+(f?.data_asof||'Not Available')+' · Officielle data '+o.fetched_at; $('catalogStatus').textContent=message;const select=$(clubPage?'clubSelect':'clubFilter'),old=select.value;select.innerHTML='<option value="">Alle klubber</option>'+Object.entries(o.teams).sort((a,b)=>a[1].name.localeCompare(b[1].name,'da')).map(([id,t])=>'<option value="'+id+'">'+esc(t.name)+'</option>').join('');select.value=old||String(club||'');if(clubPage)club=Number(select.value)||null;render()}catch(e){$('catalogStatus').textContent='Data kunne ikke indlæses: '+(e.name==='AbortError'?'timeout':e.message)+'. Dit gemte hold er ikke ændret.';usable=false;if(official)render()}}
$('catalogRetry').onclick=load;
if(clubPage){
  $('clubHistoryMode').onclick=()=>{clubView='history';render()};
  $('clubForecastMode').onclick=()=>{clubView='forecast';render()};
  $('clubHistoryWindow').onchange=event=>{clubHistoryWindow=Number(event.target.value);render()};
  $('clubForecastWindow').onchange=event=>{clubForecastWindow=Number(event.target.value);render()};
  $('clubSort')?.addEventListener('change',event=>{const [key,order]=String(event.target.value).split(':');if(!clubSortChoices.some(([value])=>value===key+':'+order))return;sort.clubs={key,dir:order==='asc'?1:-1};render()});$('clubSelect').setAttribute('aria-label','Vælg klub');$('clubSelect').onchange=e=>{club=Number(e.target.value)||null;render()};['clubSearch','forecastSearch','statsSearch'].forEach(id=>$(id).oninput=render);document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('#clubDetails .view').forEach(x=>x.classList.toggle('active',x.id===b.dataset.view))});}else{$('playerSort')?.addEventListener('change',event=>{const key=event.target.value;if(!playerSortChoices[mode]?.some(([id])=>id===key))return;sort[mode]={key,dir:-1};render()});if($('recentPeriod')){$('recentPeriod').value=String(recentCount);$('recentPeriod').onchange=e=>{recentCount=Number(e.target.value);render()}}['search','posFilter','clubFilter','statusFilter','priceFilter'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',render));document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;render()});}
document.querySelectorAll('[data-h]').forEach(b=>b.onclick=()=>{horizon=Number(b.dataset.h);render()});document.addEventListener('error',e=>{if(e.target.tagName==='IMG')e.target.hidden=true},true);load();setInterval(load,300000);
})();
