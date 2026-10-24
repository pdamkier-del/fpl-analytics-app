const assert=require('node:assert/strict');
const P=require('../app/mm-preview/planner-experience.js');
const players=Array.from({length:15},(_,i)=>({id:i+1,position:i<2?1:i<7?2:i<12?3:4,team_id:Math.floor(i/3)+1}));
const forecast={season:'2026-27',gws:[8,9,10,11,12,13],players};
const state={season:forecast.season,gw:8,source:'SYNTHETIC_CONFIRMED_TEAM',observed_at:'2026-10-20T10:00:00Z',
 bank_tenths:7,free_transfers:2,squad:players.map(p=>({id:p.id,purchase_price_tenths:50})),
 chips_used:{wildcard:[],free_hit:[],bench_boost:[],triple_captain:[]}};
const now='2026-10-21T10:00:00Z';
assert.throws(()=>P.prepare(state,forecast,'0.7','2',false,now),/Bekræft/);
assert.deepEqual(P.prepare(state,forecast,'0.7','2',true,now),state,
 'Confirming identical facts must retain provenance and the manager hash instead of restarting a model wait');
for(const [bank,ft,expected]of [['0.8','2',{bank_tenths:8}],['0.7','3',{free_transfers:3}]]){
 const next=P.prepare(state,forecast,bank,ft,true,now);
 assert.equal(next.observed_at,now);for(const [k,v]of Object.entries(expected))assert.equal(next[k],v);
 assert.deepEqual(next.squad,state.squad);
}
const old={...state,gw:7};assert.equal(P.prepare(old,forecast,'0.7','2',true,now).observed_at,now);
assert.equal(state.observed_at,'2026-10-20T10:00:00Z');assert.equal(state.bank_tenths,7);
console.log('PASS: identical confirmations preserve actual provenance; changed bank, FT and GW establish a new observation.');
