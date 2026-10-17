'use strict';
const assert=require('assert'),client=require('../app/mm-preview/job-client.js');
(async()=>{
 let checks=0;
 for(const status of [404,410,422]){
  const fetcher=async()=>({ok:false,status,json:async()=>({error:'Terminal job failure'})});
  await assert.rejects(()=>client.request('/plans/test',{},1000,fetcher),e=>{assert.equal(e.message,'Terminal job failure');assert.equal(e.httpStatus,status);assert(client.terminal(e));return true;});checks++;
 }
 const retryable=async()=>({ok:false,status:429,json:async()=>({error:'Optaget'})});
 await assert.rejects(()=>client.request('/plans/test',{},1000,retryable),e=>!client.terminal(e)&&e.httpStatus===429);checks++;
 const reset=async()=>{throw TypeError('Connection reset');};
 await assert.rejects(()=>client.request('/plans/test',{},1000,reset),e=>!client.terminal(e)&&e.message==='Connection reset');checks++;
 const waiting=(_,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(Error('aborted'),{name:'AbortError'}))));
 await assert.rejects(()=>client.request('/plans/test',{},1,waiting),e=>!client.terminal(e)&&e.message.includes('hold og job er bevaret'));checks++;
 const success=async(url,options)=>{assert.equal(options.cache,'no-store');assert(options.signal);return {ok:true,json:async()=>({status:'completed'})};};
 assert.deepEqual(await client.request('/plans/test',{},1000,success),{status:'completed'});checks++;
 console.log('B preview jobs: '+checks+' failure/retry/timeout/response checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
