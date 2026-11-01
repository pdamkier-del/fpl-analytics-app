'use strict';
// Browser-only synthetic state, no real private POSTs or official FPL action.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const base=process.env.DESKTOP_URL,fixture=JSON.parse(fs.readFileSync(process.env.DASHBOARD_TEST_FIXTURE));
 assert(base,'DESKTOP_URL is required');
 const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const report={};
 try{for(const [name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let posts=0,reference=null;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/plans**',route=>{if(route.request().method()==='POST'){posts++;return route.abort();}return route.continue();});
  await context.addInitScript(state=>{localStorage.setItem('fpl-manager-state-v1',JSON.stringify(state));localStorage.setItem('fpl-B-news-auto-plan-v1','false');},fixture.state);
  const routes=['players-classic.html?mode=forecast&horizon=1','player.html?id='+fixture.state.squad[0].id,'my-team-classic.html','transfers-classic.html'];
  for(const route of routes){
   await page.goto(base+route,{waitUntil:'networkidle'});
   const actual=await page.evaluate(async()=>{
    const f=await FplBExistingApp.forecast(),q=await FplBExistingApp.probabilities();
    const p=f.players.find(p=>p.name==='Penders'&&p.team==='Chelsea');
    const manager=typeof FplManagerClient==='undefined'?null:FplManagerClient.snapshot().forecast;
    return {model:f.model,forecast:f.forecast_sha256,panel:q.forecast.forecast_sha256,planner:manager?.forecast_sha256,
     weeks:p.weeks.map(w=>({gw:w.gw,xm:w.xmins,pm:w.pm_analytic_minutes,xp:w.xpts})),
     saved:JSON.parse(localStorage.getItem('fpl-manager-state-v1')),overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert.equal(actual.model,'B-MM-PM-TS-v1');assert.equal(actual.forecast,actual.panel);
   if(actual.planner)assert.equal(actual.planner,actual.forecast);
   for(const w of actual.weeks)assert(Math.abs(w.xm-w.pm)<1e-7);
   const identity={hash:actual.forecast,weeks:actual.weeks};
   if(reference)assert.deepEqual(identity,reference);else reference=identity;
   assert.deepEqual(actual.saved,fixture.state);assert.equal(actual.overflow,false,name+' '+route+' horizontal overflow');
  }
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  report[name]={routes:routes.length,forecast_sha256:reference.hash,identical_panel_and_planner:true,
   MM_PM_minutes_equal:true,manager_state_unchanged:true,real_private_posts:posts,page_errors:errors};
  await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(report,null,2));
})().catch(error=>{console.error(error);process.exit(1)});
