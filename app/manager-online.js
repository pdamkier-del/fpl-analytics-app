'use strict';
(()=>{
 const $=id=>document.getElementById(id),repo='pdamkier-del/fpl-analytics-app',branch='free-github-static-20261010';
 fetch('https://api.github.com/repos/'+repo+'/contents/app/diagnostic-pipeline-status.json?ref='+branch,{cache:'no-store',headers:{Accept:'application/vnd.github+json'}}).then(r=>r.ok?r.json():null).then(file=>{if(!file)return;const info=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\s/g,'')),c=>c.charCodeAt(0))));const p=$('pipelineStatus');p.textContent='Seneste automatiske forecastforsøg: '+info.status+' · '+info.observed_at+'. ';const link=document.createElement('a');link.href=info.workflow;link.textContent='Se kørsel';link.target='_blank';link.rel='noopener noreferrer';p.append(link);if(info.status!=='success')p.append(document.createTextNode(' Sidste verificerede forecast bevares og kontrolleres for alder og GW.'))}).catch(()=>{});
 const from64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
 async function open(envelope,privateKey){
  if(envelope.version!==1||envelope.algorithm!=='RSA-OAEP-256+A256GCM')throw Error('Ugyldigt krypteret svar');
  const raw=await crypto.subtle.decrypt({name:'RSA-OAEP'},privateKey,from64(envelope.key));
  const key=await crypto.subtle.importKey('raw',raw,'AES-GCM',false,['decrypt']);
  return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:from64(envelope.nonce),additionalData:new TextEncoder().encode('fpl-manager-result-v1')},key,from64(envelope.ciphertext))));
 }
 window.FplEncryptedManagerResult={open};
 $('calculateOnline').onclick=async()=>{
  const button=$('calculateOnline'),status=$('onlineStatus');button.disabled=true;
  try{
   const raw=FplManagerOnline.getState(),token=$('githubToken').value.trim();
   if(!token)throw Error('Angiv et afgrænset GitHub-token med Actions: Read and write');
   localStorage.setItem('fpl-manager-state-v1',JSON.stringify(raw));
   const pair=await crypto.subtle.generateKey({name:'RSA-OAEP',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['encrypt','decrypt']);
   const requestId=crypto.randomUUID(),publicKey=await crypto.subtle.exportKey('jwk',pair.publicKey);
   const api=async(path,options={})=>fetch('https://api.github.com/repos/'+repo+'/'+path,{...options,cache:'no-store',headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','Content-Type':'application/json'}});
   status.textContent='Sender hold-state til original Python-beregning…';
   const response=await api('actions/workflows/live-manager-plan.yml/dispatches',{method:'POST',body:JSON.stringify({ref:'main',inputs:{forecast_cutoff:FplManagerOnline.getForecast().data_asof,manager_state_json:JSON.stringify(raw),request_id:requestId,public_key_json:JSON.stringify(publicKey)}})});
   if(!response.ok)throw Error('GitHub afviste beregningen ('+response.status+'). Kontrollér repo-adgang og Actions-rettighed.');
   let run=null;if(response.status!==204)run=await response.json();
   const link=document.createElement('a');link.href=run?.html_url||'https://github.com/'+repo+'/actions/workflows/live-manager-plan.yml';link.target='_blank';link.rel='noopener noreferrer';link.textContent='Åbn kørsel';
   status.replaceChildren(document.createTextNode('Beregningen kører. Behold denne fane åben. '),link);
   for(let i=0;i<180;i++){
    await new Promise(resolve=>setTimeout(resolve,10000));
    const result=await api('contents/app/manager-results/'+requestId+'.json?ref='+branch);
    if(result.ok){const file=await result.json();const plan=await open(JSON.parse(new TextDecoder().decode(from64(file.content.replace(/\s/g,'')))),pair.privateKey);await FplManagerOnline.acceptPlan(plan);status.textContent='Dit originale TS v3- og chipresultat er klar · diagnostisk.';return}
    if(result.status!==404)throw Error('Resultatet kunne ikke hentes ('+result.status+')');
    if(run?.workflow_run_id&&i%3===0){const r=await api('actions/runs/'+run.workflow_run_id);if(r.ok){const state=await r.json();if(state.status==='completed'&&state.conclusion!=='success')throw Error('Beregningen fejlede. Se kørslens log; ingen anbefaling er publiceret.')}}
   }
   throw Error('Resultatet er endnu ikke klar. Se kørsel og importér resultatet manuelt.');
  }catch(e){status.textContent='Not Available: '+e.message}finally{button.disabled=false;$('githubToken').value=''}
 };
})();
