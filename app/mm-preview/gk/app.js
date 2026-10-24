'use strict';
(async()=>{
 const $=id=>document.getElementById(id),make=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;},fmt=n=>Number.isFinite(n)?n.toFixed(2):'Not Available',pct=n=>Number.isFinite(n)?(100*n).toFixed(1)+' %':'Not Available';
 const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
 try{
  const response=await fetch('index.json',{cache:'no-store'});if(!response.ok)throw Error('Forecast er endnu ikke publiceret');const index=await response.json();
  const load=async(name,key)=>{const r=await fetch(name,{cache:'no-store'});if(!r.ok)throw Error('Manglende '+name);const b=await r.arrayBuffer();if(await digest(b)!==index[key])throw Error('Checksumfejl i '+name);return JSON.parse(new TextDecoder().decode(b));};
  const [f,m,b,evidence,v1]=await Promise.all([load('forecast.json','forecast_sha256'),load('gk-mm.json','mm_sha256'),load('before.json','before_sha256'),load('evidence.json','evidence_sha256'),load('before-v1.json','before_v1_sha256')]);
  if(evidence.model!==FplJointGK.VERSION||!evidence.role_validation?.accepted)throw Error('Rollekorrektionen er ikke valideret');
  const mm=FplJointGK.validate(f,m),previous=new Map(v1.players.map(p=>[p.fixture_uuid+'|'+p.player_uuid,p])),before=new Map(b.players.map(p=>[p.fixture_uuid+'|'+p.player_uuid,p]));
  $('status').textContent=FplJointGK.VERSION+' · '+f.players.length+' spillere · '+f.fixtures+' kampe · SHA-256 verificeret';
  $('quality').textContent='Originale MM/PM-kilder: '+f.component_source_asof.original_B_PM+' · officiel målmandstrup: '+f.component_source_asof.official_GK_roster+'. GK-sampleren og den fælles startudvælgelse er ændret eksplicit i denne preview.';
  $('gw').replaceChildren(...f.gws.map(g=>{const e=make('option','GW '+g);e.value=g;return e;}));
  $('panel-gw').replaceChildren(...Array.from($('gw').options,o=>o.cloneNode(true)));
  $('close-panel').onclick=()=>$('player-panel').close();
  $('panel-gw').onchange=()=>{$('gw').value=$('panel-gw').value;draw();};
  const clubs=new Map(f.players.map(p=>[p.team_id,p.team]));for(const[id,name]of[...clubs].sort((a,b)=>a[1].localeCompare(b[1]))){const e=make('option',name);e.value=id;$('club').append(e);}
  let selected=null;
  function compare(p){
   selected=p;$('panel-gw').value=$('gw').value;if(!$('player-panel').open)$('player-panel').showModal();const gw=Number($('gw').value),w=p.weeks.find(w=>w.gw===gw),box=$('comparison');
   box.replaceChildren(make('h3',p.name+' · '+p.team+' · GW '+gw));
   if(!w.fixtures.length)box.append(make('p','Ingen kamp i denne GW.'));
   for(const x of w.fixtures){
    const section=make('section'),d=x.distribution,r=mm.get(x.fixture_uuid+'|'+p.player_uuid);
    const opponent=f.players.find(other=>other.team_id!==p.team_id&&other.weeks.some(week=>week.fixtures.some(fixture=>fixture.fixture_uuid===x.fixture_uuid)))?.team;
    section.className='fixture-panel';section.append(make('h4',(opponent?'Mod '+opponent:x.fixture_uuid)+(x.kickoff?' · '+new Date(x.kickoff).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'}):'')),make('p','xP '+fmt(x.xpts)+' · xM '+fmt(x.xmins)));
    if(!d){section.append(make('p','Sandsynligheder er endnu ikke tilgængelige for denne kamp.'));box.append(section);continue;}
    const grid=make('div');grid.className='prob-grid';
    const fields=[['P(0 minutter)',r?1-r.p_play:d.p_zero],['P(indhop)',r?r.p_play-r.p_start:d.p_cameo],['P(start)',r?.p_start??d.p_start],['P(60+ minutter)',r?.p_60_plus??d.p_60_plus],['P(90 minutter)',r?.p_90??d.p_90],['Mindst 2 point',d.p_2_plus],['Mindst 5 point',d.p_5_plus],['Mindst 10 point',d.p_10_plus]];
    for(const[label,value]of fields){const card=make('div');card.append(make('span',label),make('strong',pct(value)));grid.append(card);}section.append(grid);
    section.append(make('p','Centralt 80 % modelinterval: '+d.points_interval80.map(fmt).join(' – ')+' point · PM E[min] '+fmt(r?.xmins??d.pm_expected_minutes)));
    const bins=r?[1-r.p_play,r.p_play-r.p_60_plus,r.p_60_plus-r.p_90,r.p_90]:d.minute_bins;
    section.append(make('p','Minutfordeling: '+['0 min','1–59 min','60–89 min','90 min'].map((label,i)=>label+' '+pct(bins[i])).join(' · ')));
    section.append(make('p','Pointchancer og outfield-minutter: '+d.draws+' fælles PM-simuleringer. Små forskelle i procenter kan skyldes simuleringen. GK-minutter vises fra den præcise fælles fordeling.'));
    const old=previous.get(x.fixture_uuid+'|'+p.player_uuid);
    if(old){const detail=make('details');detail.append(make('summary','GK før / efter'),make('p','Før: xM '+fmt(old.xm)+' · P(start) '+pct(old.p)+' · xP '+fmt(old.xp)),make('p','Nu: xM '+fmt(x.xmins)+' · P(start) '+pct(r?.p_start)+' · xP '+fmt(x.xpts)));section.append(detail);}
    box.append(section);
   }
   box.append(make('p','P(start), P(60+) og P(90) overlapper. Minutfordelingens fire grupper summerer til 100 %. Intervallet er et modelestimat, ikke en garanti. Fremtidige skadesreturer er betingede antagelser.'));
  }
  function draw(){FplJointGK.validate(f,m);const gw=Number($('gw').value),q=$('search').value.toLocaleLowerCase('da');const rows=f.players.filter(p=>(!$('position').value||p.position===Number($('position').value))&&(!$('club').value||p.team_id===Number($('club').value))&&p.name.toLocaleLowerCase('da').includes(q)).map(p=>({p,w:p.weeks.find(w=>w.gw===gw)})).sort((a,b)=>b.w.xpts-a.w.xpts);
   $('rows').replaceChildren(...rows.map(({p,w})=>{const tr=document.createElement('tr'),name=document.createElement('td'),button=make('button',p.name);button.onclick=()=>compare(p);name.append(button);tr.append(name);const values=[p.team,fmt(w.xpts),fmt(w.xmins),w.fixtures.map(x=>pct(mm.get(x.fixture_uuid+'|'+p.player_uuid)?.p_start??x.distribution?.p_start)).join(' / ')||'Ingen kamp',fmt(p.weeks.reduce((s,w)=>s+w.xpts,0))];for(const value of values)tr.append(make('td',value));return tr;}));
   if(selected&&$('player-panel').open&&rows.some(x=>x.p===selected))compare(selected);else{selected=null;$('player-panel').close();}
  }
  const e=f.official_gk_evidence;$('sources').replaceChildren(make('span','Chelsea: '+e.first_team_goalkeepers.map(p=>p.name).join(', ')+'. Ikke i FPL: '+e.unlisted_competitors.join(', ')+'. '));for(const source of Object.values(e.sources)){const a=make('a',new URL(source.url).hostname+' · officiel kilde');a.href=source.url;a.target='_blank';a.rel='noopener';$('sources').append(a,document.createTextNode(' · '));}
  const review=e.hierarchy_review;if(review)$('sources').prepend(make('p','Officielle kampoplysninger: Penders var eneste GK-reserve mod Everton og afløste Martínez. Alonso udtrykker fuld tillid. Sharman-Lowe og Slonina var ikke i kamptruppen; deres næste tilgængelighed er ikke bekræftet. Registrering alene giver ikke en stor startchance.'));
  const role=evidence.role_validation;if(role){const a=role.mm_metrics.all,fit=role.fit;$('sources').append(make('p','Ny rollekorrektion: én fuldt tilgængelig, etableret kandidat får hovedparten af starterne. Historisk start-Brier '+a.v1.start_brier.toFixed(5)+' → '+a.v2.start_brier.toFixed(5)+'. MM-test GW6–38; kun '+role.role_applied_team_fixtures+' historiske hold/kampe rammes. Risiko for en anden starter i denne situation: '+pct(fit.predictive_other_start_probability)+'. Begrænset stikprøve; ikke uafhængigt certificeret.'));
   $('quality').append(document.createTextNode(' Rollefordelingen er opdateret i v2. Eksisterende konkurrence mellem flere etablerede målmænd bevares.'));
  }
  $('coverage').textContent=f.gk_team_fixtures.length+' hold/kampe: én GK-starter og 90 minutter inklusive den ikke-listede gruppe. Modellen sampler 11 startere pr. hold. Historiske resultater findes i evidensfilen; perioden er genbrugt forskning, ikke uafhængig certificering.';
  for(const id of['gw','position','club','search'])$(id).oninput=()=>{try{draw();}catch(e){$('content').hidden=true;$('status').textContent='Not Available: '+e.message;}};
  $('content').hidden=false;draw();
 }catch(e){$('content').hidden=true;$('status').textContent='Not Available: '+e.message;}
})();
