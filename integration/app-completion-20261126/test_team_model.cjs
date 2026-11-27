const assert=require('node:assert/strict'),M=require('./ui/shared-team-model.js');
// Synthetic unit fixtures only, never a real manager response/publication.
const positions=[1,1,2,2,2,2,2,3,3,3,3,3,4,4,4];
const players=new Map(positions.map((position,i)=>[i+1,{id:i+1,position,team_id:Math.floor(i/3)+1,price_tenths:50,weeks:Array.from({length:6},(_,j)=>({gw:12+j,xpts:2}))}]));
const ids=[1,3,4,5,8,9,10,11,13,14,15,2,6,7,12];
const picks=ids.map((element,i)=>({element,position:i+1,is_captain:i===1,is_vice_captain:i===2}));
assert.equal(M.lineup(picks,players).ids.length,15);assert.equal(M.lineup([...picks.slice(0,14),picks[0]],players),null);
const original={squad:ids.map(id=>({id,purchase_price_tenths:50})),bank_tenths:10,free_transfers:1};const serialized=JSON.stringify(original);
players.set(16,{id:16,position:2,team_id:6,price_tenths:55,weeks:Array.from({length:6},()=>({xpts:3}))});const draft=ids.map(id=>id===3?16:id);const c=M.compare(original,draft,players);assert.equal(c.valid,true);assert.equal(c.bank,5);assert.equal(c.hits,0);assert.deepEqual(c.deltas,[1,3,6]);assert.equal(JSON.stringify(original),serialized);
assert.equal(M.sale(50,55),52);assert.equal(M.sale(50,47),47);
const noFinance={...original,bank_tenths:undefined,free_transfers:undefined};const u=M.compare(noFinance,draft,players);assert.equal(u.bank,null);assert.equal(u.hits,null);
assert.equal(M.compare(original,ids.map(id=>id===8?16:id),players).valid,false);
console.log('PASS: official nomination legality, draft isolation, budget/sale/hits, unknown finances and non-TS marginal xP');
const vm=require('node:vm'),fs=require('node:fs');
const urls=[],sandbox={URL,location:{href:'https://pdamkier-del.github.io/fpl-analytics-app/previews/team-transfers-20261126/app/overview.html'},window:{fetch:(u)=>{urls.push(String(u));return Promise.resolve({ok:true});}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/ui/preview-data-root.js','utf8'),sandbox);
sandbox.window.fetch('../current/index.json');sandbox.window.fetch('../../manager-service.json');sandbox.window.fetch('shared-team.js');
assert.equal(urls[0],'https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/current/index.json');assert.equal(urls[1],'https://pdamkier-del.github.io/fpl-analytics-app/manager-service.json');assert.equal(urls[2],'shared-team.js');
console.log('PASS: isolated preview JSON root and private service configuration preserve the existing data chain');
// Regression: a stale live-status/TS gate must not erase a validated MM/PM snapshot.
const contract=require('../model-interface/contract-v1.js');
const frozen={model:'B-MM-PM-TS-v1',locked_model_active:false,season:'2026-27',gws:[12,13,14,15,16,17],data_asof:'2026-11-26T08:00:00Z',origin_deadline:'2026-11-27T18:30:00Z',forecast_sha256:'a'.repeat(64),players:[...players.values()].map(p=>({...p,weeks:p.weeks.map((w,i)=>({...w,gw:12+i,xmins:60}))}))};
const blocked={forecast:frozen,usable:false,reason:'Official status older than two hours'};
const before=JSON.stringify(blocked),now=Date.parse('2026-11-27T11:00:00Z');
assert.equal(contract.validateForecast(frozen).ok,true);
assert.deepEqual(M.projectionState(blocked,contract,now),{available:true,cutoff:frozen.data_asof,historical:false,tsReady:false});
assert.equal(JSON.stringify(blocked),before);assert.equal(blocked.usable,false);
assert.equal(M.projectionState(blocked,contract,Date.parse('2026-11-28T11:00:00Z')).historical,true);
assert.equal(M.projectionState({...blocked,forecast:{...frozen,data_asof:'2026-11-27T12:00:00Z'}},contract,now).available,false);
const broken=structuredClone(frozen);broken.players[0].weeks[0].xpts=null;
assert.equal(M.projectionState({...blocked,forecast:broken},contract,now).available,false);
assert.equal(M.projectionState(blocked,null,now).available,false);
console.log('PASS: original MM/PM remains readable with TS blocked; invalid/future snapshots fail closed and historical data is labelled');
const confirmed={...original,season:'2026-27',gw:12,source:'Synthetic verified entry',observed_at:'2026-11-27T10:00:00Z',chips_used:{wildcard:[],free_hit:[],bench_boost:[],triple_captain:[]}};
const refreshed={...confirmed,observed_at:'2026-11-27T11:00:00Z'};
assert.equal(M.stableVerifiedState(confirmed,refreshed),confirmed);
const changedBank={...refreshed,bank_tenths:11};assert.equal(M.stableVerifiedState(confirmed,changedBank),changedBank);
const changedFt={...refreshed,free_transfers:2};assert.equal(M.stableVerifiedState(confirmed,changedFt),changedFt);
const otherEntry={...refreshed,source:'Other synthetic entry'};assert.equal(M.stableVerifiedState(confirmed,otherEntry),otherEntry);
assert.equal(M.stableVerifiedState({...confirmed,validation_only:true},refreshed),refreshed);
console.log('PASS: identical official revalidation preserves private plan identity; bank/FT/entry changes invalidate it');
assert.equal(M.stableVerifiedState({...confirmed,optional_decision:'different'},refreshed),refreshed);
assert.equal(M.stableVerifiedState({...confirmed,observed_at:'2026-11-28T10:00:00Z'},refreshed),refreshed);

// The production TS client reports real server/polling messages only to these
// data hooks. The isolated UI must expose both hooks, otherwise users see an
// indefinite generic "Beregning i gang" while the service computes.
const transfersHtml=fs.readFileSync(__dirname+'/ui/transfers-classic.html','utf8');
const transfersCss=fs.readFileSync(__dirname+'/ui/shared-team.css','utf8');
assert.match(transfersHtml,/data-compute-feedback/);
assert.match(transfersHtml,/data-compute-status/);
assert.match(transfersHtml,/data-compute/);
assert.match(transfersCss,/\.ts-progress\[data-phase="error"\]/);
console.log('PASS: TS job progress and concrete backend errors have accessible public UI targets');
