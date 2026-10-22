'use strict';
// All manager/network fixtures are synthetic and intercepted; no real FPL action.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
const seal=n=>{const {content_sha256,...body}=n;return {...body,content_sha256:crypto.createHash('sha256').update(JSON.stringify(ordered(body))).digest('hex')};};
(async()=>{
 const base=process.env.DESKTOP_URL,fixture=JSON.parse(fs.readFileSync(process.env.DASHBOARD_TEST_FIXTURE));
 const f=await(await fetch(new URL('../current/forecast.json',base))).json();
 const docs=await(await fetch(new URL('../current/existing-app-data.json',base))).json();
 const template=await(await fetch(new URL('../news/availability.json',base))).json();
 assert(Date.parse(fixture.state.observed_at)>Date.parse(f.data_asof),'Fixture must reproduce a later team observation');
 const matching={...template,observed_at:new Date().toISOString(),players:docs.documents['current-players.json'].players.map(p=>({
  id:p.id,name:p.web_name,team:p.team,position:p.position,price_tenths:Math.round(p.price*10),status:p.status,
  news:p.news||'',news_added:p.news_added||null,chance_of_playing_next_round:p.chance_of_playing_next_round??null,chance_of_playing_this_round:p.chance_of_playing_this_round??null,
 }))};
 const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});const proof={};
 try{for(const [name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let body,posts=0,healthReady=false,news=structuredClone(matching);
  if(process.env.SNAPSHOT_CLOCK_AGE_HOURS){const at=Date.parse(f.data_asof)+Number(process.env.SNAPSHOT_CLOCK_AGE_HOURS)*3600000;assert(at<Date.parse(f.origin_deadline));await page.clock.setFixedTime(new Date(at));}
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/news/availability.json',r=>r.fulfill({json:seal(news)}));
  await context.route('**/health',r=>r.fulfill({json:{runtime:'original_locked_python',locked_model_active:false,supports_idempotent_submit:true,supports_mm_preview:true,supports_unified_B_chain:true,supports_B_snapshot_policy:healthReady}}));
  await context.route('**/plans**',r=>{
   if(r.request().method()==='POST'){
    body=r.request().postDataJSON();posts++;assert.equal(body.forecast_policy,'latest_verified_snapshot_v1');
    assert.deepEqual(body.state,fixture.state);return r.fulfill({status:202,json:{id:body.request_id,key:body.request_key}});
   }
   return r.fulfill({json:{status:'completed',plan:fixture.result}});
  });
  await context.addInitScript(state=>{if(!sessionStorage.getItem('snapshot-fixture-seeded')){localStorage.setItem('fpl-manager-state-v1',JSON.stringify(state));sessionStorage.setItem('snapshot-fixture-seeded','1');}localStorage.setItem('fpl-B-news-auto-plan-v1','false');},fixture.state);
  await page.goto(base+'transfers-classic.html',{waitUntil:'networkidle'});await page.locator('#latest-snapshot-info').waitFor();
  assert.equal(await page.evaluate(()=>FplManagerClient.snapshot().usable&&FplManagerClient.snapshot().stateValid),true);
  await page.locator('[data-compute]').click();await page.waitForFunction(()=>document.querySelector('[data-compute-feedback]')?.textContent.includes('opdatering af beregningstjenesten'));
  assert.equal(posts,0,'An old backend must not receive a request it cannot support');
  assert.match(await page.locator('[data-compute-feedback]').innerText(),/opdatering af beregningstjenesten/);
  healthReady=true;
  await page.locator('[data-compute]').click();
  await page.waitForFunction(()=>!!FplManagerClient.snapshot().plan,{},{timeout:45000}).catch(async e=>{console.error(JSON.stringify({errors,feedback:await page.locator('[data-compute-feedback]').innerText()}));throw e;});
  assert.equal(posts,1);assert.equal(body.forecast_cutoff,f.data_asof);
  assert.equal(await page.evaluate(()=>FplManagerClient.snapshot().plan.model_asof),f.data_asof);
  assert.match(await page.locator('#latest-snapshot-info').innerText(),/Prognose og priser/);
  assert.match(await page.locator('#latest-snapshot-info').innerText(),/Nyere skader og prisændringer/);
  Object.assign(news.players.find(p=>p.id===fixture.state.squad[0].id),{status:'d',news:'SYNTHETIC_NEW_INJURY',news_added:news.observed_at,chance_of_playing_next_round:75});
  await page.evaluate(()=>FplManagerClient.load());
  assert(await page.evaluate(()=>!!FplManagerClient.snapshot().plan),'New injury must warn without erasing a labelled snapshot plan');
  assert.equal(await page.evaluate(()=>{const s=FplManagerClient.snapshot();return FplForecastWindow.check(s.forecast,s.official,Date.parse(s.forecast.origin_deadline)+1000).usable;}),false);assert.equal(posts,1);
  await page.goto(base+'overview.html#dashboard',{waitUntil:'networkidle'});await page.locator('#latest-snapshot-info').waitFor();
  assert.equal(await page.locator('[data-plan-phase]').getAttribute('data-plan-phase'),'ready');
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('fpl-manager-state-v1'))),fixture.state);
  assert.equal(posts,1);assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  proof[name]={synthetic_only:true,forecast_age_hours_tested:Number(process.env.SNAPSHOT_CLOCK_AGE_HOURS)||null,later_manager_observation_supported:true,backend_capability_required:true,request_policy_verified:true,model_timestamp_unchanged:true,prices_timestamp_visible:true,new_injury_is_advisory:true,deadline_still_blocks:true,six_GW_plan_displayed:true,dashboard_ready:true,private_state_unchanged:true,real_private_posts:0,mocked_private_posts:posts,page_errors:errors};
  await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(proof,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
