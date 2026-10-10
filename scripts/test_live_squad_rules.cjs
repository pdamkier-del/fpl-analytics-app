// Exercise the real rules embedded in the current-squad page, without DOM/network.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('app/my-team-live.html','utf8');
const script=[...src.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(x=>x[1]).find(x=>x.includes('function legalXI'));
assert.ok(script,'Current squad source missing');
const start=script.indexOf('const KEY='),end=script.indexOf("$('auto').addEventListener");
assert.ok(start>0 && end>start,'Cannot isolate squad rules');
const sandbox={};
vm.createContext(sandbox);
vm.runInContext(script.slice(start,end)+'\nthis.check={positions,legalXI,validSquad}',sandbox);
const {legalXI,validSquad}=sandbox.check;
const players=[];
function add(pos,n,clubStart){for(let i=0;i<n;i++)players.push({id:players.length+1,position:pos,team:clubStart+(i%5)})}
add(1,2,1);add(2,5,6);add(3,5,11);add(4,3,16);
assert.equal(players.length,15);
assert.equal(validSquad(players),true);
const lineup=[players[0],...players.filter(p=>p.position===2).slice(0,4),...players.filter(p=>p.position===3).slice(0,4),...players.filter(p=>p.position===4).slice(0,2)];
assert.equal(legalXI(lineup),true,'4-4-2 must be valid');
assert.equal(legalXI([players[0],...players.filter(p=>p.position===2).slice(0,2),...players.filter(p=>p.position===3).slice(0,5),...players.filter(p=>p.position===4)]),false,'Two DEF invalid');
assert.equal(validSquad([...players,players[0]]),false,'Duplicate squad invalid');
const fourClub=players.slice(0,4).map((p,i)=>({...p,team:123}));
assert.equal(validSquad([...fourClub,...players.slice(4)]),false,'Max 3 from one club');
console.log('PASS: current squad exact quotas, 4-4-2, illegal XI, duplicate IDs, club maximum.');
