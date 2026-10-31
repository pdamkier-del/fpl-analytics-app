'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.DESKTOP_URL||'http://127.0.0.1:18130/mm-preview/app/';
 const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});const report={};
 try{for(const [name,viewport]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport}),page=await context.newPage(),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/plans**',route=>{if(route.request().method()==='POST'){posts++;return route.abort();}return route.continue();});
  await context.addInitScript(()=>localStorage.setItem('fpl-manager-state-v1','history-test-preserved'));
  await page.goto(base+'history-classic.html',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.querySelector('#archive-count')?.textContent.includes('841 spillere'));
  assert.equal(await page.locator('#archive-season option').count(),4);
  assert.equal(await page.locator('.sidebar .brand').innerText(),'xP\nFPL Analytics');
  await page.locator('#archive-season').selectOption('2024-25');
  await page.waitForFunction(()=>document.querySelector('#archive-count')?.textContent.includes('784 spillere'));
  await page.locator('#archive-search').fill('haaland');
  assert.equal(await page.locator('#archive-results tbody tr').count(),1);
  await page.locator('#archive-results button').click();
  await page.waitForFunction(()=>document.querySelector('#archive-detail h2')?.textContent.includes('Haaland'));
  const player=await page.locator('#archive-detail h2').innerText();
  const matchRows=await page.locator('#archive-detail tbody tr').count();assert.equal(matchRows,38);
  const currentLink=new URL(await page.locator('#archive-detail > a').getAttribute('href'),base);assert(currentLink.pathname.endsWith('/player.html'));assert.match(currentLink.searchParams.get('id'),/^\d+$/);
  await page.locator('[data-archive-view="teams"]').click();
  assert.equal(await page.locator('#archive-results tbody tr').count(),20);
  await page.locator('#archive-search').fill('arsenal');
  assert.equal(await page.locator('#archive-results tbody tr').count(),1);
  await page.locator('#archive-results button').click();
  await page.waitForFunction(()=>document.querySelector('#archive-detail h2')?.textContent.includes('Arsenal'));
  assert.equal(await page.locator('#archive-detail tbody tr').count(),38);
  for(const season of ['2022-23','2023-24']){
   await page.locator('#archive-season').selectOption(season);
   await page.waitForFunction(value=>document.querySelector('#archive-count')?.textContent.includes(value),season.replace('-','/'));
   await page.locator('#archive-results button').click();
   await page.waitForFunction(value=>document.querySelector('#archive-detail h2')?.textContent.includes(value),season.replace('-','/'));
   assert.equal(await page.locator('#archive-detail tbody tr').count(),38);
  }
  await page.locator('#archive-season').selectOption('2025-26');
  await page.waitForFunction(()=>document.querySelector('#archive-count')?.textContent.includes('2025/26'));
  assert.equal(await page.locator('#archive-results tbody tr').count(),1);
  await page.locator('#archive-results button').click();
  await page.waitForFunction(()=>document.querySelector('#archive-detail h2')?.textContent.includes('2025/26'));
  assert.equal(await page.locator('#archive-detail tbody tr').count(),38);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await page.evaluate(()=>localStorage.getItem('fpl-manager-state-v1')),'history-test-preserved');
  assert.deepEqual(errors,[]);assert.equal(posts,0);
  const links=await page.evaluate(()=>fetch('../history-archive/index.json').then(r=>r.json()));
  const playerUuid=Object.entries(links.current_players).find(([uuid,code])=>String(links.current_player_ids[code])===currentLink.searchParams.get('id'))[0];
  await page.goto(base+'history-classic.html?season=2024-25&player='+encodeURIComponent(playerUuid),{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.querySelector('#archive-detail h2')?.textContent.includes('Haaland'));
  report[name]={player,player_matches:matchRows,team_matches_per_season:38,archived_seasons:4,player_deeplink:true,original_desktop_shell:true,manager_unchanged:true,private_posts:posts,page_errors:errors};
  await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
