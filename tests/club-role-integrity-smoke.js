/* Role regression against real Clubs page source: never invent tactical roles. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync('app/index.html','utf8');
const start=html.indexOf('function expectedLineup(){');
const end=html.indexOf('function renderHead(){',start);
assert.ok(start>0&&end>start);
const source=html.slice(start,end);
const players=[
 {id:1,player:'GK one',club:'CHE',pos:'GK',gws:[{gw:6,pstart:.97,xmins:89}]},
 ...Array.from({length:6},(_,j)=>({id:j+2,player:'Def '+(j+1),club:'CHE',pos:'DEF',gws:[{gw:6,pstart:.91-j*.035,xmins:75}]})),
 ...Array.from({length:7},(_,j)=>({id:j+8,player:'Mid '+(j+1),club:'CHE',pos:'MID',gws:[{gw:6,pstart:.88-j*.035,xmins:73}]})),
 ...Array.from({length:3},(_,j)=>({id:j+15,player:'Forward '+(j+1),club:'CHE',pos:'FWD',gws:[{gw:6,pstart:.90-j*.04,xmins:72}]})),
];
const dom=new JSDOM('<div id="formationBadge"></div><div id="lineupSub"></div><div id="pitch"></div><div id="xiMinutes"></div><div id="uncertainty"></div><div id="roleBattles"></div>',{url:'http://localhost:8765/index.html?club=CHE'});
const {window}=dom,document=window.document;
const data={forecasts:players,meta:{next_gw:6}};
const escape=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const make=new Function('D','R','roleEvidence','club','ps','nextG','document','window','num','pct','esc',source+'; return {expectedLineup,renderPitch,competitorFor};');
const roleData={current_xi_certified:false,expected_lineups:[],players:[]};
const app=make(data,roleData,()=>null,'CHE',()=>players,p=>p.gws?.[0]||{},document,window,(v,d=1)=>Number(v||0).toFixed(d),
 v=>Math.round(Number(v||0)*100)+'%',escape);
const result=app.expectedLineup();
assert.equal(result.fallback,true);
assert.equal(result.players.length,11);
assert.equal(new Set(result.players.map(x=>x.id)).size,11);
assert.equal(result.players.filter(x=>x.pos==='GK').length,1);
assert.ok(result.players.every(x=>x._role===null));
app.renderPitch();
assert.equal(document.querySelectorAll('#pitch .player-node').length,11);
assert.equal(document.querySelectorAll('#pitch .competitor').length,0);
assert.ok(document.querySelector('#lineupSub').textContent.includes('MM-rolledata mangler'));
assert.ok(document.querySelector('#formationBadge').textContent.includes('Ingen taktisk XI'));
assert.ok([...document.querySelectorAll('#pitch .node-role')].every(n=>n.textContent.startsWith('FPL:')));
assert.ok(![...document.querySelectorAll('#pitch .node-role')].some(n=>/\b(?:CAM|RAM|LDM|RB|ST)\b/.test(n.textContent)));
const sourceRoles=['GK','RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST'];
const explicitPlayers=sourceRoles.map((role,index)=>({id:players[index].id,role}));
roleData.current_xi_certified=true;
roleData.expected_lineups=[{club:'CHE',gw:6,formation:'4-2-3-1',players:explicitPlayers}];
assert.equal(app.expectedLineup().fallback,false);
app.renderPitch();
assert.equal(document.querySelectorAll('#pitch .player-node').length,11);
assert.equal(document.querySelectorAll('#pitch .node-role').length,11);
assert.ok(document.querySelector('#pitch').textContent.includes('CAM'));
assert.ok(document.querySelector('#formationBadge').textContent.includes('4-2-3-1'));
roleData.expected_lineups=[{club:'CHE',gw:6,formation:'4-2-3-1',players:explicitPlayers.map(x=>({...x,role:'MID'}))}];
assert.equal(app.expectedLineup().fallback,true,'FPL MID must not masquerade as tactical role');
roleData.expected_lineups=[{club:'CHE',gw:6,formation:'4-2-3-1',players:explicitPlayers.slice(0,10)}];
assert.equal(app.expectedLineup().fallback,true,'partial role data must not be used');
roleData.expected_lineups=[{club:'CHE',gw:5,formation:'4-2-3-1',players:explicitPlayers}];
assert.equal(app.expectedLineup().fallback,true,'old GW role data must not leak');
console.log('CLUB_ROLE_INTEGRITY_OK: real XI roles respected; absent/invalid/stale roles not invented');
