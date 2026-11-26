"""Prepublication Chromium smoke: real public assets, explicitly unavailable backend."""
import asyncio,json,sys
from playwright.async_api import async_playwright
async def main():
 async with async_playwright()as p:
  browser=await p.chromium.launch(executable_path=sys.argv[2],headless=True,args=['--no-sandbox'])
  context=await browser.new_context(ignore_https_errors=True);page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  # Fault injection, not a fake manager: no official/private requests started in CI.
  await context.route('https://fpl-analytics-private-manager.onrender.com/**',lambda r:r.fulfill(status=503,content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body='{"error":"Test: backend unavailable"}'))
  results=[]
  for name in ['overview.html','transfers-classic.html','players-classic.html']:
   await page.goto(sys.argv[1]+name,wait_until='domcontentloaded',timeout=60000);await page.wait_for_timeout(6000)
   assert await page.locator('nav.fpl-primary-navigation').count()==1
   if name!='players-classic.html':
    assert await page.locator('[data-shared-team]').count()==1
    assert 'Historisk prognose · GW12'not in await page.locator('body').inner_text()
    assert await page.locator('#planner-context').count()==0
   await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(300)
   overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
   assert not overflow,(name,'mobile overflow')
   results.append(dict(page=name,mobile_no_overflow=True));await page.set_viewport_size({'width':1360,'height':1000})
  assert not errors,errors
  print(json.dumps(dict(scope='Prepublication: public assets plus explicitly unavailable backend; no actual manager or TS result fixture',checks=results,page_errors=errors),indent=2));await browser.close()
asyncio.run(main())
