"""Isolated renderer regression. Synthetic values, no FPL/manager/network payloads."""
async def check(browser,base):
 from urllib.parse import urlparse
 assert urlparse(base).hostname in ('127.0.0.1','localhost'), 'Fixture is local-test-only'
 context=await browser.new_context();page=await context.new_page()
 await page.route('**/__display_fixture__',lambda r:r.fulfill(content_type='text/html',body='<section data-shared-team="transfers"></section>'))
 await page.goto(base+'__display_fixture__')
 await page.add_script_tag(url=base+'model-contract-v1.js')
 await page.add_script_tag(url=base+'shared-team-model.js')
 await page.evaluate('''()=>{
 const positions=[1,1,2,2,2,2,2,3,3,3,3,3,4,4,4],gws=[12,13,14,15,16,17];
 const players=positions.map((position,i)=>({id:i+1,name:'Synthetic '+(i+1),position,team_id:Math.floor(i/3)+1,price_tenths:50,weeks:gws.map(gw=>({gw,xpts:1.25,xmins:60,fixtures:[{p_start:.9}]}))}));
 const ids=[1,3,4,5,8,9,10,11,13,14,15,2,6,7,12],picks=ids.map((element,i)=>({element,position:i+1,is_captain:i===1,is_vice_captain:i===2}));
 const f={model:'B-MM-PM-TS-v1',locked_model_active:false,season:'2026-27',gws,data_asof:new Date(Date.now()-3600000).toISOString(),origin_deadline:new Date(Date.now()+86400000).toISOString(),forecast_sha256:'a'.repeat(64),players};
 window.__fixtureContext={forecast:f,people:new Map(players.map(p=>[p.id,p])),official:{players:players.map(p=>({id:p.id,status:'a'})),teams:{}},usable:false,stateValid:false,reason:'Synthetic stale FPL-status',plan:null,busy:false};
 window.__fixtureComputeCalls=0;
 window.FplManagerClient={load:async()=>{},snapshot:()=>__fixtureContext,compute:()=>{__fixtureComputeCalls++}};
 window.FplHistoryRefreshClient={run:async()=>({entry_id:7647524,season:f.season,observed_at:new Date().toISOString(),weeks:[{gw:11,picks}]}),acknowledge:()=>{}};
 window.FplOfficialManagerImport={loadInitialPrices:async()=>null,fromOfficialHistory:()=>({})};
 }''')
 await page.add_script_tag(url=base+'shared-team.js')
 await page.evaluate("window.dispatchEvent(new Event('DOMContentLoaded'))")
 await page.wait_for_function('document.querySelectorAll(".team-player").length===15')
 assert set(await page.locator('.team-player-button>strong').all_text_contents())=={'1,3 xP'}
 assert all('60 min' in text for text in await page.locator('.team-player>small').all_text_contents())
 assert 'Synthetic stale FPL-status' in await page.locator('.projection-source').inner_text()
 await page.locator('[data-team-period]').select_option('all')
 assert set(await page.locator('.team-player-button>strong').all_text_contents())=={'7,5 xP'}
 assert all('360 min' in text for text in await page.locator('.team-player>small').all_text_contents())
 assert await page.evaluate('__fixtureComputeCalls===0&&!__fixtureContext.usable')
 await context.close()
 return dict(scope='Local synthetic renderer fixture, not actual manager evidence',players=15,one_gw_xp=1.25,six_gw_xp=7.5,stale_ts_still_blocked=True)
