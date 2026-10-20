'use strict';
(function(root){
 // A 429 is not an accepted job. Reuse the same private id/key until accepted.
 async function submit({url,body,request,onWait,beforeRetry,wait=ms=>new Promise(r=>setTimeout(r,ms)),now=Date.now,maxWaitMs=35*60*1000}){
  const started=now(),payload=JSON.stringify(body);let attempts=0;
  for(;;){
   if(attempts&&await beforeRetry()===false)return null;
   const response=await request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:payload});
   if(![429,503].includes(response.status))return response;
   const elapsed=now()-started;if(elapsed>=maxWaitMs)throw Error('Beregningstjenesten er stadig optaget. Din forespørgsel er bevaret; tryk Vis nyeste transferplan for at prøve igen.');
   const header=response.headers?.get('Retry-After'),seconds=header&&/^\d+$/.test(header)?Math.max(1,Math.min(60,Number(header))):Math.min(30,10+attempts*5);
   const delay=Math.min(seconds*1000,maxWaitMs-elapsed);onWait(Math.ceil(delay/1000));
   // Drain the small rejection response before the next attempt.
   if(response.text)await response.text();await wait(delay);attempts++;
  }
 }
 const api={submit};root.FplPreviewCapacity=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
