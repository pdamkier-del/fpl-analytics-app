'use strict';
(function(root){
 let pending;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const day=x=>x?new Date(x).toLocaleDateString('da-DK',{timeZone:'Europe/Copenhagen'}):'Udgivelsestid ikke fastlagt';
 const allowed=u=>{try{const x=new URL(u);return x.protocol==='https:'&&['www.mancity.com','www.chelseafc.com','www.newcastleunited.com','www.liverpoolfc.com','www.leedsunited.com','www.fantasyfootballscout.co.uk'].includes(x.hostname)&&!x.username&&!x.password;}catch{return false;}};
 function validate(data,index,now=Date.now()){
  if(!Number.isFinite(Date.parse(data.observed_at))||Date.parse(data.observed_at)>now+30000)throw Error('Ugyldigt hentetidspunkt');
  if(data.schema!=='player-text-context-v1'||data.season!=='2026-27'||data.forecast_effect!=='none'||data.automatic_refresh!==false||data.observed_at!==index.observed_at||!Array.isArray(data.records)||!Array.isArray(data.teams))throw Error('Ugyldig spillerkontekst');
  for(const r of [...data.records,...data.teams]){if(r.model_input_enabled!==false||!allowed(r.source_url)||!Number.isFinite(Date.parse(r.observed_at))||Date.parse(r.observed_at)>now+30000||!Number.isInteger(r.team_id))throw Error('Ugyldig kontekstkilde');}
  const teamIds=data.teams.map(r=>r.team_id);if(new Set(teamIds).size!==teamIds.length)throw Error('Dubleret klubkontekst');
  for(const r of data.records){if(!Number.isInteger(r.player_id)||!['role_context','historical_match','dated_status'].includes(r.scope)||typeof r.excerpt!=='string'||typeof r.qualification!=='string'||typeof r.interpretation!=='string'||(r.published_at&&(!Number.isFinite(Date.parse(r.published_at))||Date.parse(r.published_at)>Date.parse(r.observed_at))))throw Error('Ugyldigt spillerudsagn');}
  return data;
 }
 async function load(){if(!pending)pending=(async()=>{const base=new URL('../text-context/',location.href),response=await fetch(new URL('index.json',base),{cache:'no-store'});if(!response.ok)throw Error('Ingen spillerkontekst');const index=await response.json();if(index.schema!=='player-text-context-index-v1'||index.file!=='evidence.json')throw Error('Forkert kontekstindeks');const r=await fetch(new URL(index.file,base),{cache:'no-store'});if(!r.ok)throw Error('Ingen kildeoplysninger');const bytes=await r.arrayBuffer(),sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');if(sha!==index.sha256)throw Error('Kontekstens kontrolsum stemmer ikke');return validate(JSON.parse(new TextDecoder().decode(bytes)),index);})().catch(e=>{pending=null;throw e;});return pending;}
 function create(player,compact=false){
  const box=el('section',undefined,'player-text-context');box.append(el('h3','Holdnyt og rolle'),el('p','Henter kildebelagt kontekst …','prob-note'));
  load().then(data=>{box.replaceChildren(el('h3','Holdnyt og rolle'));const records=data.records.filter(r=>r.player_id===player.id&&r.team_id===player.team_id).sort((a,b)=>String(b.published_at||b.observed_at).localeCompare(String(a.published_at||a.observed_at)));const team=data.teams.find(t=>t.team_id===player.team_id);
   if(!records.length)box.append(el('p','Ingen kildebelagt individuel vurdering endnu.','prob-note'));
   for(const r of records.slice(0,compact?1:3)){const item=el('article',undefined,'text-evidence-card');item.append(el('strong',r.source_kind+' · '+day(r.published_at)),el('p','“'+r.excerpt+'”','text-evidence-quote'),el('p','Vurdering: '+r.interpretation),el('p',r.qualification,'prob-note'));const label=r.scope==='historical_match'?'Oplysning til en tidligere kamp':r.scope==='role_context'?'Rollehistorik':'Status på artiklens dato';item.append(el('small',label+' · hentet '+day(r.observed_at)+(Date.now()-Date.parse(r.observed_at)>72*3600000?' · ældre kilde, ny status er ikke kontrolleret':'')));const a=el('a','Læs kilden ↗');a.href=r.source_url;a.target='_blank';a.rel='noopener noreferrer';item.append(a);box.append(item);}
   if(team){const detail=el('details'),s=el('summary','Klubbens seneste indsamlede kontekst · GW8');detail.append(s,el('p',team.summary),el('p','Historisk klubkontekst fra 23. oktober. Det er ikke en individuel spillerbesked eller en opdateret vurdering til næste runde.','prob-note'));const a=el('a','Redaktionel kilde · Fantasy Football Scout ↗');a.href=team.source_url;a.target='_blank';a.rel='noopener noreferrer';detail.append(a);box.append(detail);}
   box.append(el('p','Kildeoplysninger og vurdering vises separat. Denne kontekst ændrer endnu ikke prognosens xMin eller xP. Opdateres ikke automatisk.','prob-note'));
  }).catch(()=>box.replaceChildren(el('h3','Holdnyt og rolle'),el('p','Kildebelagt kontekst kunne ikke hentes. Manglende oplysninger betyder ikke, at spilleren er klar eller ude.','prob-note')));return box;
 }
 const api={validate,load,create,allowed};root.FplPlayerTextContext=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
