'use strict';
(function(root){
 const VERSION='B-GK-role-aware-v2';
 function validate(f,m,now=Date.now()){
  if(f.model!==VERSION||f.locked_model_active!==false||f.minute_sampler_audit?.sampler!==VERSION)throw Error('Forkert GK-previewversion');
  if(!Array.isArray(f.players)||!f.players.length||new Set(f.players.map(p=>p.id)).size!==f.players.length)throw Error('Ufuldstændig spillerliste');
  const cuts=Object.values(f.component_source_asof||{});
  if(cuts.length<2||cuts.some(c=>!Number.isFinite(Date.parse(c))||Date.parse(c)>now||now-Date.parse(c)>24*3600000)||now>=Date.parse(f.origin_deadline))throw Error('Not Available: data eller deadline er udløbet');
  const mm=new Map(m.players.map(r=>[r.fixture_id+'|'+r.player_id,r]));
  if(mm.size!==m.players.length)throw Error('Dubleret MM-identitet');
  const groups=new Map();
  for(const p of f.players)for(const w of p.weeks)for(const x of w.fixtures){
   if(!Number.isFinite(x.xpts)||!Number.isFinite(x.xmins))throw Error('Manglende forecast');
   if(p.position!==1)continue;
   const r=mm.get(x.fixture_uuid+'|'+p.player_uuid),v=r?.minute_pmf;
   if(!r||v?.length!==91||v.some(p=>!Number.isFinite(p)||p<0)||Math.abs(v.reduce((a,b)=>a+b,0)-1)>1e-8)throw Error('Ugyldig målmandsfordeling');
   if(Math.abs(v.reduce((a,b,i)=>a+b*i,0)-x.xmins)>1e-7||Math.abs(x.xmins-x.pm_analytic_minutes)>1e-7)throw Error('MM/PM-minutter stemmer ikke');
   if(Math.abs(v.slice(60).reduce((a,b)=>a+b,0)-r.p_60_plus)>1e-8||Math.abs(v[90]-r.p_90)>1e-8)throw Error('Minutchancer stemmer ikke');
   const k=p.team_id+'|'+x.fixture_uuid,g=groups.get(k)||{p:0,m:0};g.p+=r.p_start;g.m+=r.xmins;groups.set(k,g);
  }
  if(f.gk_team_fixtures?.length!==2*f.fixtures||groups.size!==f.gk_team_fixtures.length)throw Error('Manglende hold/kampe');
  for(const t of f.gk_team_fixtures){const g=groups.get(t.team+'|'+t.fixture_uuid);if(!g||Math.abs(g.p+t.unlisted_start_probability-1)>1e-7||Math.abs(g.m+t.unlisted_expected_minutes-90)>1e-7)throw Error('Målmandsdækningen er ikke 90 minutter');}
  return mm;
 }
 function interval(r){return r? r.interval80.join('–'):'Not Available';}
 const api={VERSION,validate,interval};root.FplJointGK=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
