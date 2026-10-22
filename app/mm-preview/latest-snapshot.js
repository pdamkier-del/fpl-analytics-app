'use strict';
(function(root){
 const POLICY='latest_verified_snapshot_v1',MODEL='B-MM-PM-TS-v1';
 const clock=x=>new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'});
 const api={enabled:true,policy:POLICY};
 api.installWindow=()=>{const original=FplForecastWindow.check;FplForecastWindow.check=(f,o,now=Date.now())=>{
  if(f?.model!==MODEL)return original(f,o,now);
  const cutoff=Date.parse(f.data_asof),deadline=Date.parse(f.origin_deadline);
  if(!Number.isFinite(cutoff)||cutoff>now||!Number.isFinite(deadline)||now>=deadline||o?.next_gw!==f.gws?.[0])return {usable:false,reason:'Denne gameweeks prognose er udløbet eller mangler. En ny modelopdatering kræves.'};
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
  const h=document.createElement('h2');h.textContent='Planens datagrundlag';const p=document.createElement('p');p.textContent='Prognose og priser: '+clock(c.forecast.data_asof)+(c.plan?' · Plan beregnet: '+clock(c.plan.computed_at):'')+'.';
  const note=document.createElement('p');note.textContent='Planen bruger den seneste validerede prognose. Nyere skader og prisændringer kan stå i nyhederne uden at være medregnet. Kontrollér dem før du handler. En ny holdbekræftelse kræver ikke en ny modelkørsel.';
  box.append(h,p,note);host.after(box);
 };};
 root.FplLatestSnapshot=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
