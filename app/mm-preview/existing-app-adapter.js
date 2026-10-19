'use strict';
// Data/URL adapter for COPIES of the established app, never production pages.
(()=>{
 const nativeFetch=window.fetch.bind(window),base=new URL('../',location.href);
 const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
 async function checked(file,sha){const r=await nativeFetch(new URL('current/'+file,base),{cache:'no-store'});if(!r.ok)throw Error('B-previewdata mangler: '+file);const b=await r.arrayBuffer();if(!sha||await digest(b)!==sha)throw Error('B-preview checksumfejl: '+file);return JSON.parse(new TextDecoder().decode(b));}
 const publicStats=/\/(players-classic|rankings|current-players|clubs-classic|player)\.html$/.test(location.pathname||new URL(location.href).pathname);
 let probabilities=null;
 async function probabilityData(){if(!probabilities)probabilities=(async()=>{
  const response=await nativeFetch(new URL('gk/index.json',base),{cache:'no-store'});if(!response.ok)throw Error('Sandsynlighedsdata mangler');const i=await response.json();
  async function load(file,key){const r=await nativeFetch(new URL('gk/'+file,base),{cache:'no-store'});if(!r.ok)throw Error('Sandsynlighedsdata mangler');const bytes=await r.arrayBuffer();if(await digest(bytes)!==i[key])throw Error('Checksumfejl i sandsynligheder');return JSON.parse(new TextDecoder().decode(bytes));}
  const [f,m,e]=await Promise.all([load('forecast.json','forecast_sha256'),load('gk-mm.json','mm_sha256'),load('evidence.json','evidence_sha256')]);
  if(!e.role_validation?.accepted||!e.deterministic_repeat||!e.stages?.passed)throw Error('Sandsynligheder er ikke valideret');
  const mm=FplJointGK.validate(f,m);for(const p of f.players)for(const w of p.weeks)for(const x of w.fixtures)FplJointGK.distribution(x.distribution);
  setTimeout(()=>{probabilities=null},60000);return {forecast:f,mm};
 })().catch(e=>{probabilities=null;throw e;});return probabilities;}
 let ready=null;
 async function data(){if(!ready)ready=(async()=>{const r=await nativeFetch(new URL('current/index.json',base),{cache:'no-store'});if(!r.ok)throw Error('Aktuelt B-forecast mangler');const i=await r.json();if(i.model!=='B_locked_PM_preview'||i.locked_model_active!==false||i.minute_sampler!=='locked')throw Error('Forkert B-preview-kontrakt');const [f,d]=await Promise.all([checked(i.forecast_file,i.forecast_file_sha256),checked('existing-app-data.json',i.existing_app_data_sha256)]);if(f.forecast_sha256!==i.forecast_sha256||d.forecast_sha256!==i.forecast_sha256)throw Error('B-snapshots er forskellige');setTimeout(()=>{ready=null},60000);if(i.desktop_probabilities&&publicStats){const p=await probabilityData();if(p.forecast.forecast_sha256!==i.desktop_probabilities.forecast_sha256)throw Error('Forskellige sandsynlighedssnapshots');
 const catalogue=new Map(d.documents['current-players.json'].players.map(p=>[p.id,p]));
 if(catalogue.size!==p.forecast.players.length||p.forecast.players.some(p=>{const q=catalogue.get(p.id);return !q||q.team!==p.team_id||q.position!==p.position||Math.abs(q.price*10-p.price_tenths)>1e-6;}))throw Error('Forskellige spillerkataloger');
 const docs=JSON.parse(JSON.stringify(d.documents));for(const doc of Object.values(docs)){doc.snapshot_sha256=p.forecast.forecast_sha256;if(doc.forecast_sha256)doc.forecast_sha256=p.forecast.forecast_sha256;if(doc.cutoff)doc.cutoff=p.forecast.data_asof;}
 return {forecast:p.forecast,documents:docs};}return {forecast:f,documents:d.documents};})().catch(e=>{ready=null;throw e});return ready;}
 window.fetch=async(input,options)=>{
  const u=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
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
 window.FplBExistingApp={probabilities:probabilityData,publicStats,forecast:async()=>{ready=null;return (await data()).forecast;}};
 document.addEventListener('DOMContentLoaded',()=>{
  const banner=document.createElement('aside');banner.setAttribute('role','status');banner.style.cssText='position:relative;z-index:20;padding:12px;background:#fff1b8;color:#302600;text-align:center';banner.textContent='PREVIEW · Individuel MM B → uændret låst PM → TS v3. Diagnostisk, ikke certificeret. Dit faktiske hold bevares lokalt; forslag er separate.';document.body.prepend(banner);
  data().then(({forecast:f})=>{if(publicStats&&f.model==='B-GK-role-aware-v2'){banner.textContent='B-preview · FPL Analytics · sandsynligheder i det eksisterende spillerkort';return;}banner.append(document.createTextNode(' Cutoff '+f.data_asof+'. Minutusikkerhedsintervaller: Not Available (ikke valideret).'));
   const p=f.players.find(p=>p.id===Number(new URLSearchParams(location.search).get('id')));
   if(p){const section=document.createElement('section');section.className='panel';const h=document.createElement('h2');h.textContent='MM B → låst PM · samme snapshot';section.append(h);
    // Reuse the normal app freshness gate; the catalogue is the same sealed document.
    data().then(d=>{const check=FplForecastWindow.check(f,d.documents['current-players.json']);if(!check.usable){section.append(document.createTextNode('Not Available: '+check.reason));return;}for(const w of p.weeks){const row=document.createElement('p');row.textContent='GW '+w.gw+' · xM '+w.xmins.toFixed(2)+' · PM E[min] '+w.pm_analytic_minutes.toFixed(2)+' · P(spiller) '+(100*w.p_play).toFixed(1)+' % · xP '+w.xpts.toFixed(2);section.append(row);}});const note=document.createElement('p');note.textContent='xM er B-modellens forventning. PM E[min] anvender den uændrede afrundede og afgrænsede Gaussiske sampling og kan derfor afvige. Ingen validerede minutintervaller er tilgængelige.';section.append(note);(document.querySelector('main')||document.body).append(section);}
  }).catch(e=>{banner.textContent='Not Available: '+e.message;});
 });
})();
