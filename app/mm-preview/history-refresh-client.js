'use strict';
(function(root){
 const BASE='https://fpl-analytics-private-manager.onrender.com',KEY='fpl-history-refresh-job-v1';let active=null;
 function pending(){try{const p=JSON.parse(sessionStorage.getItem(KEY));return p&&/^[a-f0-9]{32}$/.test(p.id)&&/^[A-Za-z0-9_-]{43}$/.test(p.key)&&Number.isInteger(p.entry_id)&&Date.now()-p.created<3600000?p:null}catch{return null}}
 async function readJSON(url,options={}){let r;try{r=await fetch(url,{cache:'no-store',...options,signal:AbortSignal.timeout(90000)})}catch{throw Error('Der kunne ikke oprettes forbindelse til historiktjenesten. Serveren kan være ved at starte. Prøv igen om lidt.')}const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(data.error||(r.status===404&&url===BASE+'/preview/history'?'Opdateringsfunktionen er endnu ikke aktiveret på serveren':'Data kunne ikke hentes. Prøv igen senere.'));return data}
 function run({entryId,season,onProgress=()=>{}}){
  if(active&&active.entryId===entryId&&active.season===season){active.listeners.add(onProgress);if(active.last)onProgress(active.last);return active.promise}
  const job={entryId,season,listeners:new Set([onProgress]),last:null};active=job;const update=data=>{job.last=data;job.listeners.forEach(fn=>fn(data))};
  job.promise=(async()=>{
   update({stage:'connection'});const health=await readJSON(BASE+'/health');if(health.supports_full_history_refresh!==true)throw Error('Den komplette historikfunktion er endnu ikke aktiveret på serveren. Et Render-deploy er nødvendigt.');
   let receipt=pending();if(!receipt||receipt.entry_id!==entryId||receipt.season!==season){receipt=await readJSON(BASE+'/preview/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entry_id:entryId,season})});if(!/^[a-f0-9]{32}$/.test(receipt.id)||!/^[A-Za-z0-9_-]{43}$/.test(receipt.key))throw Error('Ugyldig privat jobkvittering');receipt={...receipt,entry_id:entryId,season,created:Date.now()};sessionStorage.setItem(KEY,JSON.stringify(receipt))}
   update({stage:'history'});
   for(let i=0;i<1200;i++){let result;try{result=await readJSON(BASE+'/plans/'+receipt.id,{headers:{'X-Plan-Key':receipt.key}})}catch(error){if(!/forbindelse/.test(error.message))sessionStorage.removeItem(KEY);throw error}if(result.status==='completed'){if(result.history?.entry_id!==entryId)throw Error('Historikken tilhører et andet manager-ID');return result.history}if(result.status!=='running'){sessionStorage.removeItem(KEY);throw Error('Historikopdateringen kunne ikke afsluttes')}update({stage:result.stage||'history',gw:result.gw,completed_gws:result.completed_gws,total_gws:result.total_gws});await new Promise(resolve=>setTimeout(resolve,1500))}
   throw Error('Opdateringen kører stadig. Åbn siden igen for at fortsætte med samme private job.');
  })().finally(()=>{if(active===job)active=null});return job.promise;
 }
 root.FplHistoryRefreshClient={run,readJSON,pending,acknowledge:()=>sessionStorage.removeItem(KEY)};
})(typeof window==='object'?window:globalThis);
