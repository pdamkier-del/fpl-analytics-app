'use strict';
(function(root){
const KEY='fpl-season-team-history-v1',position=p=>({1:'GK',2:'DEF',3:'MID',4:'FWD',GKP:'GK',GK:'GK',DEF:'DEF',MID:'MID',FWD:'FWD'}[p.position]||p.position),isXI=r=>['XI','C','VC'].includes(r.role);
function legal(rows){const counts={GK:0,DEF:0,MID:0,FWD:0};for(const r of rows)counts[position(r)]++;return rows.length===11&&counts.GK===1&&counts.DEF>=3&&counts.DEF<=5&&counts.MID>=2&&counts.MID<=5&&counts.FWD>=1&&counts.FWD<=3}
function validSquad(rows){const counts={GK:0,DEF:0,MID:0,FWD:0};if(!Array.isArray(rows)||rows.length!==15||new Set(rows.map(r=>r.id)).size!==15||rows.some(r=>!Number.isInteger(r.id)))return false;for(const r of rows)counts[position(r)]++;return counts.GK===2&&counts.DEF===5&&counts.MID===5&&counts.FWD===3&&rows.filter(r=>r.role==='C').length===1&&rows.filter(r=>r.role==='VC').length===1&&legal(rows.filter(isXI))}

const hasPlayed=r=>r.minutes>0||r.started>0||r.played===true||r.yellow_cards>0||r.red_cards>0;
function score(rows,actual,{chip=null,hits=0}={}){
 if(!validSquad(rows))throw Error('Ugyldig arkiveret trup');
 if(rows.some(r=>!actual.has(r.id)||!actual.get(r.id).final))return null;
 const played=r=>hasPlayed(actual.get(r.id)),xi=rows.filter(isXI),bench=rows.filter(r=>!isXI(r)),captain=xi.find(r=>r.role==='C'),vice=xi.find(r=>r.role==='VC');if(!captain||!vice||captain.id===vice.id)throw Error('Kaptajn og vice mangler');
 let selected=xi.slice(),substitutions=[];
 if(chip!=='bench_boost'){
  const gk=xi.find(r=>position(r)==='GK'),reserve=bench.find(r=>position(r)==='GK');if(!played(gk)&&reserve&&played(reserve)){selected=selected.map(r=>r.id===gk.id?reserve:r);substitutions.push({out:gk.id,in:reserve.id})}
  const missing=xi.filter(r=>position(r)!=='GK'&&!played(r)),reserves=bench.filter(r=>position(r)!=='GK'&&played(r)).sort((a,b)=>Number(String(a.role).replace(/\D/g,''))-Number(String(b.role).replace(/\D/g,'')));let best=[];
  function search(i,used,moves){if(i===reserves.length){const candidate=selected.filter(r=>!moves.some(m=>m.out===r.id)).concat(moves.map(m=>rows.find(r=>r.id===m.in)));if(legal(candidate)){const rank=moves.map(m=>reserves.findIndex(r=>r.id===m.in));if(moves.length>best.length||(moves.length===best.length&&rank.join('')<best.map(m=>reserves.findIndex(r=>r.id===m.in)).join('')))best=moves.slice()}return}search(i+1,used,moves);for(const r of missing)if(!used.has(r.id)){used.add(r.id);moves.push({out:r.id,in:reserves[i].id});search(i+1,used,moves);moves.pop();used.delete(r.id)}}search(0,new Set(),[]);selected=selected.filter(r=>!best.some(m=>m.out===r.id)).concat(best.map(m=>rows.find(r=>r.id===m.in)));substitutions.push(...best);
 }else selected=rows.slice();
 const scoring=selected.filter(played),cap=played(captain)?captain:played(vice)?vice:null,multiplier=chip==='triple_captain'?3:2,gross=scoring.reduce((sum,r)=>sum+actual.get(r.id).points,0)+(cap?(multiplier-1)*actual.get(cap.id).points:0);
 return {gross,hits,net:gross-hits,captain_id:cap?.id??null,scoring_ids:scoring.map(r=>r.id),substitutions};
}
function bestOwnXI(rows,actual,options={}){
 if(rows.length!==15||rows.some(r=>!actual.has(r.id)||!actual.get(r.id).final))return null;let best=null;
 function visit(start,chosen){if(chosen.length===11){if(!legal(chosen))return;const possible=chosen.filter(r=>hasPlayed(actual.get(r.id))).sort((a,b)=>actual.get(b.id).points-actual.get(a.id).points||a.id-b.id),absent=chosen.filter(r=>!hasPlayed(actual.get(r.id))),avoidNegative=possible.length&&actual.get(possible[0].id).points<0&&absent.length>=2;const captain=avoidNegative?absent[0]:possible[0]||chosen[0],vice=avoidNegative?absent[1]:chosen.find(r=>r.id!==captain.id);const xi=new Set(chosen.map(r=>r.id)),candidate=chosen.map(r=>({...r,role:r.id===captain.id?'C':r.id===vice.id?'VC':'XI'})).concat(rows.filter(r=>!xi.has(r.id)).map((r,i)=>({...r,role:position(r)==='GK'?'BGK':'B'+(i+1)})));const result=score(candidate,actual,options);if(!best||result.net>best.score.net)best={rows:candidate,score:result,scope:'Best XI from these same 15, chosen after results; no transfer or chip optimisation.'};return}for(let i=start;i<=rows.length-(11-chosen.length);i++){chosen.push(rows[i]);visit(i+1,chosen);chosen.pop()}}visit(0,[]);return best;
}
function read(storage=localStorage){const raw=JSON.parse(storage.getItem(KEY)||'{"schema":"fpl-season-team-history-v1","seasons":{}}');if(raw.schema!==KEY||!raw.seasons)throw Error('Ukendt holdarkiv');return raw}
let lastSignature=null;
async function capture(c,{now=new Date(),storage=localStorage}={}){
 const p=c?.plan,f=c?.forecast;if(!p||!f||!c.stateValid||!c.usable||p.validation_only||!p.ts_ran||p.forecast_sha256!==f.forecast_sha256||p.gw!==f.gws[0]||Date.parse(f.origin_deadline)<=now.getTime()||!Number.isFinite(Date.parse(p.computed_at))||Date.parse(p.computed_at)>now.getTime()||c.state?.season!==f.season||c.state?.gw!==p.gw)return false;
 const signature=JSON.stringify([f.forecast_sha256,p.computed_at,c.state]);if(signature===lastSignature)return false;
 if(root.FplManagerClient?.hash&&p.manager_state_sha256!==await root.FplManagerClient.hash(c.state))return false;
 const winner={wc:'wildcard',fh:'free_hit',bb:'bench_boost',tc:'triple_captain'}[p.chip_assessment?.provisional_choice_without_missing_tc],choice=p.chip_plan?.rows?.find(r=>r.chip===winner),chip=choice?.expected_use_gw===p.gw&&p.chip_assessment?.availability?.[winner]&&(choice.decision==='USE_NOW_DIAGNOSTIC'||choice.decision==='USE_TC')?winner:null;
 if(chip==='triple_captain')return false; // Do not infer an unconfirmed manual TC target.
 if(chip==='bench_boost'&&!Number.isFinite(p.chip_assessment.bb_gain))return false;
 const candidate=chip&&p.chip_assessment?.candidate_lineups?.[chip],lineup=candidate?.rows||p.lineup;
 if(!legal(lineup.filter(isXI))||lineup.length!==15)return false;
 const own=JSON.parse(storage.getItem('fpl-manual-lineup-v1')||'null'),names=new Map(f.players.map(p=>[p.id,p.name]));
 const archive=read(storage),season=archive.seasons[f.season]||(archive.seasons[f.season]={weeks:{},actual:{}});
 season.weeks[p.gw]={gw:p.gw,recorded_at:now.toISOString(),deadline:f.origin_deadline,forecast_sha256:f.forecast_sha256,model_asof:f.data_asof,computed_at:p.computed_at,chip,hits:chip==='wildcard'||chip==='free_hit'?0:p.plan.path[0].official_hit_points,expected_score:candidate?.expected_score??(p.plan.path[0].projected_manager_score+(chip==='bench_boost'?p.chip_assessment.bb_gain:0)),recommended:lineup.map(r=>({...r,name:names.get(r.id)||r.web_name||String(r.id)})),actual_squad:c.state.squad.map(r=>({...r,name:names.get(r.id),position:f.players.find(p=>p.id===r.id)?.position})),own_selection:own,transfers:chip==='wildcard'||chip==='free_hit'?{outgoing:c.state.squad.filter(p=>!lineup.some(r=>r.id===p.id)).map(p=>p.id),incoming:lineup.filter(r=>!c.state.squad.some(p=>p.id===r.id)).map(r=>r.id)}:{outgoing:p.plan.path[0].outgoing,incoming:p.plan.path[0].incoming},local_clock_only:true};storage.setItem(KEY,JSON.stringify(archive));lastSignature=signature;return true;
}
root.FplSeasonCompare={score,bestOwnXI,read,capture,KEY,legal,validSquad};if(typeof module!=='undefined')module.exports=root.FplSeasonCompare;
})(typeof window==='undefined'?globalThis:window);
