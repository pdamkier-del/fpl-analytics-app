/* Exercise cold-start locking and progress across replacement DOM nodes. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/weekly-app.js','utf8');
const functions=source.slice(source.indexOf('function showComputeStatus()'),source.indexOf('async function load()'));
let nodes={'compute-status':{textContent:'',className:''},compute:{disabled:false}},calls=0,resolveHealth;
const context={document:{getElementById:id=>nodes[id]},busy:false,computeMessage:'',computeError:false,state:{},stateLegal:()=>true,usable:true,service:{url:'https://test.invalid'},AbortController,setTimeout,clearTimeout,fetch:()=>{calls++;return new Promise(resolve=>resolveHealth=resolve)}};
vm.createContext(context);vm.runInContext(functions,context);
(async()=>{
 const first=context.compute();await context.compute();
 assert.equal(calls,1);assert.equal(nodes.compute.disabled,true);
 nodes={'compute-status':{textContent:'',className:''},compute:{disabled:true}};
 context.showComputeStatus();assert.match(nodes['compute-status'].textContent,/90 sekunder/);
 resolveHealth({ok:false,status:503});await first;
 assert.equal(nodes.compute.disabled,false);assert.match(nodes['compute-status'].textContent,/Not Available/);assert.equal(nodes['compute-status'].className,'error');
 console.log('Weekly compute: duplicate cold starts blocked; progress and retry survive DOM replacement.');
})().catch(e=>{console.error(e);process.exitCode=1});
