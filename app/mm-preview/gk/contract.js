'use strict';
(function(root){
 const VERSION='B-GK-role-aware-v2';
 function distribution(d){
  const keys=['p_start','p_zero','p_cameo','p_60_plus','p_90','p_2_plus','p_5_plus','p_10_plus'];
  if(!d||!Number.isInteger(d.draws)||d.draws<=0||keys.some(k=>!Number.isFinite(d[k])||d[k]<-1e-9||d[k]>1+1e-9))throw Error('Ugyldige PM-sandsynligheder');
  if(Math.abs(d.p_zero+d.p_cameo+d.p_start-1)>1e-8||d.p_90>d.p_60_plus+1e-8||d.p_60_plus>1-d.p_zero+1e-8||d.p_10_plus>d.p_5_plus||d.p_5_plus>d.p_2_plus)throw Error('PM-sandsynligheder stemmer ikke');
  if(d.minute_bins?.length!==4||d.minute_bins.some(x=>!Number.isFinite(x)||x<0||x>1)||Math.abs(d.minute_bins.reduce((a,b)=>a+b,0)-1)>1e-8||Math.abs(d.minute_bins[0]-d.p_zero)>1e-8||Math.abs(d.minute_bins[3]-d.p_90)>1e-8||Math.abs(d.minute_bins[2]+d.minute_bins[3]-d.p_60_plus)>1e-8)throw Error('Ugyldig minutfordeling');
  if(d.points_interval80?.length!==2||d.points_interval80.some(x=>!Number.isFinite(x))||d.points_interval80[0]>d.points_interval80[1]||!Number.isFinite(d.pm_expected_minutes)||d.pm_expected_minutes<0||d.pm_expected_minutes>90)throw Error('Ugyldigt PM-interval');
  return d;
 }
 function validate(f,m,now=Date.now()){
  if(![VERSION,'B-MM-PM-TS-v1'].includes(f.model)||f.locked_model_active!==false||f.minute_sampler_audit?.sampler!==f.model)throw Error('Forkert GK-previewversion');
  if(!Array.isArray(f.players)||!f.players.length||new Set(f.players.map(p=>p.id)).size!==f.players.length)throw Error('Ufuldstændig spillerliste');
  const cuts=Object.values(f.component_source_asof||{});
  if(cuts.length<2||cuts.some(c=>!Number.isFinite(Date.parse(c))||Date.parse(c)>now||now-Date.parse(c)>24*3600000)||now>=Date.parse(f.origin_deadline))throw Error('Not Available: data eller deadline er udløbet');
  const mm=new Map(m.players.map(r=>[r.fixture_id+'|'+r.player_id,r]));
  if(mm.size!==m.players.length)throw Error('Dubleret MM-identitet');
  const groups=new Map();
  for(const p of f.players)for(const w of p.weeks)for(const x of w.fixtures){
   if(!Number.isFinite(x.xpts)||!Number.isFinite(x.xmins))throw Error('Manglende forecast');
   if(x.distribution)distribution(x.distribution);
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
 const api={VERSION,validate,interval,distribution};root.FplJointGK=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
