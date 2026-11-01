'use strict';
// Private synthetic remote receipt stays local; only aggregate assertions print.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const receipt=JSON.parse(fs.readFileSync(process.env.REMOTE_RECEIPT));
 const plan=JSON.parse(fs.readFileSync(process.env.REMOTE_RESULT));
 assert.equal(plan.validation_only,true);assert.equal(plan.calculation_runtime,'B_unified_python');
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const proof={};
 try{for(const [name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/plans**',r=>{if(r.request().method()==='POST'){posts++;return r.abort();}return r.continue();});
  await context.addInitScript(({state,plan})=>{
   if(!sessionStorage.getItem('remote-display-seeded')){
    localStorage.setItem('fpl-manager-state-v1',JSON.stringify(state));
    localStorage.setItem('fpl-manager-plan-B-preview-v1',JSON.stringify(plan));
    sessionStorage.setItem('remote-display-seeded','1');
   }
   localStorage.setItem('fpl-B-news-auto-plan-v1','false');
  },{state:receipt.body.state,plan});
  await page.goto('https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html',{waitUntil:'networkidle'});
  await page.locator('#planner-context').waitFor();
  assert.equal(await page.evaluate(()=>FplManagerClient.snapshot().plan),null,
   'A synthetic validation result must not be accepted as a real personal plan');
  // Display-only clone: unchanged numbers, never saved outside this test context.
  const displayState=await page.evaluate(async({state,plan})=>{
   const copy={...state};delete copy.validation_only;
   const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(ordered(copy)))))].map(x=>x.toString(16).padStart(2,'0')).join('');
   localStorage.setItem('fpl-manager-state-v1',JSON.stringify(copy));
   localStorage.setItem('fpl-manager-plan-B-preview-v1',JSON.stringify({...plan,validation_only:false,manager_state_sha256:digest}));
   return copy;
  },{state:receipt.body.state,plan});
  await page.reload({waitUntil:'networkidle'});
  await page.locator('#planner-context').waitFor();
  const readiness=await page.evaluate(()=>{const s=FplManagerClient.snapshot();return {hasPlan:!!s.plan,usable:s.usable,stateValid:s.stateValid,reason:s.reason};});
  assert.equal(readiness.hasPlan,true,JSON.stringify(readiness));
  await page.locator('#transfer-path').waitFor({state:'attached'});
  assert.match(await page.locator('#planner-context').innerText(),/Plan klar/);
  const shown=await page.evaluate(()=>FplManagerClient.snapshot().plan);
  assert.equal(shown.forecast_sha256,plan.forecast_sha256);
  assert.deepEqual(shown.plan.path,plan.plan.path);
  if(plan.forecast_policy==='latest_verified_snapshot_v1'){
   assert.equal(shown.model_asof,plan.model_asof);assert.equal(shown.prices_asof,plan.prices_asof);
   const info=await page.locator('#latest-snapshot-info').innerText();
   assert(info.includes(new Date(plan.model_asof).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'})));
   assert.match(info,/Nyere skader og prisændringer/);
  }
  await page.locator('#transfer-path > summary').click();
  assert((await page.locator('#transfer-path').innerText()).includes(''+plan.plan.path.at(-1).gw));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('fpl-manager-state-v1'))),displayState);
  await page.screenshot({path:'/tmp/fpl-ready-remote-plan-'+name+'.png',fullPage:true});
  await page.goto('https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/overview.html#dashboard',{waitUntil:'networkidle'});
  await page.locator('#dashboard-team-news').waitFor();
  assert.equal(await page.locator('[data-plan-phase]').getAttribute('data-plan-phase'),'ready');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'/tmp/fpl-ready-dashboard-'+name+'.png',fullPage:true});
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  proof[name]={synthetic_result_rejected_as_personal:true,browser_only_presentation_copy:true,
   synthetic_only_presentation_state:true,remote_result_numbers_displayed:true,six_GW_path_identical:true,dashboard_plan_ready:true,
   forecast_sha256:plan.forecast_sha256,forecast_policy:plan.forecast_policy||null,model_asof:plan.model_asof||null,private_state_unchanged:true,additional_jobs:posts,page_errors:errors};
  await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(proof,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
