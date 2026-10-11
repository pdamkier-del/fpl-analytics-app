const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/weekly-app.js','utf8');
const functions=source.slice(source.indexOf('function showComputeStatus()'),source.indexOf('async function load()'));
const stored=new Map([['fpl-private-job',JSON.stringify({id:'example',key:'private',forecast_cutoff:'old',manager_state_sha256:'state'})]]);
const context={document:{getElementById:()=>null},busy:false,computeMessage:'',computeError:false,state:{},stateLegal:()=>true,usable:true,service:{url:'https://example.invalid'},forecast:{data_asof:'new'},official:{},AbortController,
 sessionStorage:{getItem:k=>stored.get(k),removeItem:k=>stored.delete(k),setItem:(k,v)=>stored.set(k,v)},
 localStorage:{setItem:()=>{throw Error('Stale result must never be saved')}},hash:async()=> 'state',FplForecastWindow:{check:()=>({usable:true})},
 setTimeout:fn=>{queueMicrotask(fn);return 0},clearTimeout:()=>{},fetch:async()=>{throw Error('disconnected')}};
vm.createContext(context);vm.runInContext(functions,context);
(async()=>{
 await assert.rejects(context.boundedFetch('https://example.invalid'),/Forbindelsen blev afbrudt/);
 assert.ok(stored.has('fpl-private-job'));
 context.fetch=async()=>{const e=Error('timeout');e.name='AbortError';throw e};
 await assert.rejects(context.boundedFetch('https://example.invalid'),/timeout/);
 // A completed job on an old cutoff is rejected after the forecast changes.
 stored.set('fpl-private-job',JSON.stringify({id:'example',key:'private',forecast_cutoff:'new',manager_state_sha256:'state'}));
 context.fetch=async url=>url.endsWith('/health')?{ok:true,json:async()=>({runtime:'original_locked_python',locked_model_active:false})}:{ok:true,json:async()=>({status:'completed',plan:{forecast_cutoff:'old',manager_state_sha256:'state',locked_model_active:false}})};
 await context.compute();assert.match(context.computeMessage,/Forecast eller hold er ændret/);assert.equal(stored.has('fpl-private-job'),false);assert.equal(context.busy,false);
 const realState={squad:[{id:1,purchase_price_tenths:45}],bank_tenths:7};
 context.localStorage={getItem:k=>k==='fpl-manager-state-v1'?JSON.stringify(realState):'{invalid plan'};
 vm.runInContext(source.slice(source.indexOf('async function readSaved()'),source.indexOf('function missing(')),context);
 await context.readSaved();assert.deepEqual(JSON.parse(JSON.stringify(context.state)),realState);assert.equal(context.plan,null);
 console.log('PASS: timeout and disconnect preserve jobs; changed forecasts reject completed stale results.');
})().catch(e=>{console.error(e);process.exitCode=1});
