'use strict';
(()=>{
 const make=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
 const num=x=>Number.isFinite(x)?x.toFixed(2):'Not Available',pct=x=>Number.isFinite(x)?(100*x).toFixed(1)+' %':'Not Available';
 let data=null,dialog=null;
 function content(player,initialGW,inline=false){
  const root=make('section',undefined,'panel fpl-probabilities'),toolbar=make('div',undefined,'panel-head prob-toolbar');
  const title=make('div'),heading=make('h2',inline?'Minut- og pointchancer':player.name);title.append(heading,make('div',inline?'B-model · sandsynlige udfald pr. kamp':player.team+' · B-model','panel-sub'));toolbar.append(title);
  const controls=make('div'),select=make('select');select.setAttribute('aria-label','GW for sandsynligheder');for(const gw of data.forecast.gws){const o=make('option','GW '+gw);o.value=gw;select.append(o);}select.value=initialGW;controls.append(select);
  if(!inline){const close=make('button','Luk spillerkort');close.type='button';close.onclick=()=>dialog.close();controls.append(close);}
  toolbar.append(controls);const body=make('div',undefined,'panel-body');root.append(toolbar,body);
  function draw(){body.replaceChildren();const week=player.weeks.find(w=>w.gw===Number(select.value));if(!week?.fixtures.length){body.append(make('p','Ingen kamp i denne GW.'));return;}
   for(const f of week.fixtures){const d=f.distribution,m=data.mm.get(f.fixture_uuid+'|'+player.player_uuid),other=data.forecast.players.find(p=>p.team_id!==player.team_id&&p.weeks.some(w=>w.fixtures.some(x=>x.fixture_uuid===f.fixture_uuid))),fixture=make('div',undefined,'prob-fixture');
    fixture.append(make('h3',(other?'Mod '+other.team:'Kamp')+' · '+new Date(f.kickoff).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'})),make('p','xP '+num(f.xpts)+' · xM '+num(f.xmins)+' · PM E[min] '+num(m?.xmins??d.pm_expected_minutes)));
    const values=[['P(0 minutter)',m?1-m.p_play:d.p_zero],['P(indhop)',m?m.p_play-m.p_start:d.p_cameo],['P(start)',m?.p_start??d.p_start],['P(60+ minutter)',m?.p_60_plus??d.p_60_plus],['P(90 minutter)',m?.p_90??d.p_90],['Mindst 2 point',d.p_2_plus],['Mindst 5 point',d.p_5_plus],['Mindst 10 point',d.p_10_plus]],grid=make('div',undefined,'prob-grid');
    for(const[label,value]of values){const card=make('div',undefined,'card');card.append(make('div',label,'label'),make('div',pct(value),'value'));grid.append(card);}fixture.append(grid);
    const bins=m?[1-m.p_play,m.p_play-m.p_60_plus,m.p_60_plus-m.p_90,m.p_90]:d.minute_bins;
    fixture.append(make('p','Centralt 80 % pointinterval: '+d.points_interval80.map(num).join(' – '),'prob-note'),make('p','Minutfordeling: '+['0 min','1–59 min','60–89 min','90 min'].map((label,i)=>label+' '+pct(bins[i])).join(' · '),'prob-note'));
    body.append(fixture);
   }
   body.append(make('p','Pointchancer bygger på 400 fælles PM-simuleringer. Start, 60+ og 90 minutter overlapper; minutgrupperne summerer til 100 %. Tallene er modelestimater, ikke garantier. Små procentforskelle bør ikke overfortolkes.','prob-note'));
  }
  select.onchange=draw;draw();return root;
 }
 function open(id){const player=data?.forecast.players.find(p=>p.id===Number(id));if(!player)return;
  if(!dialog){dialog=make('dialog',undefined,'fpl-probability-dialog');dialog.setAttribute('aria-label','Spillerkort med sandsynligheder');document.body.append(dialog);}
  const panel=content(player,data.forecast.gws[0]);dialog.replaceChildren(panel);const link=make('a','Åbn det fulde spillerkort →');link.href='player.html?id='+player.id;panel.append(link);dialog.showModal();
 }
 async function init(){
  if(!window.FplBExistingApp)return;
  try{data=await FplBExistingApp.probabilities();
   const id=Number(new URLSearchParams(location.search).get('id')),player=data.forecast.players.find(p=>p.id===id);
   if(player&&location.pathname.endsWith('/player.html')){const target=document.querySelector('#gwStrip')?.closest('section');if(target){const panel=content(player,data.forecast.gws[0],true);panel.id='player-probabilities';target.after(panel);}}
   // The existing forecast table, club pitch and profile stay in the desktop
   // navigation. Only a normal left click on a player opens the detail panel.
   document.addEventListener('click',event=>{if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const a=event.target.closest('a[href]');if(!a||a.closest('dialog'))return;const url=new URL(a.href,location.href);if(url.origin!==location.origin||!url.pathname.endsWith('/player.html'))return;if(a.closest('#forecastTable,#pitch,#clubBench,#clubUnavailable')){event.preventDefault();open(url.searchParams.get('id'));}});
   // Extend the original My Team sheet rather than replace its captain/swap UI.
   document.addEventListener('click',event=>{const trigger=event.target.closest('[data-open]');if(!trigger)return;queueMicrotask(()=>{const host=document.querySelector('#sheetMeta')?.parentElement;if(!host)return;host.querySelector('.fpl-probabilities')?.remove();const p=data.forecast.players.find(p=>p.id===Number(trigger.dataset.open));if(p)host.append(content(p,data.forecast.gws[0],true));});},true);
   window.FplDesktopProbabilities={open};
  }catch(e){const target=document.querySelector('#gwStrip')?.closest('section');if(target){const note=make('p','Sandsynligheder er ikke tilgængelige: '+e.message,'prob-note');target.append(note);}}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
