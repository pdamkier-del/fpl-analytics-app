'use strict';
(function(root){
 function catalogue(f,o){
  if(f?.model!=='B_locked_PM_preview'||f.scope!=='prospective_preview'||f.locked_model_active!==false||f.minute_sampler_audit?.sampler!=='locked')throw Error('Forkert aktuel B-/PM-kontrakt');
  const byId=new Map(o?.players?.map(p=>[p.id,p]));
  if(!byId.size||byId.size!==o.players.length||byId.size!==f.players?.length||new Set(f.players.map(p=>p.id)).size!==byId.size)throw Error('Officielt spillerudvalg er ændret; nyt forecast kræves');
  for(const p of f.players){const q=byId.get(p.id);if(!q||q.team!==p.team_id||q.position!==p.position||!Number.isInteger(p.price_tenths)||Math.abs(q.price*10-p.price_tenths)>1e-6)throw Error('Pris, klub eller position er ændret; nyt forecast kræves');
   if(p.weeks?.map(w=>w.gw).join(',')!==f.gws.join(',')||p.weeks.some(w=>!Number.isFinite(w.xpts)||!Number.isFinite(w.xmins)||!Number.isFinite(w.pm_analytic_minutes)||w.p_play<0||w.p_play>1))throw Error('Ufuldstændig spillerprognose');
  }return true;
 }
 function metrics(p,gw,mm){const w=p.weeks.find(w=>w.gw===gw);if(!w)throw Error('GW mangler');const starts=w.fixtures.map(f=>mm.get(f.fixture_uuid+'|'+p.player_uuid)?.p_start);if(starts.some(p=>!Number.isFinite(p)))throw Error('MM/PM-spilleridentitet mangler');return {name:p.name,price:p.price_tenths/10,xp:w.xpts,six:p.weeks.reduce((a,w)=>a+w.xpts,0),xm:w.xmins,pm:w.pm_analytic_minutes,play:w.p_play,start:starts.length?Math.max(...starts):0,starts,status:w.unavailable?'Verificeret fravær':w.fixtures.length?'Diagnostisk':'Blank GW'};}
 function interval(row){return row.uncertainty_validated===true&&Array.isArray(row.interval80)?row.interval80.join('–')+' min':'Not Available: interval er ikke valideret';}
 const api={catalogue,metrics,interval};root.FplBPreviewContract=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
