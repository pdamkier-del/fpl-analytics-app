'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { chromium } = require('playwright');

async function verify() {
  const base = new URL(process.env.FPL_PREVIEW_URL);
  const liveGw = Number(process.env.FPL_EXPECT_LIVE_GW || 0);
  const planFixturePath = process.env.FPL_TEST_PLAN_FIXTURE;
  const fixture = planFixturePath ? JSON.parse(await fs.readFile(planFixturePath, 'utf8')) : null;
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH, args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      let submissions = 0;
      await page.route('**/plans**', route => {
        if (route.request().method() !== 'POST') return route.continue();
        submissions++;
        return route.abort();
      });
      async function checkDashboard() {
        if (liveGw) {
          await page.waitForFunction(gw => {
            const current = window.FplDashboardContext?.();
            return current?.usable && current.forecast.gws[0] === gw;
          }, liveGw);
        } else {
          await page.getByRole('heading', { name: /Historisk prognose/ }).waitFor();
        }
      }
      await page.goto(new URL('overview.html', base).href);
      await checkDashboard();

      let saved = await page.evaluate(data => {
        const state = data?.state || {
          season: '2026-27', squad: Array.from({ length: 15 }, (_, i) => ({ id: i + 1 })),
        };
        FplManagerStore.save(state);
        if (data) localStorage.setItem('fpl-manager-plan-B-preview-v1', JSON.stringify(data.result));
        return state;
      }, fixture);
      await page.goto(new URL('transfers-classic.html', base).href);
      await page.evaluate(() => FplManagerClient.load());
      assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
      assert.equal(await page.evaluate(() => FplManagerClient.snapshot().usable), Boolean(liveGw));
      if (fixture) {
        assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan?.manager_state_sha256),
          fixture.result.manager_state_sha256);
        saved = await page.evaluate(() => {
          const edited = FplManagerStore.read();
          edited.bank_tenths++;
          FplManagerStore.save(edited);
          return edited;
        });
        await page.reload();
        await page.evaluate(() => FplManagerClient.load());
        assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan), null);
      }

      await page.evaluate(async () => {
        await navigator.serviceWorker.ready;
      });
      await page.waitForFunction(() => !!navigator.serviceWorker.controller);
      const workerPath = process.env.FPL_TEST_WORKER_FILE;
      if (workerPath) {
        const original = await fs.readFile(workerPath, 'utf8');
        const next = original.replace(/const cacheName = cachePrefix \+ '[^']+'/, "const cacheName = cachePrefix + 'smoke-next'");
        assert.notEqual(next, original);
        try {
          await fs.writeFile(workerPath, next);
          await page.evaluate(async () => {
            const registration = await navigator.serviceWorker.ready;
            const updated = new Promise(resolve => {
              navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true });
            });
            await registration.update();
            await Promise.race([updated, new Promise((_, reject) => {
              setTimeout(() => reject(new Error('New worker did not take control')), 10_000);
            })]);
          });
          assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
          assert(await page.evaluate(async () => (await caches.keys()).some(key => key.endsWith(':smoke-next'))));
        } finally {
          await fs.writeFile(workerPath, original);
        }
      }
      await context.setOffline(true);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.getByRole('heading', { name: 'Ingen forbindelse' }).waitFor();
      await context.setOffline(false);
      await page.goto(new URL('overview.html', base).href, { waitUntil: 'domcontentloaded' });
      await checkDashboard();
      assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
      assert.equal(submissions, 0);
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

verify().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
