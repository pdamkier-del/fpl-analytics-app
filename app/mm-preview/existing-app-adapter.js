'use strict';
// Data/URL adapter for COPIES of the established app, never production pages.
(()=>{
 const nativeFetch=window.fetch.bind(window),base=new URL('../',location.href);
 const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
 async function checked(file,sha){const r=await nativeFetch(new URL('current/'+file,base),{cache:'no-store'});if(!r.ok)throw Error('B-previewdata mangler: '+file);const b=await r.arrayBuffer();if(!sha||await digest(b)!==sha)throw Error('B-preview checksumfejl: '+file);return JSON.parse(new TextDecoder().decode(b));}
 let ready=null;
 async function data(){if(!ready)ready=(async()=>{const r=await nativeFetch(new URL('current/index.json',base),{cache:'no-store'});if(!r.ok)throw Error('Aktuelt B-forecast mangler');const i=await r.json();if(i.model!=='B_locked_PM_preview'||i.locked_model_active!==false||i.minute_sampler!=='locked')throw Error('Forkert B-preview-kontrakt');const [f,d]=await Promise.all([checked(i.forecast_file,i.forecast_file_sha256),checked('existing-app-data.json',i.existing_app_data_sha256)]);if(f.forecast_sha256!==i.forecast_sha256||d.forecast_sha256!==i.forecast_sha256)throw Error('B-snapshots er forskellige');setTimeout(()=>{ready=null},60000);return {forecast:f,documents:d.documents};})().catch(e=>{ready=null;throw e});return ready;}
 window.fetch=async(input,options)=>{
  const u=new URL(typeof input==='string'?input:input.url,location.href);
  if(u.origin===location.origin&&u.pathname.startsWith(new URL('app/',base).pathname)&&u.pathname.endsWith('.json')){
   const name=u.pathname.split('/').pop();
   if(name==='vfinal-diagnostic.json'||['current-players.json','live-fixtures.json','club-lineups.json'].includes(name)){
    const d=await data();return new Response(JSON.stringify(name==='vfinal-diagnostic.json'?d.forecast:d.documents[name]),{headers:{'Content-Type':'application/json'}});
   }
   // Never blend old forecast-derived model values into this B snapshot.
   if(name==='fixture-expectations.json')return new Response(JSON.stringify({cutoff:null,fixtures:[]}));
   return nativeFetch(new URL('../../'+name,location.href),options);
  }
  return nativeFetch(input,options);
 };
 document.addEventListener('DOMContentLoaded',()=>{
  const banner=document.createElement('aside');banner.setAttribute('role','status');banner.style.cssText='position:relative;z-index:20;padding:12px;background:#fff1b8;color:#302600;text-align:center';banner.textContent='PREVIEW · Individuel MM B → uændret låst PM → TS v3. Diagnostisk, ikke certificeret. Dit faktiske hold bevares lokalt; forslag er separate.';document.body.prepend(banner);
  data().then(({forecast:f})=>{banner.append(document.createTextNode(' Cutoff '+f.data_asof+'. Minutusikkerhedsintervaller: Not Available (ikke valideret).'));
   const p=f.players.find(p=>p.id===Number(new URLSearchParams(location.search).get('id')));
   if(p){const section=document.createElement('section');section.className='panel';const h=document.createElement('h2');h.textContent='MM B → låst PM · samme snapshot';section.append(h);for(const w of p.weeks){const row=document.createElement('p');row.textContent='GW '+w.gw+' · xM '+w.xmins.toFixed(2)+' · PM E[min] '+w.pm_analytic_minutes.toFixed(2)+' · P(spiller) '+(100*w.p_play).toFixed(1)+' % · xP '+w.xpts.toFixed(2);section.append(row);}const note=document.createElement('p');note.textContent='xM er B-modellens forventning. PM E[min] anvender den uændrede afrundede og afgrænsede Gaussiske sampling og kan derfor afvige. Ingen validerede minutintervaller er tilgængelige.';section.append(note);(document.querySelector('main')||document.body).append(section);}
  }).catch(e=>{banner.textContent='Not Available: '+e.message;});
 });
})();
