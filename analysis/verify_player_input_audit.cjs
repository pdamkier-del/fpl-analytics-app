'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const proof={};
 try{
  for(const[name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
   const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let posts=0;
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/plans**',r=>{if(r.request().method()==='POST'){posts++;return r.abort()}return r.continue()});
   const url=process.env.DESKTOP_URL+'player.html?id=399';
   await page.goto(url,{waitUntil:'networkidle'});
   const panel=page.locator('.player-input-audit').first();await panel.locator('summary').click();
   await page.waitForFunction(()=>document.querySelector('.player-input-audit')?.dataset.auditLoaded==='true');
   const expected=await page.evaluate(async()=>{
    const d=await FplBExistingApp.probabilities(),i=await(await fetch('../input-audit/index.json')).json();
    const a=await(await fetch('../input-audit/'+i.file)).json();return{forecast:d.forecast.forecast_sha256,audit:a.forecast_sha256,player:a.players.find(p=>p.id===399),players:a.players.length};
   });
   assert.equal(expected.forecast,expected.audit);assert.equal(await panel.getAttribute('data-forecast'),expected.forecast);
   assert.equal(await panel.locator('tbody tr').count(),7);
   assert.match(await panel.innerText(),/kun Premier League/);assert.match(await panel.innerText(),/Trænerudtalelser/);
   assert.match(await panel.innerText(),expected.player.physical_team_minutes_verified?/Kampens minutbudget er afstemt/:/Ikke fuldt sammenhængende/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(posts,0);assert.deepEqual(errors,[]);
   proof[name]={forecast_sha256:expected.forecast,players_audited:expected.players,per_player_status_matches_report:true,private_posts:posts,page_errors:errors,normal_browser_security:true,scheme:new URL(url).protocol};
   await context.close();
  }
  const context=await browser.newContext(),page=await context.newPage();
  await page.route('**/input-audit/index.json',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({schema:'B-all-player-chain-audit-index-v1',forecast_sha256:'another forecast'})}));
  await page.goto(process.env.DESKTOP_URL+'player.html?id=399',{waitUntil:'networkidle'});
  const bad=page.locator('.player-input-audit').first();await bad.locator('summary').click();
  await page.waitForFunction(()=>document.querySelector('.player-input-audit')?.dataset.auditLoaded==='false');
  assert.match(await bad.innerText(),/Dækningen er derfor ikke bekræftet/);assert.equal(await bad.locator('tbody tr').count(),0);
  proof.stale_or_missing_audit_never_green=true;await context.close();
  const corrupt=await browser.newContext(),badpage=await corrupt.newPage();
  await badpage.route('**/input-audit/audit.json',r=>r.fulfill({status:200,contentType:'application/json',body:'{"schema":"B-all-player-chain-audit-v1"}'}));
  await badpage.goto(process.env.DESKTOP_URL+'player.html?id=399',{waitUntil:'networkidle'});
  const broken=badpage.locator('.player-input-audit').first();await broken.locator('summary').click();
  await badpage.waitForFunction(()=>document.querySelector('.player-input-audit')?.dataset.auditLoaded==='false');
  assert.equal(await broken.locator('tbody tr').count(),0);proof.tampered_audit_checksum_rejected=true;await corrupt.close();
 }finally{await browser.close()}
 console.log(JSON.stringify(proof,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
