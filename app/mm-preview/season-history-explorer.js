'use strict';
// Retrospective public statistics only. No manager storage or model changes.
(function(){
 const $=id=>document.getElementById(id),make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const number=(v,d=0)=>v===null||v===undefined?'—':Number(v).toFixed(d);
 const key=s=>String(s||'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('da');
 let archive,season,view='players',selected=null,token=0;
 const params=new URLSearchParams(location.search);
 async function read(file,sha){
  if(!/^(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_.-]+\.json$/.test(file)||file.includes('..'))throw Error('Ugyldig historikkilde');
  const response=await fetch('../history-archive/'+file,{cache:'no-store'});if(!response.ok)throw Error('Historikkilden svarer '+response.status);
  const body=await response.arrayBuffer();
  if(sha){const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',body)),v=>v.toString(16).padStart(2,'0')).join('');if(digest!==sha)throw Error('Historikken er ved at blive opdateret. Prøv igen.');}
  return JSON.parse(new TextDecoder().decode(body));
 }
 function table(labels,rows){const wrap=make('div',undefined,'table-wrap archive-table'),t=make('table'),head=make('thead'),tr=make('tr'),body=make('tbody');
  for(const label of labels){const th=make('th',label);th.scope='col';tr.append(th);}head.append(tr);
  for(const values of rows){const r=make('tr');for(const value of values){const cell=make('td');if(value instanceof Node)cell.append(value);else cell.textContent=value;r.append(cell);}body.append(r);}
  t.append(head,body);wrap.append(t);return wrap;
 }
 function pick(label,fn){const b=make('button',label,'archive-player-link');b.type='button';b.onclick=fn;return b;}
 function choose(record,type){params.delete('player');params.set('id',type==='player'?record.player_uuid:record.key);return open(record,type);}
 function sync(){const q=new URLSearchParams({season:season.season,view});if($('archive-search').value)q.set('search',$('archive-search').value);if($('archive-club').value)q.set('club',$('archive-club').value);if(selected){q.set('id',String(selected));}history.replaceState(null,'','?'+q);}
 function render(){
  if(!season)return;
  const term=key($('archive-search').value),club=$('archive-club').value;
  const rows=view==='players'?season.players.filter(p=>(!term||key(p.name+' '+p.clubs.join(' ')).includes(term))&&(!club||p.clubs.includes(club))).map(p=>club?{...p,...p.by_club[club]}:p):season.teams.filter(t=>(!term||key(t.name).includes(term))&&(!club||t.name===club));
  const oldSort=$('archive-sort').value,sorts=view==='players'?[['points','Point'],['minutes','Minutter'],['goals','Mål'],['xg','xG']]:[['points','Kamppoint'],['goals','Mål'],['xg','xG']];
  $('archive-sort').replaceChildren(...sorts.map(([v,label])=>new Option(label,v)));if(sorts.some(([v])=>v===oldSort))$('archive-sort').value=oldSort;
  const sort=$('archive-sort').value;rows.sort((a,b)=>Number(b[sort]??-1)-Number(a[sort]??-1)||a.name.localeCompare(b.name,'da'));
  const data=view==='players'?rows.map(p=>[pick(p.name,()=>choose(p,'player')),club||p.clubs.join(', '),p.position,number(p.minutes),number(p.points),number(p.goals),number(p.assists),number(p.xg,2),number(p.xa,2)]):rows.map(t=>[pick(t.name,()=>choose(t,'team')),t.matches,t.wins,t.draws,t.losses,t.points,number(t.goals),number(t.conceded),number(t.xg,2),number(t.xga,2)]);
  const labels=view==='players'?['Spiller','Klub i sæsonen','Pos','Min','Point','Mål','Assists','xG','xA']:['Hold','Kampe','V','U','T','Kamppoint','Mål','Imod','xG','xGA'];
  $('archive-results').replaceChildren(data.length?table(labels,data):make('p','Ingen resultater for dette filter.','card'));
  $('archive-count').textContent=rows.length+' '+(view==='players'?'spillere':'hold')+' · '+season.season.replace('-','/');
  document.querySelectorAll('[data-archive-view]').forEach(b=>{b.classList.toggle('active',b.dataset.archiveView===view);b.setAttribute('aria-pressed',String(b.dataset.archiveView===view));});
  sync();
 }
 async function open(record,type){
  const request=++token;selected=type==='player'?record.player_uuid:record.key;sync();
  const target=$('archive-detail');target.hidden=false;target.replaceChildren(make('p','Henter kampe …'));target.setAttribute('aria-busy','true');
  try{
   const data=await read(record.file,record.sha256);if(request!==token)return;
   target.replaceChildren(make('h2',record.name+' · '+season.season.replace('-','/')));
   if(type==='player'){
    const current=Object.entries(archive.current_players).find(([uuid,code])=>uuid===record.player_uuid||(record.code!==null&&String(record.code)===String(code)));
    if(current){const info=make('a','Se aktuelle prognoser og næste kampe');info.href='player.html?id='+archive.current_player_ids[current[1]];target.append(info);}
    const club=$('archive-club').value;
    target.append(table(['GW','Dato','Klub','Modstander','Resultat','Min','Point','Mål','Assists','xG','xA'],data.matches.filter(r=>!club||r.club===club).map(r=>[
     'GW '+r.gw,new Date(r.kickoff).toLocaleDateString('da-DK'),r.club,r.opponent+(r.home?' (H)':' (U)'),r.gf+'–'+r.ga,number(r.minutes),number(r.points),number(r.goals),number(r.assists),number(r.xg,2),number(r.xa,2)])));
   }else target.append(table(['GW','Dato','Modstander','Resultat','xG','xGA'],data.matches.map(r=>['GW '+r.gw,new Date(r.kickoff).toLocaleDateString('da-DK'),r.opponent+(r.home?' (H)':' (U)'),r.gf+'–'+r.ga,number(r.xg,2),number(r.xga,2)])));
   target.append(make('p','Faktiske Premier League-kampe. — betyder manglende data. Kampstatistik er ikke en historisk modelprognose.','notice'));
  }catch(e){if(request===token)target.replaceChildren(make('p',e.message,'card'));}
  finally{if(request===token)target.setAttribute('aria-busy','false');}
 }
 function busy(value){document.querySelectorAll('#archive-season,#archive-club,#archive-search,#archive-sort,[data-archive-view]').forEach(n=>n.disabled=value);}
 async function loadSeason(){
  const item=archive.seasons.find(s=>s.season===$('archive-season').value);$('archive-status').textContent='Henter sæson …';
  busy(true);
  const request=++token;selected=null;$('archive-detail').hidden=true;
  try{
   const data=await read(item.file,item.sha256);if(request!==token)return;season=data;
   $('archive-club').replaceChildren(new Option('Alle klubber',''),...data.teams.map(t=>new Option(t.name,t.name)).sort((a,b)=>a.text.localeCompare(b.text,'da')));
   const desired=params.get('club');if(desired){const canonical=archive.current_teams[desired];const team=data.teams.find(t=>t.name===desired||t.key===canonical||t.key===desired);if(team)$('archive-club').value=team.name;}
   $('archive-status').textContent='380 afsluttede kampe · '+data.players.length+' spillere · kildekontrolleret arkiv';
   $('archive-search').value=params.get('search')||'';busy(false);render();
   const uuid=params.get('player'),code=archive.current_players[uuid],id=params.get('id');
   const match=view==='players'?data.players.find(p=>(uuid&&(p.player_uuid===uuid||(code&&String(p.code)===code)))||p.player_uuid===id):data.teams.find(t=>t.key===id||(desired&&(t.name===desired||t.key===archive.current_teams[desired])));
   if(match)await open(match,view==='players'?'player':'team');
   else if(uuid&&view==='players')$('archive-status').textContent+=' · Ingen kampe i denne sæson for den valgte spiller.';
  }catch(e){if(request===token){busy(false);$('archive-status').textContent=e.message;$('archive-results').replaceChildren();}}
 }
 async function init(){try{
  archive=await read('index.json');if(archive.schema!=='fpl-public-history-archive-v1')throw Error('Ukendt arkivversion');
  view=params.get('view')==='teams'?'teams':'players';
  $('archive-season').replaceChildren(...[...archive.seasons].reverse().map(s=>new Option(s.season.replace('-','/'),s.season)));
  if(archive.seasons.some(s=>s.season===params.get('season')))$('archive-season').value=params.get('season');
  $('archive-season').onchange=loadSeason;$('archive-retry').onclick=loadSeason;
  $('archive-search').oninput=()=>{params.set('search',$('archive-search').value);params.delete('player');render();};
  $('archive-club').onchange=()=>{params.set('club',$('archive-club').value);params.delete('player');render();};$('archive-sort').onchange=render;
  document.querySelectorAll('[data-archive-view]').forEach(b=>b.onclick=()=>{++token;view=b.dataset.archiveView;selected=null;params.delete('player');params.delete('id');params.delete('search');$('archive-search').value='';$('archive-detail').hidden=true;render();});
  await loadSeason();
 }catch(e){$('archive-status').textContent='Historikken kunne ikke hentes: '+e.message;}}
 init();
})();
