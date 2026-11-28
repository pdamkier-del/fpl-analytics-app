'use strict';
(function(root){
 const POLICY='latest_verified_snapshot_v1',MODEL='B-MM-PM-TS-v1';
 const clock=x=>new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'});
 const MAX_AGE_MS=36*60*60*1000; // An expired data capture must never silently produce a new-looking transfer plan.
 const api={enabled:true,policy:POLICY};
 api.installWindow=()=>{const original=FplForecastWindow.check;FplForecastWindow.check=(f,o,now=Date.now())=>{
  if(f?.model!==MODEL)return original(f,o,now);
  const cutoff=Date.parse(f.data_asof),deadline=Date.parse(f.origin_deadline);
  if(!Number.isFinite(cutoff)||cutoff>now||!Number.isFinite(deadline)||now>=deadline||o?.next_gw!==f.gws?.[0])return {usable:false,reason:'Prognosen er ikke til den aktuelle gameweek, eller deadline er passeret. Transferplanen må ikke genberegnes på den.'};
  if(now-cutoff>MAX_AGE_MS)return {usable:false,reason:'Prognosen er mere end 36 timer gammel ('+clock(f.data_asof)+'). Der kræves en ny verificeret MM/PM-opdatering før en ny transferplan.'};
  return {usable:true,snapshot:true,reason:'Seneste validerede prognose · '+clock(f.data_asof)};
 };};
 api.installNews=()=>{const original=FplTeamNews.evaluate;FplTeamNews.evaluate=(c,now=Date.now())=>{
  const r=original(c,now);if(c.forecast?.model!==MODEL)return r;
  const valid=FplForecastWindow.check(c.forecast,c.official,now).usable&&(!c.news||c.news.next_gw===c.forecast.gws[0]);
  if(!valid)return r;
  const ready=!!(c.stateValid&&c.state?.gw===c.forecast.gws[0]&&c.plan?.ts_ran&&c.plan.forecast_sha256===c.forecast.forecast_sha256&&c.plan.gw===c.forecast.gws[0]);
  const phase=!c.state?'missing_team':!c.stateValid||c.state.gw!==c.forecast.gws[0]?'update_state':c.busy?'calculating':ready?'ready':'can_compute';
  const message=phase==='missing_team'||phase==='update_state'?r.message:(ready?'Plan klar':c.busy?'Planen beregnes':'Klar til beregning')+' · prognose fra '+clock(c.forecast.data_asof)+'.';
  return {...r,phase,message,aligned:true,alignmentReason:'',canCompute:!!(c.stateValid&&c.state?.gw===c.forecast.gws[0]&&!c.busy),planReady:phase==='ready',snapshotWarning:r.changed?r.alignmentReason:r.issue||''};
 };};
 api.reason=(state,forecast,official)=>{const w=FplForecastWindow.check(forecast,official);return !w.usable?w.reason:FplPlannerExperience.diagnose(state,forecast).join(' ');};
 api.installPlanner=()=>{const original=FplPlannerExperience.mount;FplPlannerExperience.mount=c=>{
  original(c);if(!c?.forecast)return;document.getElementById('latest-snapshot-info')?.remove();
  const host=document.getElementById('planner-context');if(!host)return;
  const box=document.createElement('section');box.id='latest-snapshot-info';box.className='panel';
  const h=document.createElement('h2');h.textContent='Planens datagrundlag';const p=document.createElement('p');p.textContent='GW '+c.forecast.gws[0]+'–'+c.forecast.gws.at(-1)+' · Model '+c.forecast.model+' · Prognose og priser: '+clock(c.forecast.data_asof)+(c.plan?' · Plan beregnet: '+clock(c.plan.computed_at):'')+'.';
  const note=document.createElement('p');note.textContent='Vis nyeste transferplan henter det nyeste publicerede verificerede snapshot og genberegner transferoptimering, hvis nødvendigt. Knappen starter ikke selv en ny MM/PM-modelkørsel. Prognoser ældre end 36 timer eller for forkert GW blokeres. Nyere skader og prisændringer kan stadig mangle; kontrollér dem før du handler.';
  box.append(h,p,note);
  const dashboard=document.getElementById('weekly-main');
  const compactDashboard=document.getElementById('compact-team')&&(!location.hash||location.hash==='#dashboard');
  if(compactDashboard&&dashboard){
   const modelGuide=dashboard.querySelector(':scope > #dashboard-model-explainer');
   dashboard.insertBefore(host,modelGuide);
   dashboard.insertBefore(box,modelGuide);
  }else host.after(box);
  root.FplTransferResultSummary?.placeData();
 };};
 root.FplLatestSnapshot=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
