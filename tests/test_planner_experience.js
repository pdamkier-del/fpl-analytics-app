const assert=require('node:assert/strict'),fs=require('fs');
const p=require('../app/mm-preview/planner-experience.js');
const fixture=JSON.parse(fs.readFileSync(process.env.DASHBOARD_TEST_FIXTURE));
const forecast=JSON.parse(fs.readFileSync(process.env.PLANNER_TEST_FORECAST||'app/mm-preview/current/forecast.json')),state=fixture.state,people=new Map(forecast.players.map(p=>[p.id,p]));
assert.deepEqual(p.diagnose(state,forecast),[]);
const old=structuredClone(state);old.gw=7;assert.match(p.diagnose(old,forecast).join(' '),/GW 7.*GW 8/);
assert.throws(()=>p.prepare(old,forecast,'0.7','2',false),/Bekræft/);
const next=p.prepare(old,forecast,'0.7','2',true);assert.equal(next.gw,8);assert.deepEqual(next.squad,old.squad);assert.deepEqual(next.chips_used,old.chips_used);assert.equal(old.gw,7);assert.equal(next.bank_tenths,7);assert.equal(next.free_transfers,2);
assert.throws(()=>p.prepare(old,forecast,'0.77','2',true));
assert.throws(()=>p.prepare(old,forecast,'0.7','6',true));
const zero=p.scenario(state,people,[],[]);assert.equal(zero.delta,0);assert.equal(zero.hit,0);assert.equal(zero.ft,3);
const first=fixture.result.plan.path[0];if(first.incoming.length){const o=first.outgoing[0],i=first.incoming.find(id=>people.get(id).position===people.get(o).position),r=p.scenario({...state,free_transfers:0},people,[o],[i]);assert.equal(r.hit,4);assert(Math.abs(r.delta-(people.get(i).weeks[0].xpts-people.get(o).weeks[0].xpts-4))<1e-10);assert.throws(()=>p.scenario(state,people,[o,o],[i,i]));}
const a=state.squad[0].id,b=[...people.values()].find(x=>x.position!==people.get(a).position);assert.throws(()=>p.scenario(state,people,[a],[b.id]),/samme position/);
assert.equal(p.impact({id:state.squad[0].id,verified:false},state,forecast),'');
const html=p.explanation(fixture.result,people);assert.match(html,/ikke et ekstra FPL/);assert.match(html,/P\(start\)/);
const storage=new Map([['fpl-manager-plan-v1',JSON.stringify(fixture.result)]]),api={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};p.archive(api);p.archive(api);assert.equal(JSON.parse(storage.get('fpl-private-plan-history-v1')).length,1);assert(storage.has('fpl-manager-plan-v1'));
console.log('PASS: exact GW diagnosis, confirmed rollover preserving all actual IDs/prices/chips, constraints, hit arithmetic, unchanged legacy plan archive.');
