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
