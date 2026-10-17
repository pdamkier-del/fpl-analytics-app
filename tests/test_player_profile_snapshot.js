'use strict';
// Execute actual profile rendering against an explicit synthetic transport fixture.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',insertAdjacentHTML(){}});return nodes.get(id)};
 const player={id:411,name:'Synthetic duration fixture',team:'Fixture',team_id:1,position:4,price_tenths:100,weeks:[{gw:7,xpts:5.92,xmins:68.3,fixtures:[{fixture_uuid:'fixture-1',xpts:5.92,xmins:68.3,p_start:.8382,components:{goal_points:3.05}}]}]};
 const f={model:'original_locked_vFinal_diagnostic',data_asof:'fixture-cutoff',players:[player]},o={players:[{id:411,status:'a'}],teams:{1:{name:'Fixture'},2:{name:'Opponent'}},fetched_at:'fixture-cutoff'};
 const requested=[];const context={window:{},document:{getElementById:node},location:{search:'?id=411'},URLSearchParams,AbortSignal,FplForecastWindow:{check:()=>({usable:true})},console,fetch:async url=>{requested.push(url);return {ok:true,json:async()=>url==='vfinal-diagnostic.json'?f:url==='current-players.json'?o:url==='live-fixtures.json'?{fixtures:[{id:1,home:1,away:2,difficulty_home:2}]}:{}};}};
 vm.createContext(context);const inline=fs.readFileSync('app/player.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];await vm.runInContext(inline,context);
 assert.equal(node('name').textContent,player.name);assert.match(node('summary').innerHTML,/Original MM/);assert.match(node('summary').innerHTML,/5.92/);assert.match(node('gwStrip').innerHTML,/68 min · 84% start/);assert.match(node('drivers').innerHTML,/xMin \(Original MM\)/);assert.equal(requested.includes('mm-vnext-6gw.json'),false,'Experimental minute values must not override original PM profile inputs');
 console.log('PASS original profile: primary xP/minutes/startchance share original snapshot');
})();
