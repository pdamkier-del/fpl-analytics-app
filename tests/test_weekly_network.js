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
 context.fetch=async url=>url.endsWith('/health')?{ok:true,json:async()=>({runtime:'original_locked_python',locked_model_active:false,supports_idempotent_submit:true})}:{ok:true,json:async()=>({status:'completed',plan:{forecast_cutoff:'old',manager_state_sha256:'state',locked_model_active:false}})};
 await context.compute();assert.match(context.computeMessage,/Forecast eller hold er ændret/);assert.equal(stored.has('fpl-private-job'),false);assert.equal(context.busy,false);
 const realState={squad:[{id:1,purchase_price_tenths:45}],bank_tenths:7};
 context.localStorage={getItem:k=>k==='fpl-manager-state-v1'?JSON.stringify(realState):'{invalid plan'};
 vm.runInContext(source.slice(source.indexOf('async function readSaved()'),source.indexOf('function missing(')),context);
 await context.readSaved();assert.deepEqual(JSON.parse(JSON.stringify(context.state)),realState);assert.equal(context.plan,null);
 // Losing the POST response must not lose the capability needed to retry it.
 const receipts=new Map(),postBodies=[];let disconnect=true,accepted=false;
 const second={...context,state:{},busy:false,crypto:require('node:crypto').webcrypto,btoa,readSaved:async()=>{},render:()=>{},
  sessionStorage:{getItem:k=>receipts.get(k),setItem:(k,v)=>receipts.set(k,v),removeItem:k=>receipts.delete(k)},localStorage:{setItem:()=>{accepted=true}}};
 second.fetch=async(url,options)=>{
  if(url.endsWith('/health'))return {ok:true,json:async()=>({runtime:'original_locked_python',locked_model_active:false,supports_idempotent_submit:true})};
  if(options?.method==='POST'){const body=JSON.parse(options.body);postBodies.push(body);assert.ok(receipts.has('fpl-private-job'));if(disconnect){disconnect=false;throw Error('lost response')}return {ok:true,json:async()=>({id:body.request_id,key:body.request_key})};}
  return {ok:true,json:async()=>({status:'completed',plan:{forecast_cutoff:'new',manager_state_sha256:'state',locked_model_active:false}})};
 };
 vm.createContext(second);vm.runInContext(functions,second);await second.compute();
 assert.equal(JSON.parse(receipts.get('fpl-private-job')).submitted,false);
 await second.compute();assert.equal(accepted,true);assert.equal(postBodies.length,2);
 assert.equal(postBodies[0].request_id,postBodies[1].request_id);assert.equal(postBodies[0].request_key,postBodies[1].request_key);
 console.log('PASS: timeout and disconnect preserve jobs; changed forecasts reject completed stale results.');
})().catch(e=>{console.error(e);process.exitCode=1});

// Dashboard sums only the actual saved XI and extra captain points; never treats absent/stale data as zero.
{const branch=source.slice(source.indexOf(' const first=plan?.plan.path[0],chosen='),source.indexOf(" }else if(route==='players')"));const people=new Map(Array.from({length:15},(_,i)=>[i+1,{id:i+1,name:'Validation player '+(i+1),weeks:[7,8,9,10,11,12].map(gw=>({gw,xpts:2}))}]));const selected={ids:[...people.keys()],captain:1,vice:2};const ctx={html:'',driftPanel:'',notice:()=>'',plan:null,people,forecast:{gws:[7,8,9,10,11,12],data_asof:'2026-10-12T10:00:00Z',origin_deadline:'2026-10-17T10:00:00Z'},official:{next_gw:7,fetched_at:'2026-10-12T10:00:00Z',teams:{}},fixtures:{fixtures:[]},state:{squad:[...people.keys()],gw:7,bank_tenths:7,free_transfers:2,observed_at:'2026-10-11T10:00:00Z'},savedSelection:()=>selected,stateLegal:()=>true,validSelection:()=>true,usable:true,week:(p,g)=>p?.weeks?.find(w=>w.gw===g),esc:String,n:x=>Number.isFinite(x)?x.toFixed(2):'Not Available',metric:(k,v)=>k+':'+v,missing:()=>'<p>Missing current plan</p>'};vm.createContext(ctx);vm.runInContext(branch,ctx);assert.match(ctx.html,/Min gemte XI \+ kaptajn:24.00 xP/);assert.match(ctx.html,/Samme XI · seks GW:144.00 xP/);assert.match(ctx.html,/Missing current plan/);ctx.usable=false;ctx.html='';vm.runInContext('{'+branch+'}',ctx);assert.match(ctx.html,/Min gemte XI \+ kaptajn:Not Available/);assert.doesNotMatch(ctx.html,/24.00 xP/);ctx.usable=true;people.get(1).weeks[0].xpts=null;ctx.html='';vm.runInContext('{'+branch+'}',ctx);assert.match(ctx.html,/Min gemte XI \+ kaptajn:Not Available/);assert.equal(ctx.state.bank_tenths,7);}
