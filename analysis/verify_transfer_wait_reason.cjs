'use strict';
// Synthetic browser-only news/state cases; no real manager job is submitted.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),crypto=require('node:crypto');
const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
const seal=n=>{const {content_sha256,...body}=n;return {...body,content_sha256:crypto.createHash('sha256').update(JSON.stringify(ordered(body))).digest('hex')};};
(async()=>{
 const base=process.env.DESKTOP_URL,fixture=JSON.parse(fs.readFileSync(process.env.DASHBOARD_TEST_FIXTURE));
 const doc=await (await fetch(new URL('../current/existing-app-data.json',base))).json();
 const forecast=await (await fetch(new URL('../current/forecast.json',base))).json();
 const template=await (await fetch(new URL('../news/availability.json',base))).json();
 const matching={...template,observed_at:new Date().toISOString(),players:doc.documents['current-players.json'].players.map(p=>({
  id:p.id,name:p.web_name,team:p.team,position:p.position,price_tenths:Math.round(p.price*10),status:p.status,
  news:p.news||'',news_added:p.news_added||null,chance_of_playing_next_round:p.chance_of_playing_next_round??null,
  chance_of_playing_this_round:p.chance_of_playing_this_round??null,
 }))};
 const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const proof={};
 try{for(const [name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  for(const kind of ['changed_news','newer_team','same_confirmation']){
   const state=structuredClone(fixture.state),news=structuredClone(matching);
   const changed=news.players.find(p=>p.id===state.squad[0].id);
   if(kind==='changed_news')Object.assign(changed,{status:'d',news:'SYNTHETIC_BROWSER_INJURY_REGRESSION',news_added:news.observed_at,chance_of_playing_next_round:75});
   else if(kind==='newer_team')state.observed_at=new Date(Date.parse(forecast.data_asof)+1000).toISOString();
   const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let posts=0;
   page.on('pageerror',e=>errors.push(e.message));
   await context.route('**/news/availability.json',r=>r.fulfill({json:seal(news)}));
   await context.route('**/plans**',r=>{if(r.request().method()==='POST'){posts++;return r.abort();}return r.continue();});
   await context.addInitScript(s=>{if(!sessionStorage.getItem('transfer-wait-fixture-seeded')){localStorage.setItem('fpl-manager-state-v1',JSON.stringify(s));sessionStorage.setItem('transfer-wait-fixture-seeded','1');}localStorage.setItem('fpl-B-news-auto-plan-v1','false');},state);
   await page.goto(base+'transfers-classic.html',{waitUntil:'networkidle'});
   await page.locator('#planner-context').waitFor();
   if(kind==='same_confirmation'){
    await page.locator('[data-prepare-gw]').click();
    await page.locator('#prepare-gw-dialog [name=confirm]').check();
    await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),page.locator('#prepare-gw-dialog button[type=submit]').click()]);
    await page.locator('#planner-context').waitFor();
    assert.equal(await page.evaluate(()=>FplManagerClient.snapshot().stateValid&&FplManagerClient.snapshot().usable),true);
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('fpl-B-wait-for-forecast')),null);
   }else{
    await page.locator('[data-compute]').click();
    await page.waitForFunction(()=>sessionStorage.getItem('fpl-B-wait-for-forecast')==='1');
    const text=await page.locator('[data-compute-feedback]').innerText();
    if(kind==='changed_news'){assert.match(text,/Nye FPL-oplysninger/);assert(text.includes(changed.name));assert.doesNotMatch(text,/efter observationen/);}
    else assert.match(text,/ikke bekræfte holdet igen/);
   }
   assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('fpl-manager-state-v1'))),state);
   assert.equal(posts,0);assert.deepEqual(errors,[]);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   proof[name+'_'+kind]={synthetic_only:true,correct_wait_reason:true,request_retained:kind!=='same_confirmation',unchanged_confirmation_stays_usable:kind==='same_confirmation',private_state_unchanged:true,real_private_posts:posts,page_errors:errors};
   await context.close();
  }
 }}finally{await browser.close();}
 console.log(JSON.stringify(proof,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
